"""Per-run summaries that keep application and scheduler clock domains separate."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from cpu_fairness.analysis.fairness import analyze_delta_windows
from cpu_fairness.telemetry.parser import read_trace


class AnalysisError(ValueError):
    """A completed run does not contain valid inputs for per-run analysis."""


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"cannot read {label} at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"{label} at {path} must contain a JSON object")
    return value


def _read_jsonl_objects(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AnalysisError(f"cannot read {label} at {path}: {exc}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"{label} line {line_number} is invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise AnalysisError(f"{label} line {line_number} must contain a JSON object")
        records.append(value)
    return records


def _required_nonnegative_integer(record: dict[str, Any], key: str, label: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AnalysisError(f"{label}.{key} must be a nonnegative integer")
    return value


def nearest_rank_summary(values: list[int]) -> dict[str, Any]:
    """Return sample count and nearest-rank p50/p95 for nonnegative integer values."""
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise AnalysisError("percentile samples must be nonnegative integers")
    ordered = sorted(values)

    def nearest_rank(percentile: float) -> int | None:
        if not ordered:
            return None
        rank = math.ceil(percentile * len(ordered))
        return ordered[rank - 1]

    return {
        "sample_count": len(ordered),
        "method": "nearest_rank",
        "p50_ns": nearest_rank(0.50),
        "p95_ns": nearest_rank(0.95),
    }


def _manifest_output(manifest: dict[str, Any], key: str, fallback: Path) -> Path:
    outputs = manifest.get("outputs", {})
    value = outputs.get(key) if isinstance(outputs, dict) else None
    return Path(value) if isinstance(value, str) else fallback


def analyze_run(run_directory: str | Path) -> dict[str, Any]:
    """Summarize one completed raw run without changing its files."""
    run_path = Path(run_directory).expanduser().resolve()
    manifest = _read_json_object(run_path / "manifest.json", "run manifest")
    if manifest.get("status") != "completed":
        raise AnalysisError("only runs with manifest status 'completed' can be analyzed")

    configuration = manifest.get("configuration")
    processes = manifest.get("processes")
    if not isinstance(configuration, dict) or not isinstance(processes, dict):
        raise AnalysisError("manifest is missing configuration or process identities")
    interactive = processes.get("interactive")
    batch = processes.get("batch")
    if not isinstance(interactive, dict) or not isinstance(batch, dict):
        raise AnalysisError("manifest is missing interactive or batch process identity")
    interactive_tids = interactive.get("tids")
    batch_tids = batch.get("tids")
    if not isinstance(interactive_tids, list) or not interactive_tids or not isinstance(batch_tids, list) or not batch_tids:
        raise AnalysisError("manifest is missing workload TIDs")
    interactive_tid, batch_tid = interactive_tids[0], batch_tids[0]
    for role, tid in (("interactive", interactive_tid), ("batch", batch_tid)):
        if isinstance(tid, bool) or not isinstance(tid, int) or tid <= 0:
            raise AnalysisError(f"manifest {role} TID must be a positive integer")
    if interactive_tid == batch_tid:
        raise AnalysisError("interactive and batch workload TIDs must be distinct")

    interactive_path = _manifest_output(
        manifest, "interactive_jsonl", run_path / "interactive.jsonl"
    )
    batch_path = _manifest_output(manifest, "batch_summary", run_path / "batch.json")
    interactive_records = _read_jsonl_objects(interactive_path, "interactive workload log")
    if not interactive_records:
        raise AnalysisError("interactive workload log contains no request records")
    approximate_response_times: list[int] = []
    turnaround_times: list[int] = []
    legacy_latency_values: list[int] = []
    timing_schemas: set[str] = set()
    for index, record in enumerate(interactive_records, start=1):
        label = f"interactive record line {index}"
        release_ns = _required_nonnegative_integer(
            record, "intended_release_monotonic_ns", label
        )
        start_ns = _required_nonnegative_integer(
            record, "execution_start_monotonic_ns", label
        )
        completion_ns = _required_nonnegative_integer(
            record, "completion_monotonic_ns", label
        )
        if not release_ns <= start_ns <= completion_ns:
            raise AnalysisError(
                f"{label} timestamps must satisfy release <= execution start <= completion"
            )
        approximate_response_ns = start_ns - release_ns
        turnaround_ns = completion_ns - release_ns

        has_approx = "approx_response_time_ns" in record
        has_turnaround = "turnaround_time_ns" in record
        if has_approx != has_turnaround:
            raise AnalysisError(
                f"{label} must provide both approx_response_time_ns and turnaround_time_ns"
            )
        if has_approx:
            recorded_response = _required_nonnegative_integer(
                record, "approx_response_time_ns", label
            )
            recorded_turnaround = _required_nonnegative_integer(
                record, "turnaround_time_ns", label
            )
            if recorded_response != approximate_response_ns:
                raise AnalysisError(
                    f"{label}.approx_response_time_ns does not match its source timestamps"
                )
            if recorded_turnaround != turnaround_ns:
                raise AnalysisError(
                    f"{label}.turnaround_time_ns does not match its source timestamps"
                )
            timing_schemas.add("corrected_explicit_fields")
        else:
            # Old records called release-to-completion response_latency_ns. Keep
            # it visible as a legacy field, but derive corrected metrics only
            # from the preserved source timestamps above.
            legacy_latency_values.append(
                _required_nonnegative_integer(record, "response_latency_ns", label)
            )
            timing_schemas.add("legacy_field_timestamp_derived")
        approximate_response_times.append(approximate_response_ns)
        turnaround_times.append(turnaround_ns)
    batch_record = _read_json_object(batch_path, "batch workload summary")
    completed_units = _required_nonnegative_integer(batch_record, "completed_units", "batch summary")
    elapsed_ns = batch_record.get("duration_monotonic_ns")
    if isinstance(elapsed_ns, bool) or not isinstance(elapsed_ns, int) or elapsed_ns <= 0:
        raise AnalysisError("batch summary.duration_monotonic_ns must be a positive integer")

    analysis_path = _manifest_output(
        manifest,
        "analysis",
        run_path.parent.parent / "processed" / run_path.name / "analysis.json",
    )
    scheduler_analysis = _read_json_object(analysis_path, "scheduler analysis")
    waits_path = _manifest_output(
        manifest,
        "wait_episodes",
        analysis_path.parent / "wait_episodes.jsonl",
    )
    wait_records = _read_jsonl_objects(waits_path, "wait episode output")
    wait_records_by_tid: dict[int, list[dict[str, Any]]] = {
        interactive_tid: [],
        batch_tid: [],
    }
    for index, record in enumerate(wait_records, start=1):
        tid = record.get("tid")
        if isinstance(tid, bool) or not isinstance(tid, int) or tid not in wait_records_by_tid:
            raise AnalysisError(f"wait episode line {index} has an unknown or invalid TID")
        if not isinstance(record.get("complete"), bool):
            raise AnalysisError(f"wait episode line {index} must have a boolean complete field")
        if record["complete"]:
            _required_nonnegative_integer(record, "wait_ns", f"wait episode line {index}")
        elif record.get("wait_ns") is not None:
            _required_nonnegative_integer(record, "wait_ns", f"wait episode line {index}")
        wait_records_by_tid[tid].append(record)
    service_path = _manifest_output(
        manifest,
        "task_accounting",
        analysis_path.parent / "task_accounting.json",
    )
    try:
        service_value = json.loads(service_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"cannot read task accounting at {service_path}: {exc}") from exc
    if not isinstance(service_value, list) or any(not isinstance(row, dict) for row in service_value):
        raise AnalysisError(f"task accounting at {service_path} must contain a JSON array of objects")

    def task_metrics(tid: int, role: str) -> dict[str, Any]:
        task_waits = wait_records_by_tid[tid]
        complete_waits = [
            _required_nonnegative_integer(record, "wait_ns", f"{role} wait episode")
            for record in task_waits
            if record["complete"]
        ]
        censored_count = sum(not record["complete"] for record in task_waits)
        service = next((row for row in service_value if row.get("tid") == tid), None)
        if service is None:
            raise AnalysisError(f"task accounting is missing {role} TID {tid}")
        service_ns = _required_nonnegative_integer(service, "cpu_service_ns", f"{role} task accounting")
        return {
            "tid": tid,
            "nice_value": manifest["processes"][role].get("nice_value"),
            "runnable_wait": {
                **nearest_rank_summary(complete_waits),
                "complete_sample_count": len(complete_waits),
                "censored_sample_count": censored_count,
            },
            "cpu_service_ns": service_ns,
            "incomplete_service_intervals": service.get("incomplete_service_intervals"),
        }

    event_counts = scheduler_analysis.get("event_counts", {})
    policy_application = manifest.get("policy_application", {})
    policy = configuration.get("policy", {})
    trace_path = _manifest_output(manifest, "raw_trace", run_path / "scheduler.tsv")
    environment = manifest.get("environment", {})
    cpu_quota = environment.get("cpu_quota") if isinstance(environment, dict) else None
    if not isinstance(cpu_quota, dict) or cpu_quota.get("status") != "unlimited":
        delta_fairness = {
            "status": "unavailable",
            "reason": "run manifest does not verify an unlimited cgroup CPU quota",
        }
    else:
        try:
            trace_events, trace_end_ns = read_trace(trace_path)
            task_metadata = {
                interactive_tid: {
                    "workload_class": "interactive",
                    "nice_value": interactive.get("nice_value"),
                    "scheduler_policy": (interactive.get("scheduler_policy") or {}).get("name")
                    if isinstance(interactive.get("scheduler_policy"), dict)
                    else None,
                },
                batch_tid: {
                    "workload_class": "batch",
                    "nice_value": batch.get("nice_value"),
                    "scheduler_policy": (batch.get("scheduler_policy") or {}).get("name")
                    if isinstance(batch.get("scheduler_policy"), dict)
                    else None,
                },
            }
            delta_fairness = analyze_delta_windows(
                trace_events,
                task_metadata,
                trace_end_ns if trace_end_ns is not None else -1,
                environment.get("effective_cpu_count"),
            )
        except (OSError, ValueError) as exc:
            delta_fairness = {
                "status": "unavailable",
                "reason": f"cannot analyze scheduler trace for Delta windows: {exc}",
            }
    return {
        "data_kind": "measured_run_metrics",
        "run_id": manifest.get("run_id", run_path.name),
        "policy": policy.get("type") if isinstance(policy, dict) else None,
        "policy_application": policy_application,
        "interactive": {
            **task_metrics(interactive_tid, "interactive"),
            "approx_response_time": nearest_rank_summary(approximate_response_times),
            "turnaround_time": nearest_rank_summary(turnaround_times),
            "per_request_cpu_service_time": {
                "available": False,
                "reason": "Current scheduler tracing reports CPU service per TID, not per interactive request.",
            },
        },
        "interactive_timing_schema": (
            next(iter(timing_schemas)) if len(timing_schemas) == 1 else "mixed_legacy_and_corrected_records"
        ),
        "legacy_ambiguous_response_latency": (
            {
                "field_name": "response_latency_ns",
                "summary": nearest_rank_summary(legacy_latency_values),
                "used_for_corrected_metrics": False,
                "note": "Legacy records used this name for release-to-completion; corrected metrics above are derived from the preserved timestamps.",
            }
            if legacy_latency_values
            else None
        ),
        "batch": {
            **task_metrics(batch_tid, "batch"),
            "completed_units": completed_units,
            "elapsed_ns": elapsed_ns,
            "throughput_units_per_second": completed_units * 1_000_000_000 / elapsed_ns,
        },
        "scheduler_event_counts": event_counts,
        "delta_fairness": delta_fairness,
        "warnings": {
            "manifest": manifest.get("warnings", []),
            "analysis": scheduler_analysis.get("warnings", []),
        },
        "metric_definitions": {
            "percentiles": "nearest-rank; rank = ceil(p * sample_count), one-based",
            "approx_response_time": "execution-start timestamp minus intended-release timestamp; Python monotonic nanoseconds; approximate user-space observation, not the exact kernel first-scheduled time",
            "turnaround_time": "completion timestamp minus intended-release timestamp; Python monotonic nanoseconds",
            "per_request_cpu_service_time": "not measured; scheduler-derived CPU service is currently per TID and must not be substituted for per-request service",
            "runnable_wait": "bpftrace timestamp difference; complete episodes only; grouped by task TID",
            "cpu_service": "sum of observed sched_switch intervals in bpftrace nanoseconds",
            "batch_throughput": "completed units divided by batch elapsed monotonic seconds",
            "clock_domains_subtracted": False,
        },
    }
