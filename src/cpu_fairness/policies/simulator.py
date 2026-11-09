"""Bounded wait-aware policy simulator over measured scheduler windows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SimulationError(ValueError):
    """Measured input or simulator settings do not satisfy the contract."""


DEFAULT_CONFIG: dict[str, int] = {
    "schema_version": 1,
    "interactive_wait_threshold_ns": 1_000_000,
    "batch_aging_wait_threshold_ns": 10_000_000,
    "boost_step": 1,
    "aging_step": 1,
    "maximum_boost_level": 3,
    "maximum_aging_level": 3,
    "cooldown_windows": 2,
}


def validate_simulator_config(config: Any) -> dict[str, int]:
    if not isinstance(config, dict):
        raise SimulationError("simulator configuration must be a JSON object")
    unknown = set(config) - set(DEFAULT_CONFIG)
    if unknown:
        raise SimulationError(f"unknown simulator configuration keys: {sorted(unknown)}")
    validated: dict[str, int] = {}
    for key, default in DEFAULT_CONFIG.items():
        value = config.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise SimulationError(f"{key} must be an integer")
        if key == "schema_version":
            if value != 1:
                raise SimulationError("schema_version must be 1")
        elif value < 0 or (key not in {"cooldown_windows"} and value == 0):
            raise SimulationError(f"{key} must be positive")
        validated[key] = value
    return validated


def load_simulator_config(path: str | Path) -> dict[str, int]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SimulationError(f"cannot read simulator configuration at {path}: {exc}") from exc
    return validate_simulator_config(value)


def simulate_wait_aware(
    measured_run: dict[str, Any], config: Any = None
) -> dict[str, Any]:
    """Produce bounded hypothetical boost decisions; never predicts outcomes."""
    if measured_run.get("data_kind") != "measured_run_metrics":
        raise SimulationError("simulator input must be measured run metrics")
    delta = measured_run.get("delta_fairness")
    if not isinstance(delta, dict) or delta.get("status") != "available":
        reason = delta.get("reason", "Delta windows are unavailable") if isinstance(delta, dict) else "Delta windows are unavailable"
        raise SimulationError(f"cannot simulate without measured scheduler windows: {reason}")
    windows = delta.get("windows")
    if not isinstance(windows, list) or not windows:
        raise SimulationError("measured input has no per-window records; request detailed Delta windows")
    settings = validate_simulator_config(config or {})

    task_state: dict[int, dict[str, int]] = {}
    decisions: list[dict[str, Any]] = []
    for window in windows:
        start_ns, end_ns = window.get("start_ns"), window.get("end_ns")
        rows = window.get("tasks")
        if (
            isinstance(start_ns, bool) or not isinstance(start_ns, int)
            or isinstance(end_ns, bool) or not isinstance(end_ns, int)
            or end_ns <= start_ns or not isinstance(rows, list)
        ):
            raise SimulationError("measured window has invalid boundaries or task records")
        for task in rows:
            tid = task.get("tid")
            workload_class = task.get("workload_class")
            wait_ns = task.get("runnable_wait_ns")
            if isinstance(tid, bool) or not isinstance(tid, int) or tid <= 0:
                raise SimulationError("measured task has an invalid TID")
            if workload_class not in {"interactive", "batch"}:
                raise SimulationError(f"TID {tid} has an unsupported workload class")
            if isinstance(wait_ns, bool) or not isinstance(wait_ns, int) or wait_ns < 0:
                raise SimulationError(f"TID {tid} has an invalid runnable-wait value")
            state = task_state.setdefault(
                tid,
                {"boost_level": 0, "aging_level": 0, "cooldown_remaining": 0},
            )
            reason = "wait_below_threshold"
            action = "hold"
            if workload_class == "interactive":
                if wait_ns >= settings["interactive_wait_threshold_ns"]:
                    if state["cooldown_remaining"] == 0:
                        state["boost_level"] = min(
                            settings["maximum_boost_level"],
                            state["boost_level"] + settings["boost_step"],
                        )
                        state["cooldown_remaining"] = settings["cooldown_windows"]
                        action = "request_bounded_boost"
                        reason = "interactive_wait_threshold_exceeded"
                    else:
                        action = "cooldown_hold"
                        reason = "anti_oscillation_cooldown"
                else:
                    state["boost_level"] = max(0, state["boost_level"] - settings["boost_step"])
            else:
                if wait_ns >= settings["batch_aging_wait_threshold_ns"]:
                    state["aging_level"] = min(
                        settings["maximum_aging_level"],
                        state["aging_level"] + settings["aging_step"],
                    )
                    action = "request_aging_credit"
                    reason = "batch_wait_aging_threshold_exceeded"
                else:
                    state["aging_level"] = max(0, state["aging_level"] - settings["aging_step"])
            combined_level = min(
                settings["maximum_boost_level"],
                state["boost_level"] + state["aging_level"],
            )
            decisions.append(
                {
                    "window_start_ns": start_ns,
                    "window_end_ns": end_ns,
                    "tid": tid,
                    "workload_class": workload_class,
                    "measured_runnable_wait_ns": wait_ns,
                    "action": action,
                    "reason": reason,
                    "simulated_boost_level": combined_level,
                    "cooldown_remaining_windows": state["cooldown_remaining"],
                }
            )
            if workload_class == "interactive" and state["cooldown_remaining"] > 0 and action != "request_bounded_boost":
                state["cooldown_remaining"] -= 1

    return {
        "data_kind": "simulated_policy_decisions",
        "source_data_kind": measured_run["data_kind"],
        "source_run_id": measured_run.get("run_id"),
        "policy": "bounded_wait_aware_simulator",
        "config": settings,
        "decision_count": len(decisions),
        "hypothetical_outcomes_generated": False,
        "live_scheduler_modified": False,
        "decisions": decisions,
    }
