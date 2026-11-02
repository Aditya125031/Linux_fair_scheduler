"""Read-only Linux capability checks for the Ubuntu experiment guest."""

from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "sched_wakeup": {"pid", "prio", "target_cpu"},
    "sched_switch": {
        "prev_pid", "prev_prio", "prev_state", "next_pid", "next_prio"
    },
}


def tracepoint_fields(format_path: str | Path) -> set[str]:
    """Parse field names from one kernel tracepoint ``format`` file."""
    fields: set[str] = set()
    for line in Path(format_path).read_text(encoding="utf-8", errors="replace").splitlines():
        declaration = line.partition(";")[0]
        match = re.match(
            r"\s*field:\s*.*\s([A-Za-z_]\w*)(?:\[[^\]]*\])?\s*$",
            declaration,
        )
        if match:
            fields.add(match.group(1))
    return fields


def _tracefs_root() -> Path | None:
    for root in (Path("/sys/kernel/tracing"), Path("/sys/kernel/debug/tracing")):
        if (root / "events" / "sched").is_dir():
            return root
    return None


def _read_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return values
    for line in lines:
        key, separator, value = line.partition("=")
        if separator and key in {"ID", "VERSION_ID", "PRETTY_NAME"}:
            try:
                parsed = shlex.split(value)
                if parsed:
                    values[key] = parsed[0]
            except ValueError:
                values[key] = value.strip('"\'')
    return values


def _run_version(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "detail": str(exc)}
    output = (completed.stdout or completed.stderr).strip()
    return {"ok": completed.returncode == 0, "detail": output, "returncode": completed.returncode}


def collect_preflight() -> dict[str, Any]:
    """Collect checks without changing kernel, scheduler, or cgroup settings."""
    result: dict[str, Any] = {
        "platform": sys.platform,
        "kernel_version": platform.release(),
        "python_version": platform.python_version(),
        "os_release": {},
        "checks": {},
    }
    checks: dict[str, Any] = result["checks"]
    is_linux = sys.platform.startswith("linux")
    checks["linux_platform"] = {"ok": is_linux, "detail": platform.platform()}
    if not is_linux:
        result["ready"] = False
        return result

    result["os_release"] = _read_os_release()

    checks["python_version"] = {
        "ok": sys.version_info >= (3, 11),
        "detail": platform.python_version(),
    }
    checks["runner_unprivileged"] = {
        "ok": hasattr(os, "geteuid") and os.geteuid() != 0,
        "detail": f"effective UID {os.geteuid()}" if hasattr(os, "geteuid") else "effective UID unavailable",
    }
    checks["kernel_version"] = {
        "ok": bool(platform.release()),
        "detail": platform.release(),
    }
    bpftrace_path = shutil.which("bpftrace")
    checks["bpftrace_available"] = {
        "ok": bpftrace_path is not None,
        "detail": bpftrace_path or "bpftrace not found on PATH",
    }
    if bpftrace_path:
        checks["bpftrace_version"] = _run_version([bpftrace_path, "--version"])

    tracefs = _tracefs_root()
    checks["tracefs"] = {
        "ok": tracefs is not None,
        "detail": str(tracefs) if tracefs else "scheduler tracefs events not found",
    }
    tracepoint_results: dict[str, Any] = {}
    if tracefs:
        for event_name, required in REQUIRED_FIELDS.items():
            format_file = tracefs / "events" / "sched" / event_name / "format"
            try:
                actual = tracepoint_fields(format_file)
                missing = sorted(required - actual)
                tracepoint_results[event_name] = {
                    "available": True,
                    "format_file": str(format_file),
                    "fields": sorted(actual),
                    "required_fields": sorted(required),
                    "missing_fields": missing,
                    "ok": not missing,
                }
            except OSError as exc:
                tracepoint_results[event_name] = {
                    "available": False,
                    "format_file": str(format_file),
                    "detail": str(exc),
                    "ok": False,
                }
    else:
        tracepoint_results = {
            name: {"available": False, "ok": False, "detail": "tracefs unavailable"}
            for name in REQUIRED_FIELDS
        }
    checks["tracepoints"] = tracepoint_results

    btf = Path("/sys/kernel/btf/vmlinux")
    checks["btf"] = {"ok": btf.is_file(), "detail": str(btf)}
    cgroup2 = Path("/sys/fs/cgroup/cgroup.controllers")
    try:
        controllers = cgroup2.read_text(encoding="utf-8").strip() if cgroup2.is_file() else ""
    except OSError as exc:
        controllers = f"could not read controllers: {exc}"
    checks["cgroup_v2"] = {
        "ok": cgroup2.is_file(),
        "detail": f"{cgroup2}; controllers={controllers}",
    }

    sudo_path = shutil.which("sudo")
    sudo_check = (
        _run_version([sudo_path, "-n", "bpftrace", "--version"])
        if sudo_path and bpftrace_path
        else {"ok": False, "detail": "sudo or bpftrace not found"}
    )
    checks["sudo_bpftrace"] = sudo_check
    result["tracefs_root"] = str(tracefs) if tracefs else None
    result["ready"] = all(
        item.get("ok", False)
        for name, item in checks.items()
        if name not in {"tracepoints"}
    ) and all(item.get("ok", False) for item in tracepoint_results.values())
    return result


def format_preflight(result: dict[str, Any]) -> str:
    """Render a short human-readable report while retaining JSON via the CLI."""
    lines = [
        f"Platform: {result['platform']}",
        f"Kernel: {result['kernel_version']}",
        f"Python: {result['python_version']}",
    ]
    for name, check in result["checks"].items():
        if name == "tracepoints":
            for event_name, event_check in check.items():
                state = "PASS" if event_check.get("ok") else "FAIL"
                lines.append(f"{state} {event_name}: {event_check.get('detail', ', '.join(event_check.get('missing_fields', [])))}")
            continue
        state = "PASS" if check.get("ok") else "FAIL"
        lines.append(f"{state} {name}: {check.get('detail', '')}")
    lines.append(f"Overall: {'READY' if result.get('ready') else 'NOT READY'}")
    return "\n".join(lines)
