"""Periodic CPU-burst workload with application-clock JSONL records."""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
from pathlib import Path
from typing import Any


_stop_requested = False


def _request_stop(_signum: int, _frame: Any) -> None:
    global _stop_requested
    _stop_requested = True


def _identity() -> dict[str, int | str | None]:
    tid = threading.get_native_id()
    try:
        nice: int | None = os.getpriority(os.PRIO_PROCESS, os.getpid())
    except (AttributeError, OSError):
        nice = None
    return {
        "tgid": os.getpid(), "tid": tid, "nice_value": nice,
        "identity_kind": "Linux task ID (TID)",
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def run_interactive(
    duration_seconds: float,
    arrival_interval_ms: float,
    burst_iterations: int,
    output_path: str | Path,
    ready_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run periodic deterministic bursts and return structured run metadata."""
    global _stop_requested
    _stop_requested = False
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    identity = _identity()
    log_path = Path(output_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ready = Path(ready_path) if ready_path is not None else None
    if ready:
        _write_json(ready, identity)

    start_ns = time.monotonic_ns()
    stop_ns = start_ns + int(duration_seconds * 1_000_000_000)
    interval_ns = int(arrival_interval_ms * 1_000_000)
    records: list[dict[str, Any]] = []
    request_id = 0
    while not _stop_requested:
        intended_release_ns = start_ns + request_id * interval_ns
        if intended_release_ns >= stop_ns:
            break
        remaining_ns = intended_release_ns - time.monotonic_ns()
        if remaining_ns > 0:
            time.sleep(remaining_ns / 1_000_000_000)
        if _stop_requested:
            break

        execution_start_ns = time.monotonic_ns()
        checksum = 0
        for value in range(burst_iterations):
            checksum = (checksum + value * value) & 0xFFFFFFFF
        completion_ns = time.monotonic_ns()
        request_id += 1
        records.append(
            {
                "request_id": request_id,
                "intended_release_monotonic_ns": intended_release_ns,
                "execution_start_monotonic_ns": execution_start_ns,
                "completion_monotonic_ns": completion_ns,
                "response_latency_ns": completion_ns - intended_release_ns,
                "burst_iterations": burst_iterations,
                "arrival_interval_ms": arrival_interval_ms,
                "duration_seconds": duration_seconds,
                "checksum": checksum,
                "clock_domain": "python_time.monotonic_ns",
                **identity,
            }
        )

    with log_path.open("w", encoding="utf-8", newline="") as output:
        for record in records:
            output.write(json.dumps(record, sort_keys=True) + "\n")
    summary = {
        **identity,
        "requests_completed": len(records),
        "duration_requested_seconds": duration_seconds,
        "arrival_interval_ms": arrival_interval_ms,
        "burst_iterations": burst_iterations,
        "completion_status": "stopped" if _stop_requested else "completed",
        "log_path": str(log_path),
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--arrival-interval-ms", type=float, required=True)
    parser.add_argument("--burst-iterations", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ready-file", required=True)
    args = parser.parse_args(argv)
    if args.duration <= 0 or args.arrival_interval_ms <= 0 or args.burst_iterations <= 0:
        parser.error("duration, arrival interval, and burst iterations must be positive")
    summary = run_interactive(
        args.duration,
        args.arrival_interval_ms,
        args.burst_iterations,
        args.output,
        args.ready_file,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
