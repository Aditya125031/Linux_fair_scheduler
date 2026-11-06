"""Lifecycle wrapper for the narrowly privileged bpftrace child process."""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


class CollectorError(RuntimeError):
    """Collector startup or shutdown failed."""


class BpftraceCollector:
    _TRACE_EVENTS = {"WAKEUP", "SWITCH", "END"}

    def __init__(self, trace_path: str | Path, stderr_path: str | Path):
        self.trace_path = Path(trace_path)
        self.stderr_path = Path(stderr_path)
        self.process: subprocess.Popen[str] | None = None
        self._ready: queue.Queue[tuple[str, str | None]] = queue.Queue(maxsize=1)
        self._reader: threading.Thread | None = None
        self._trace_file: Any = None
        self._stderr_file: Any = None
        self._ready_seen = False
        self._event_lines = 0
        self.start_monotonic_ns: int | None = None
        self.end_monotonic_ns: int | None = None

    def start(self, timeout_seconds: float = 20.0) -> None:
        if not os.sys.platform.startswith("linux"):
            raise CollectorError("bpftrace collection is Linux-only; run this command in the Ubuntu guest")
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._trace_file = self.trace_path.open("x", encoding="utf-8", newline="")
        self._trace_file.write("\t".join((
            "timestamp_ns", "event", "tid", "prev_tid", "next_tid", "prev_state",
            "prio", "prev_prio", "next_prio", "cpu", "target_cpu",
        )) + "\n")
        self._trace_file.flush()
        self._stderr_file = self.stderr_path.open("x", encoding="utf-8", newline="")
        script_path = Path(__file__).with_name("scheduler.bt")
        command = ["sudo", "-n", "bpftrace", "-q", "-B", "line", str(script_path)]
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=self._stderr_file,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            self._close_files()
            raise CollectorError(f"could not start tracer: {exc}") from exc
        self.start_monotonic_ns = time.monotonic_ns()
        self._reader = threading.Thread(target=self._copy_stdout, name="bpftrace-output", daemon=True)
        self._reader.start()
        try:
            state, detail = self._ready.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            self.stop()
            raise CollectorError("timed out waiting for bpftrace READY marker; inspect bpftrace.stderr.log") from exc
        if state != "ready":
            self.stop()
            raise CollectorError(f"bpftrace did not start: {detail or 'process exited'}")

    def _copy_stdout(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            for line in self.process.stdout:
                if line.strip() == "READY":
                    if not self._ready_seen:
                        self._ready_seen = True
                        self._ready.put_nowait(("ready", None))
                    continue
                if not self._ready_seen:
                    if self._is_trace_record(line):
                        self._write_trace_line(line)
                        self._trace_file.flush()
                        continue
                    if not line.strip():
                        continue
                    self._ready.put_nowait(("error", line.strip()))
                    self._ready_seen = True
                    continue
                self._write_trace_line(line)
            self._trace_file.flush()
            if not self._ready_seen:
                self._ready.put_nowait(("error", f"bpftrace exited before READY (status {self.process.poll()})"))
        except (OSError, ValueError) as exc:
            if not self._ready_seen:
                try:
                    self._ready.put_nowait(("error", str(exc)))
                except queue.Full:
                    pass

    @classmethod
    def _is_trace_record(cls, line: str) -> bool:
        columns = line.rstrip("\r\n").split("\t")
        return (
            len(columns) == 11
            and columns[1] in cls._TRACE_EVENTS
            and columns[0].isdigit()
        )

    def _write_trace_line(self, line: str) -> None:
        self._trace_file.write(line)
        self._event_lines += 1
        if self._event_lines % 256 == 0:
            self._trace_file.flush()

    def stop(self, timeout_seconds: float = 5.0) -> dict[str, Any]:
        process = self.process
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if self._reader is not None:
            self._reader.join(timeout=2.0)
        self.end_monotonic_ns = time.monotonic_ns()
        returncode = process.poll() if process is not None else None
        self._close_files()
        return {
            "command": ["sudo", "-n", "bpftrace", "-q", "-B", "line", "scheduler.bt"],
            "returncode": returncode,
            "event_lines_written": self._event_lines,
            "start_python_monotonic_ns": self.start_monotonic_ns,
            "end_python_monotonic_ns": self.end_monotonic_ns,
            "python_clock_domain": "time.monotonic_ns",
            "trace_clock_domain": "bpftrace nsecs; not directly subtracted from Python timestamps",
        }

    def _close_files(self) -> None:
        if self.process is not None and self.process.stdout is not None:
            self.process.stdout.close()
        for handle_name in ("_trace_file", "_stderr_file"):
            handle = getattr(self, handle_name)
            if handle is not None and not handle.closed:
                handle.close()
