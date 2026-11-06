"""Single-process, CPU-bound deterministic batch workload."""

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
    return {"tgid": os.getpid(), "tid": tid, "nice_value": nice}


def _set_nice_value(nice_value: int | None) -> None:
    """Set and verify an absolute nice value for this unprivileged worker."""
    if nice_value is None:
        return
    if (
        isinstance(nice_value, bool)
        or not isinstance(nice_value, int)
        or not 0 <= nice_value <= 19
    ):
        raise ValueError("nice_value must be an integer from 0 through 19")
    try:
        os.setpriority(os.PRIO_PROCESS, 0, nice_value)
        actual = os.getpriority(os.PRIO_PROCESS, 0)
    except (AttributeError, OSError) as exc:
        raise RuntimeError(f"could not set batch nice value to {nice_value}: {exc}") from exc
    if actual != nice_value:
        raise RuntimeError(
            f"batch nice value verification failed: requested {nice_value}, observed {actual}"
        )


def run_batch(
    duration_seconds: float,
    unit_iterations: int,
    worker_id: str,
    output_path: str | Path,
    ready_path: str | Path | None = None,
    nice_value: int | None = None,
) -> dict[str, Any]:
    """Run fixed-size CPU units until duration expires or a stop signal arrives."""
    global _stop_requested
    _stop_requested = False
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    _set_nice_value(nice_value)
    identity = _identity()
    log_path = Path(output_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if ready_path is not None:
        Path(ready_path).write_text(json.dumps(identity, sort_keys=True) + "\n", encoding="utf-8")

    start_ns = time.monotonic_ns()
    deadline_ns = start_ns + int(duration_seconds * 1_000_000_000)
    completed_units = 0
    checksum = 0
    while not _stop_requested and time.monotonic_ns() < deadline_ns:
        unit_result = 0
        for value in range(unit_iterations):
            unit_result = (unit_result + value * value) & 0xFFFFFFFF
        checksum ^= unit_result
        completed_units += 1
    end_ns = time.monotonic_ns()
    summary = {
        "worker_id": worker_id,
        **identity,
        "completed_units": completed_units,
        "unit_iterations": unit_iterations,
        "duration_seconds": (end_ns - start_ns) / 1_000_000_000,
        "duration_monotonic_ns": end_ns - start_ns,
        "checksum": checksum,
        "completion_status": "stopped" if _stop_requested else "completed",
        "clock_domain": "python_time.monotonic_ns",
    }
    log_path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--unit-iterations", type=int, required=True)
    parser.add_argument("--worker-id", default="batch-1")
    parser.add_argument("--output", required=True)
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--nice-value", type=int)
    args = parser.parse_args(argv)
    if args.duration <= 0 or args.unit_iterations <= 0:
        parser.error("duration and unit iterations must be positive")
    if args.nice_value is not None and not 0 <= args.nice_value <= 19:
        parser.error("nice value must be from 0 through 19")
    summary = run_batch(
        args.duration,
        args.unit_iterations,
        args.worker_id,
        args.output,
        args.ready_file,
        args.nice_value,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
