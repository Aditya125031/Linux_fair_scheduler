"""Load and validate JSON experiment configurations."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a configuration file is invalid or unsupported."""


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ConfigError(f"non-finite JSON number is not allowed: {value}")


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a JSON object")
    return value


def _positive_number(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number greater than zero")
    if not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{name} must be a finite number greater than zero")


def _positive_integer(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{name} must be a positive integer")


def validate_config(data: Any) -> dict[str, Any]:
    """Validate the small, versioned configuration contract used by the CLI."""
    root = _require_object(data, "configuration")
    schema_version = root.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise ConfigError("schema_version must be 1")
    experiment_id = root.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ConfigError("experiment_id must be a non-empty string")
    _positive_number(root.get("duration_seconds"), "duration_seconds")

    interactive = _require_object(root.get("interactive"), "interactive")
    _positive_number(
        interactive.get("arrival_interval_ms"), "interactive.arrival_interval_ms"
    )
    _positive_integer(
        interactive.get("burst_iterations"), "interactive.burst_iterations"
    )

    batch = _require_object(root.get("batch"), "batch")
    _positive_integer(batch.get("workers"), "batch.workers")
    _positive_integer(batch.get("unit_iterations"), "batch.unit_iterations")

    policy = _require_object(root.get("policy"), "policy")
    policy_type = policy.get("type")
    if not isinstance(policy_type, str) or policy_type not in {"baseline", "fixed_nice"}:
        raise ConfigError("policy.type must be 'baseline' or 'fixed_nice'")
    if policy_type == "fixed_nice":
        nice = policy.get("batch_nice")
        if isinstance(nice, bool) or not isinstance(nice, int) or not 0 <= nice <= 19:
            raise ConfigError("policy.batch_nice must be an integer from 0 through 19")

    return root


def load_config(path: str | Path) -> dict[str, Any]:
    """Read and validate JSON from *path*, reporting useful user-facing errors."""
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            data = json.load(
                config_file,
                object_pairs_hook=_object_without_duplicate_keys,
                parse_constant=_reject_non_finite,
            )
    except OSError as exc:
        raise ConfigError(f"cannot read configuration {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"invalid JSON in {config_path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    return validate_config(data)
