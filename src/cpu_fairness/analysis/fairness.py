"""Offline capacity-normalized Delta fairness analysis over trace-clock windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from cpu_fairness.telemetry.parser import SchedulerEvent


NICE_TO_WEIGHT = (
    88761, 71755, 56483, 46273, 36291, 29154, 23254, 18705, 14949, 11916,
    9548, 7620, 6100, 4904, 3906, 3121, 2501, 1991, 1586, 1277,
    1024, 820, 655, 526, 423, 335, 272, 215, 172, 137,
    110, 87, 70, 56, 45, 36, 29, 23, 18, 15,
)
NICE_WEIGHT_BASE = -20
DEFAULT_WINDOW_NS = 50_000_000
DEFAULT_MIN_RUNNABLE_DEMAND_NS = 1


@dataclass(frozen=True)
class TaskWindow:
    """One task's observed on-CPU service and runnable wait in a window."""

    tid: int
    workload_class: str
    nice_value: int
    service_ns: int
    runnable_wait_ns: int


def nice_to_weight(nice_value: int) -> int:
    """Map Linux nice -20..19 to the standard fair-scheduler load weight."""
    if isinstance(nice_value, bool) or not isinstance(nice_value, int):
        raise ValueError("nice_value must be an integer")
    index = nice_value - NICE_WEIGHT_BASE
    if not 0 <= index < len(NICE_TO_WEIGHT):
        raise ValueError("nice_value must be between -20 and 19")
    return NICE_TO_WEIGHT[index]


def calculate_delta_window(
    tasks: Iterable[TaskWindow],
    cpu_count: int,
    window_ns: int,
    min_runnable_demand_ns: int = DEFAULT_MIN_RUNNABLE_DEMAND_NS,
) -> dict[str, Any]:
    """Calculate Delta and directional class deficits for one micro-window."""
    if isinstance(cpu_count, bool) or not isinstance(cpu_count, int) or cpu_count <= 0:
        raise ValueError("cpu_count must be a positive integer")
    if isinstance(window_ns, bool) or not isinstance(window_ns, int) or window_ns <= 0:
        raise ValueError("window_ns must be a positive integer")
    if (
        isinstance(min_runnable_demand_ns, bool)
        or not isinstance(min_runnable_demand_ns, int)
        or min_runnable_demand_ns <= 0
    ):
        raise ValueError("min_runnable_demand_ns must be a positive integer")

    seen_tids: set[int] = set()
    prepared: list[dict[str, Any]] = []
    for task in tasks:
        if task.tid in seen_tids:
            raise ValueError(f"duplicate TID {task.tid} in fairness window")
        seen_tids.add(task.tid)
        if task.workload_class not in {"interactive", "batch"}:
            raise ValueError(f"unsupported workload class {task.workload_class!r}")
        for name, value in (("service_ns", task.service_ns), ("runnable_wait_ns", task.runnable_wait_ns)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        demand_ns = task.service_ns + task.runnable_wait_ns
        if demand_ns > window_ns:
            raise ValueError(f"TID {task.tid} demand exceeds the window duration")
        if demand_ns < min_runnable_demand_ns:
            continue
        weight = nice_to_weight(task.nice_value)
        prepared.append(
            {
                "tid": task.tid,
                "workload_class": task.workload_class,
                "nice_value": task.nice_value,
                "weight": weight,
                "service_ns": task.service_ns,
                "runnable_wait_ns": task.runnable_wait_ns,
                "runnable_demand_ns": demand_ns,
            }
        )

    if not prepared:
        return {
            "task_count": 0,
            "global_delta": None,
            "interactive_mean_deficit": None,
            "batch_mean_deficit": None,
            "delta_batch_to_interactive": None,
            "delta_interactive_to_batch": None,
            "tasks": [],
        }

    total_weight = sum(task["weight"] for task in prepared)
    capacity_ns = cpu_count * window_ns
    for task in prepared:
        fair_capacity_share_ns = capacity_ns * task["weight"] / total_weight
        entitlement_ns = min(task["runnable_demand_ns"], fair_capacity_share_ns)
        normalized_service = min(1.0, task["service_ns"] / entitlement_ns)
        task["fair_capacity_share_ns"] = fair_capacity_share_ns
        task["entitlement_ns"] = entitlement_ns
        task["normalized_service"] = normalized_service

    maximum_service = max(task["normalized_service"] for task in prepared)
    for task in prepared:
        task["deficit"] = maximum_service - task["normalized_service"]

    interactive = [task["deficit"] for task in prepared if task["workload_class"] == "interactive"]
    batch = [task["deficit"] for task in prepared if task["workload_class"] == "batch"]
    interactive_mean = sum(interactive) / len(interactive) if interactive else None
    batch_mean = sum(batch) / len(batch) if batch else None
    delta_batch_to_interactive = (
        max(0.0, interactive_mean - batch_mean)
        if interactive_mean is not None and batch_mean is not None
        else None
    )
    delta_interactive_to_batch = (
        max(0.0, batch_mean - interactive_mean)
        if interactive_mean is not None and batch_mean is not None
        else None
    )
    return {
        "task_count": len(prepared),
        "global_delta": sum(task["deficit"] for task in prepared) / len(prepared),
        "interactive_mean_deficit": interactive_mean,
        "batch_mean_deficit": batch_mean,
        "delta_batch_to_interactive": delta_batch_to_interactive,
        "delta_interactive_to_batch": delta_interactive_to_batch,
        "tasks": prepared,
    }


def _intervals_by_tid(
    events: Iterable[SchedulerEvent], target_tids: set[int], end_ns: int
) -> tuple[dict[int, list[tuple[int, int]]], dict[int, list[tuple[int, int]]], list[str]]:
    """Build observed service and runnable-wait intervals from scheduler events."""
    service: dict[int, list[tuple[int, int]]] = {tid: [] for tid in target_tids}
    waiting: dict[int, list[tuple[int, int]]] = {tid: [] for tid in target_tids}
    running_since: dict[int, int] = {}
    ready_since: dict[int, int] = {}
    warnings: list[str] = []

    for event in sorted(events, key=lambda row: (row.timestamp_ns, row.line_number)):
        if event.event == "WAKEUP":
            tid = event.tid
            if tid not in target_tids:
                continue
            if tid in ready_since:
                warnings.append(f"duplicate wakeup for TID {tid} at {event.timestamp_ns}")
            elif tid not in running_since:
                ready_since[tid] = event.timestamp_ns
            continue

        prev_tid, next_tid = event.prev_tid, event.next_tid
        if prev_tid == next_tid and prev_tid in target_tids:
            continue
        if prev_tid in target_tids:
            start = running_since.pop(prev_tid, None)
            if start is None:
                warnings.append(f"switch-out without observed switch-in for TID {prev_tid}")
            elif event.timestamp_ns >= start:
                service[prev_tid].append((start, event.timestamp_ns))
            else:
                warnings.append(f"negative service interval for TID {prev_tid}")
            if event.prev_state == 0:
                if prev_tid in ready_since:
                    warnings.append(f"preemption while TID {prev_tid} already has pending wait")
                else:
                    ready_since[prev_tid] = event.timestamp_ns
        if next_tid in target_tids:
            start = ready_since.pop(next_tid, None)
            if start is not None:
                if event.timestamp_ns >= start:
                    waiting[next_tid].append((start, event.timestamp_ns))
                else:
                    warnings.append(f"negative wait interval for TID {next_tid}")
            if next_tid in running_since:
                warnings.append(f"switch-in while TID {next_tid} was already marked running")
            running_since[next_tid] = event.timestamp_ns

    for tid, start in ready_since.items():
        if end_ns >= start:
            waiting[tid].append((start, end_ns))
    for tid, start in running_since.items():
        if end_ns >= start:
            service[tid].append((start, end_ns))
    return service, waiting, warnings


def _overlap_ns(intervals: list[tuple[int, int]], start_ns: int, end_ns: int) -> int:
    return sum(max(0, min(end_ns, end) - max(start_ns, start)) for start, end in intervals)


def analyze_delta_windows(
    events: Iterable[SchedulerEvent],
    task_metadata: dict[int, dict[str, Any]],
    end_timestamp_ns: int,
    cpu_count: int,
    window_ns: int = DEFAULT_WINDOW_NS,
    min_runnable_demand_ns: int = DEFAULT_MIN_RUNNABLE_DEMAND_NS,
) -> dict[str, Any]:
    """Calculate measured Delta metrics for full trace-clock windows.

    The initial window is omitted as a warm-up because task state may predate the
    first captured event. The final partial window is omitted because its
    observation duration is shorter than the configured window.
    """
    events = list(events)
    target_tids = set(task_metadata)
    target_events = [
        event for event in events
        if event.event == "WAKEUP" and event.tid in target_tids
        or event.event == "SWITCH" and (event.prev_tid in target_tids or event.next_tid in target_tids)
    ]
    if not target_events:
        return {"status": "unavailable", "reason": "no target-task scheduler events"}
    for tid, metadata in task_metadata.items():
        if metadata.get("scheduler_policy") != "SCHED_OTHER":
            return {
                "status": "unavailable",
                "reason": f"TID {tid} is not verified as using SCHED_OTHER",
            }
        nice = metadata.get("nice_value")
        try:
            nice_to_weight(nice)
        except (TypeError, ValueError):
            return {"status": "unavailable", "reason": f"TID {tid} has no valid nice value"}
        if metadata.get("workload_class") not in {"interactive", "batch"}:
            return {"status": "unavailable", "reason": f"TID {tid} has no supported workload class"}
    if isinstance(end_timestamp_ns, bool) or not isinstance(end_timestamp_ns, int):
        return {"status": "unavailable", "reason": "trace end timestamp is missing or invalid"}
    if isinstance(cpu_count, bool) or not isinstance(cpu_count, int) or cpu_count <= 0:
        return {"status": "unavailable", "reason": "effective CPU count is missing or invalid"}
    if (
        isinstance(window_ns, bool)
        or not isinstance(window_ns, int)
        or window_ns <= 0
        or isinstance(min_runnable_demand_ns, bool)
        or not isinstance(min_runnable_demand_ns, int)
        or min_runnable_demand_ns <= 0
    ):
        return {"status": "unavailable", "reason": "window and demand thresholds must be positive"}

    first_event_ns = min(event.timestamp_ns for event in target_events)
    first_window_start_ns = first_event_ns + window_ns
    window_count = max(0, end_timestamp_ns - first_window_start_ns) // window_ns
    if window_count == 0:
        return {
            "status": "unavailable",
            "reason": "trace is too short for a full analysis window after warm-up",
        }

    target_tids = set(task_metadata)
    service_intervals, wait_intervals, warnings = _intervals_by_tid(
        target_events, target_tids, end_timestamp_ns
    )
    windows: list[dict[str, Any]] = []
    for window_index in range(window_count):
        start_ns = first_window_start_ns + window_index * window_ns
        end_ns = start_ns + window_ns
        observations = [
            TaskWindow(
                tid=tid,
                workload_class=metadata["workload_class"],
                nice_value=metadata["nice_value"],
                service_ns=_overlap_ns(service_intervals[tid], start_ns, end_ns),
                runnable_wait_ns=_overlap_ns(wait_intervals[tid], start_ns, end_ns),
            )
            for tid, metadata in task_metadata.items()
        ]
        calculated = calculate_delta_window(
            observations, cpu_count, window_ns, min_runnable_demand_ns
        )
        if calculated["task_count"]:
            windows.append(
                {
                    "start_ns": start_ns,
                    "end_ns": end_ns,
                    **calculated,
                }
            )

    global_values = [row["global_delta"] for row in windows]
    directional_values = [
        row["delta_batch_to_interactive"]
        for row in windows
        if row["delta_batch_to_interactive"] is not None
    ]
    reverse_values = [
        row["delta_interactive_to_batch"]
        for row in windows
        if row["delta_interactive_to_batch"] is not None
    ]

    def summary(values: list[float]) -> dict[str, float | int | None]:
        ordered = sorted(values)
        return {
            "sample_count": len(ordered),
            "mean": sum(ordered) / len(ordered) if ordered else None,
            "maximum": max(ordered) if ordered else None,
            "p95_nearest_rank": ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)] if ordered else None,
        }

    return {
        "status": "available" if windows else "unavailable",
        "reason": None if windows else "no window contained an active target task",
        "metric": "delta_partitioned_batch_to_interactive",
        "clock_domain": "bpftrace nsecs",
        "window_ns": window_ns,
        "min_runnable_demand_ns": min_runnable_demand_ns,
        "effective_cpu_count": cpu_count,
        "weight_definition": "Linux fair-scheduler nice-to-weight table; task nice values and SCHED_OTHER are verified in the run manifest",
        "window_counts": {
            "full_after_warmup": window_count,
            "with_active_target_tasks": len(windows),
            "with_both_classes": len(directional_values),
        },
        "global_delta": summary(global_values),
        "delta_batch_to_interactive": summary(directional_values),
        "delta_interactive_to_batch": summary(reverse_values),
        "warnings": warnings,
        "windows": windows,
    }
