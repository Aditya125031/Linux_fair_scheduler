"""Collect safe, read-only information about the current development host."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Any


def _memory_bytes() -> tuple[int | None, int | None]:
    """Return total and available memory when the current OS exposes it."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys), int(status.ullAvailPhys)
        except (AttributeError, OSError, TypeError):
            pass

    if hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_pages = os.sysconf("SC_PHYS_PAGES")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            return int(page_size * total_pages), int(page_size * available_pages)
        except (OSError, ValueError):
            pass
    return None, None


def _cgroup_cpu_quota() -> dict[str, Any]:
    """Read the current cgroup v2 CPU quota without changing system state."""
    try:
        membership = Path("/proc/self/cgroup").read_text(encoding="utf-8")
        cgroup_path = next(
            (line.split("::", 1)[1] for line in membership.splitlines() if "::" in line),
            None,
        )
        if cgroup_path is None:
            return {"status": "unknown", "reason": "cgroup v2 membership was not found"}
        cgroup_root = Path("/sys/fs/cgroup").resolve()
        cgroup_dir = (cgroup_root / cgroup_path.lstrip("/")).resolve()
        if cgroup_dir != cgroup_root and cgroup_root not in cgroup_dir.parents:
            return {"status": "unknown", "reason": "cgroup path is outside the cgroup v2 mount"}
        current = cgroup_dir
        while True:
            quota_text = (current / "cpu.max").read_text(encoding="ascii").split()
            if len(quota_text) != 2:
                return {"status": "unknown", "reason": "cpu.max has an unexpected format"}
            period_us = int(quota_text[1])
            if period_us <= 0:
                return {"status": "unknown", "reason": "cpu.max period is invalid"}
            if quota_text[0] != "max":
                quota_us = int(quota_text[0])
                if quota_us <= 0:
                    return {"status": "unknown", "reason": "cpu.max quota is invalid"}
                return {
                    "status": "limited",
                    "quota_us": quota_us,
                    "period_us": period_us,
                    "cpu_equivalents": quota_us / period_us,
                    "cgroup_path": str(current),
                }
            if current == cgroup_root:
                return {
                    "status": "unlimited",
                    "quota_us": None,
                    "period_us": period_us,
                    "checked_ancestors": True,
                }
            current = current.parent
    except (OSError, StopIteration, ValueError) as exc:
        return {"status": "unknown", "reason": f"cannot read cgroup v2 CPU quota: {exc}"}


def collect_system_info(output_dir: str | Path | None = None) -> dict[str, Any]:
    """Return host facts without probing Linux tracing features or changing state.

    ``output_dir`` is optional; when provided, its resolved path and available
    disk bytes are included if it already exists. The function does not create it.
    """
    memory_total, memory_available = _memory_bytes()
    cpu_affinity: list[int] | None = None
    if hasattr(os, "sched_getaffinity"):
        try:
            cpu_affinity = sorted(os.sched_getaffinity(0))
        except OSError:
            pass
    info: dict[str, Any] = {
        "platform": sys.platform,
        "os_name": os.name,
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "logical_cpu_count": os.cpu_count(),
        "cpu_affinity": cpu_affinity,
        "effective_cpu_count": len(cpu_affinity) if cpu_affinity is not None else os.cpu_count(),
        "cpu_quota": _cgroup_cpu_quota(),
        "memory_total_bytes": memory_total,
        "memory_available_bytes": memory_available,
        "is_linux": sys.platform.startswith("linux"),
        "is_windows": os.name == "nt",
    }
    if output_dir is not None:
        target = Path(output_dir).expanduser()
        info["output_dir"] = str(target.resolve())
        try:
            info["output_dir_exists"] = target.is_dir()
            info["output_disk_free_bytes"] = (
                shutil_disk_usage(target).free if target.is_dir() else None
            )
        except OSError:
            info["output_disk_free_bytes"] = None
    return info


def shutil_disk_usage(path: Path) -> Any:
    """Small wrapper kept local so callers can test system collection easily."""
    import shutil

    return shutil.disk_usage(path)
