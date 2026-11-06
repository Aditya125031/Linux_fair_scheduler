"""Per-run summaries that keep application and scheduler clock domains separate."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


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
    response_latencies = [
        _required_nonnegative_integer(record, "response_latency_ns", "interactive record")
        for record in interactive_records
    ]
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
    return {
        "data_kind": "measured_run_metrics",
        "run_id": manifest.get("run_id", run_path.name),
        "policy": policy.get("type") if isinstance(policy, dict) else None,
        "policy_application": policy_application,
        "interactive": {
            **task_metrics(interactive_tid, "interactive"),
            "response_latency": nearest_rank_summary(response_latencies),
        },
        "batch": {
            **task_metrics(batch_tid, "batch"),
            "completed_units": completed_units,
            "elapsed_ns": elapsed_ns,
            "throughput_units_per_second": completed_units * 1_000_000_000 / elapsed_ns,
        },
        "scheduler_event_counts": event_counts,
        "warnings": {
            "manifest": manifest.get("warnings", []),
            "analysis": scheduler_analysis.get("warnings", []),
        },
        "metric_definitions": {
            "percentiles": "nearest-rank; rank = ceil(p * sample_count), one-based",
            "response_latency": "completion minus intended release; Python monotonic nanoseconds",
            "runnable_wait": "bpftrace timestamp difference; complete episodes only; grouped by task TID",
            "cpu_service": "sum of observed sched_switch intervals in bpftrace nanoseconds",
            "batch_throughput": "completed units divided by batch elapsed monotonic seconds",
            "clock_domains_subtracted": False,
        },
    }
