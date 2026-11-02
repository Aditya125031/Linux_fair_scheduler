"""Run one bounded mixed-workload smoke experiment on Linux."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cpu_fairness.analysis.reconstruction import reconstruct, to_records
from cpu_fairness.config import ConfigError, load_config
from cpu_fairness.preflight import collect_preflight
from cpu_fairness.system_info import collect_system_info
from cpu_fairness.telemetry.collector import BpftraceCollector, CollectorError
from cpu_fairness.telemetry.parser import read_trace


class ExperimentError(RuntimeError):
    """Smoke experiment could not produce a valid trace-backed run."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _wait_ready(path: Path, process: subprocess.Popen[str], timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ExperimentError(f"invalid workload ready record {path}: {exc}") from exc
            return value
        if process.poll() is not None:
            raise ExperimentError(f"workload exited before ready (exit {process.returncode})")
        time.sleep(0.02)
    raise ExperimentError(f"timed out waiting for workload ready record: {path.name}")


def _process_identity(pid: int, ready: dict[str, Any], role: str) -> dict[str, Any]:
    task_dir = Path("/proc") / str(pid) / "task"
    try:
        tids = sorted(int(item.name) for item in task_dir.iterdir() if item.name.isdigit())
        status = (Path("/proc") / str(pid) / "status").read_text(encoding="utf-8")
    except OSError as exc:
        raise ExperimentError(f"cannot inspect workload process {pid}: {exc}") from exc
    tgid_line = next((line for line in status.splitlines() if line.startswith("Tgid:")), None)
    if tgid_line is None:
        raise ExperimentError(f"/proc/{pid}/status did not report TGID")
    tgid = int(tgid_line.split()[1])
    ready_tgid = int(ready.get("tgid", -1))
    ready_tid = int(ready.get("tid", -1))
    if tgid != pid or ready_tgid != tgid or tids != [ready_tid] or ready_tid != pid:
        raise ExperimentError(
            f"{role} identity mismatch or workload is not single-threaded: "
            f"runner_pid={pid}, proc_tgid={tgid}, tids={tids}, ready={ready}"
        )
    return {
        "role": role,
        "pid": pid,
        "tgid": tgid,
        "tids": tids,
        "nice_value": ready.get("nice_value"),
        "single_threaded_verified": len(tids) == 1,
        "identity_source": "/proc/<pid>/task and /proc/<pid>/status",
    }


def _terminate_child(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _stop_children(children: dict[str, subprocess.Popen[str]]) -> None:
    for process in children.values():
        _terminate_child(process)


def _open_child_log(path: Path):
    return path.open("x", encoding="utf-8", newline="")


def run_smoke(config_path: str | Path, output_root: str | Path = "results") -> dict[str, Any]:
    """Run a single baseline smoke experiment; only the collector uses sudo."""
    if not sys.platform.startswith("linux"):
        raise ExperimentError("smoke experiments are Linux-only; run this command inside the Ubuntu guest")
    if not hasattr(os, "geteuid") or os.geteuid() == 0:
        raise ExperimentError("do not run the project runner as root; only bpftrace is launched through sudo")

    config = load_config(config_path)
    if config["policy"]["type"] != "baseline":
        raise ConfigError("this first smoke runner supports only the baseline policy")
    if config["batch"]["workers"] != 1:
        raise ConfigError("the first smoke runner requires exactly one batch worker")
    if config["duration_seconds"] > 15:
        raise ConfigError("smoke duration is capped at 15 seconds to bound system-wide trace volume")

    preflight = collect_preflight()
    if not preflight.get("ready"):
        raise ExperimentError("Linux preflight failed; run 'cpu-fairness preflight --json' and fix reported checks")

    output_root_path = Path(output_root).expanduser().resolve()
    raw_root = output_root_path / "raw"
    processed_root = output_root_path / "processed"
    raw_root.mkdir(parents=True, exist_ok=True)
    processed_root.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", config["experiment_id"]).strip("._") or "smoke"
    run_id = f"{safe_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    raw_dir = raw_root / run_id
    processed_dir = processed_root / run_id
    if raw_dir.exists() or processed_dir.exists():
        raise ExperimentError(f"refusing to overwrite existing run directory {run_id}")
    raw_dir.mkdir()
    processed_dir.mkdir()

    manifest_path = raw_dir / "manifest.json"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "running",
        "started_utc": _utc_now(),
        "git_commit": _git_commit(),
        "environment": collect_system_info(raw_dir),
        "preflight": preflight,
        "configuration": config,
        "clock_domains": {
            "workload_and_collector_lifecycle": "Python time.monotonic_ns",
            "scheduler_events": "bpftrace nsecs",
            "cross_clock_subtraction": "not performed",
        },
        "processes": {},
        "collector": None,
        "exit_statuses": {},
        "warnings": [],
        "errors": [],
        "outputs": {
            "raw_trace": str(raw_dir / "scheduler.tsv"),
            "trace_stderr": str(raw_dir / "bpftrace.stderr.log"),
            "interactive_jsonl": str(raw_dir / "interactive.jsonl"),
            "batch_summary": str(raw_dir / "batch.json"),
            "processed_dir": str(processed_dir),
        },
    }
    _write_json(manifest_path, manifest)

    collector = BpftraceCollector(raw_dir / "scheduler.tsv", raw_dir / "bpftrace.stderr.log")
    children: dict[str, subprocess.Popen[str]] = {}
    child_logs: list[Any] = []
    collector_metadata: dict[str, Any] | None = None
    failure: str | None = None
    try:
        collector.start()
        duration = str(config["duration_seconds"])
        interactive_ready = raw_dir / "interactive.ready.json"
        interactive_log = raw_dir / "interactive.jsonl"
        interactive_stdout = _open_child_log(raw_dir / "interactive.stdout.log")
        child_logs.append(interactive_stdout)
        interactive = subprocess.Popen(
            [
                sys.executable, "-m", "cpu_fairness.workloads.interactive",
                "--duration", duration,
                "--arrival-interval-ms", str(config["interactive"]["arrival_interval_ms"]),
                "--burst-iterations", str(config["interactive"]["burst_iterations"]),
                "--output", str(interactive_log),
                "--ready-file", str(interactive_ready),
            ],
            stdout=interactive_stdout,
            stderr=subprocess.STDOUT,
            text=True,
        )
        children["interactive"] = interactive
        interactive_identity = _process_identity(
            interactive.pid, _wait_ready(interactive_ready, interactive), "interactive"
        )

        batch_ready = raw_dir / "batch.ready.json"
        batch_summary = raw_dir / "batch.json"
        batch_stdout = _open_child_log(raw_dir / "batch.stdout.log")
        child_logs.append(batch_stdout)
        batch = subprocess.Popen(
            [
                sys.executable, "-m", "cpu_fairness.workloads.batch_worker",
                "--duration", duration,
                "--unit-iterations", str(config["batch"]["unit_iterations"]),
                "--worker-id", "batch-1",
                "--output", str(batch_summary),
                "--ready-file", str(batch_ready),
            ],
            stdout=batch_stdout,
            stderr=subprocess.STDOUT,
            text=True,
        )
        children["batch"] = batch
        batch_identity = _process_identity(batch.pid, _wait_ready(batch_ready, batch), "batch")
        manifest["processes"] = {
            "interactive": interactive_identity,
            "batch": batch_identity,
            "identity_semantics": "scheduler tracepoint pid is a task ID/TID; for verified single-thread workloads TID equals TGID/process PID",
        }
        _write_json(manifest_path, manifest)

        deadline = time.monotonic() + float(config["duration_seconds"]) + 15.0
        for role, process in children.items():
            manifest["exit_statuses"][role] = process.wait(timeout=max(0.1, deadline - time.monotonic()))
            if manifest["exit_statuses"][role] != 0:
                raise ExperimentError(f"{role} workload exited with {manifest['exit_statuses'][role]}")
    except (OSError, subprocess.SubprocessError, ExperimentError, CollectorError, KeyboardInterrupt) as exc:
        failure = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, KeyboardInterrupt):
            failure = "KeyboardInterrupt: user interrupted the smoke run"
    finally:
        _stop_children(children)
        for role, process in children.items():
            manifest["exit_statuses"].setdefault(role, process.poll())
        for handle in child_logs:
            if not handle.closed:
                handle.close()
        try:
            collector_metadata = collector.stop()
        except (OSError, subprocess.SubprocessError) as exc:
            failure = failure or f"collector shutdown failed: {exc}"

    manifest["collector"] = collector_metadata
    if collector_metadata and collector_metadata.get("returncode") not in {0, 130, -signal.SIGINT}:
        failure = failure or f"bpftrace exited with status {collector_metadata.get('returncode')}"
    if collector_metadata:
        stderr_path = raw_dir / "bpftrace.stderr.log"
        stderr_text = (
            stderr_path.read_text(encoding="utf-8", errors="replace")
            if stderr_path.exists()
            else ""
        )
        if re.search(r"lost|drop|warning|overrun", stderr_text, flags=re.IGNORECASE):
            manifest["warnings"].append("bpftrace stderr contains a loss/drop/warning indicator; inspect the preserved stderr log")
            collector_metadata["possible_event_loss_or_warning"] = True
        else:
            collector_metadata["possible_event_loss_or_warning"] = False
    manifest["finished_utc"] = _utc_now()
    if failure is None:
        try:
            events, trace_end_ns = read_trace(raw_dir / "scheduler.tsv")
            target_tids = {
                manifest["processes"][role]["tids"][0] for role in ("interactive", "batch")
            }
            waits, tasks, warnings = reconstruct(events, target_tids, trace_end_ns)
            if trace_end_ns is None:
                raise ExperimentError("trace is missing its bpftrace END timestamp")
            complete_waits = [episode for episode in waits if episode.complete]
            if not complete_waits:
                raise ExperimentError("trace contained no complete target-task runnable wait episode")

            wait_path = processed_dir / "wait_episodes.jsonl"
            with wait_path.open("x", encoding="utf-8") as output:
                for row in to_records(waits):
                    output.write(json.dumps(row, sort_keys=True) + "\n")
            _write_json(processed_dir / "task_accounting.json", to_records(tasks.values()))
            target_events = [
                event for event in events
                if event.tid in target_tids or event.prev_tid in target_tids or event.next_tid in target_tids
            ]
            event_counts = {
                "all_trace_records": len(events),
                "target_task_records": len(target_events),
                "target_wakeup_records": sum(event.event == "WAKEUP" and event.tid in target_tids for event in events),
                "target_switch_records": sum(event.event == "SWITCH" and (event.prev_tid in target_tids or event.next_tid in target_tids) for event in events),
                "complete_wait_episodes": len(complete_waits),
                "censored_wait_episodes": sum(not episode.complete for episode in waits),
            }
            analysis = {
                "data_kind": "measured_trace_analysis",
                "trace_end_timestamp_ns": trace_end_ns,
                "trace_clock_domain": "bpftrace nsecs",
                "trace_end_timestamp_note": "END uses the most recent nominal 10 ms interval heartbeat; scheduling or tracing delays can make the right-censor endpoint older than one interval.",
                "target_tids": sorted(target_tids),
                "event_counts": event_counts,
                "warnings": warnings,
                "cpu_service_note": "Observed sched_switch intervals only; incomplete intervals are identified in task_accounting.json.",
            }
            _write_json(processed_dir / "analysis.json", analysis)
            manifest["event_counts"] = event_counts
            manifest["warnings"].extend(warnings)
            manifest["outputs"].update(
                {
                    "wait_episodes": str(wait_path),
                    "task_accounting": str(processed_dir / "task_accounting.json"),
                    "analysis": str(processed_dir / "analysis.json"),
                }
            )
            manifest["status"] = "completed"
        except (OSError, ValueError, ExperimentError) as exc:
            failure = f"analysis failed: {type(exc).__name__}: {exc}"
    if failure:
        manifest["status"] = "failed"
        manifest["errors"].append(failure)
    _write_json(manifest_path, manifest)
    return manifest
