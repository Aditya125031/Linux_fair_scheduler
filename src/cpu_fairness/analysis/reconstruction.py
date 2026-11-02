"""Reconstruct target-task runnable waits and observed CPU service."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from cpu_fairness.telemetry.parser import SchedulerEvent


@dataclass
class WaitEpisode:
    tid: int
    ready_since_ns: int
    scheduled_at_ns: int | None
    wait_ns: int | None
    complete: bool
    reason: str


@dataclass
class TaskAccounting:
    tid: int
    cpu_service_ns: int = 0
    observed_service_intervals: int = 0
    incomplete_service_intervals: int = 0
    scheduled_in_count: int = 0
    switch_out_count: int = 0


def reconstruct(
    events: Iterable[SchedulerEvent], target_tids: set[int], end_timestamp_ns: int | None
) -> tuple[list[WaitEpisode], dict[int, TaskAccounting], list[str]]:
    """Reconstruct waits (wakeup and runnable preemption) and switch intervals.

    All durations are computed solely from bpftrace ``nsecs`` timestamps. Python
    monotonic timestamps must not be mixed into this reconstruction.
    """
    ordered = sorted(events, key=lambda event: (event.timestamp_ns, event.line_number))
    ready_since: dict[int, int] = {}
    running_since: dict[int, int] = {}
    accounting = {tid: TaskAccounting(tid=tid) for tid in target_tids}
    waits: list[WaitEpisode] = []
    warnings: list[str] = []

    for event in ordered:
        if event.event == "WAKEUP":
            tid = event.tid
            if tid not in target_tids:
                continue
            if tid in ready_since:
                warnings.append(f"duplicate wakeup for TID {tid} at {event.timestamp_ns}")
            elif tid not in running_since:
                ready_since[tid] = event.timestamp_ns
            continue

        prev_tid = event.prev_tid
        next_tid = event.next_tid
        if prev_tid == next_tid and prev_tid in target_tids:
            continue

        if prev_tid in target_tids:
            task = accounting[prev_tid]
            task.switch_out_count += 1
            start = running_since.pop(prev_tid, None)
            if start is None:
                task.incomplete_service_intervals += 1
                warnings.append(f"switch-out without observed switch-in for TID {prev_tid}")
            elif event.timestamp_ns >= start:
                task.cpu_service_ns += event.timestamp_ns - start
                task.observed_service_intervals += 1
            else:
                task.incomplete_service_intervals += 1
                warnings.append(f"negative service interval for TID {prev_tid}")

            if event.prev_state == 0:
                if prev_tid in ready_since:
                    warnings.append(f"preemption while TID {prev_tid} already has pending wait")
                else:
                    ready_since[prev_tid] = event.timestamp_ns

        if next_tid in target_tids:
            task = accounting[next_tid]
            task.scheduled_in_count += 1
            ready = ready_since.pop(next_tid, None)
            if ready is not None:
                if event.timestamp_ns >= ready:
                    waits.append(
                        WaitEpisode(next_tid, ready, event.timestamp_ns, event.timestamp_ns - ready, True, "scheduled")
                    )
                else:
                    warnings.append(f"negative wait interval for TID {next_tid}")
            if next_tid in running_since:
                task.incomplete_service_intervals += 1
                warnings.append(f"switch-in while TID {next_tid} was already marked running")
            running_since[next_tid] = event.timestamp_ns

    for tid, ready in ready_since.items():
        wait_ns = end_timestamp_ns - ready if end_timestamp_ns is not None and end_timestamp_ns >= ready else None
        waits.append(WaitEpisode(tid, ready, None, wait_ns, False, "trace_end_censored"))
    for tid, start in running_since.items():
        task = accounting[tid]
        if end_timestamp_ns is not None and end_timestamp_ns >= start:
            task.cpu_service_ns += end_timestamp_ns - start
        task.incomplete_service_intervals += 1
    waits.sort(key=lambda episode: (episode.ready_since_ns, episode.tid))
    return waits, accounting, warnings


def to_records(items: Iterable[WaitEpisode | TaskAccounting]) -> list[dict[str, object]]:
    return [asdict(item) for item in items]
