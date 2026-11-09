"""Repeated-run summaries with deterministic bootstrap intervals."""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path
from typing import Any

from cpu_fairness.analysis.metrics import AnalysisError, analyze_run


class AggregationError(ValueError):
    """Runs cannot be compared under the requested aggregation contract."""


def _manifest_configuration(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AggregationError(f"cannot read run manifest at {manifest_path}: {exc}") from exc
    configuration = manifest.get("configuration") if isinstance(manifest, dict) else None
    if not isinstance(configuration, dict):
        raise AggregationError(f"run manifest at {manifest_path} has no configuration")
    return configuration


def _workload_signature(configuration: dict[str, Any]) -> str:
    signature = dict(configuration)
    for ignored in ("schema_version", "experiment_id", "policy"):
        signature.pop(ignored, None)
    return json.dumps(signature, sort_keys=True, separators=(",", ":"))


def _bootstrap_mean_interval(
    values: list[float], samples: int, seed: int
) -> dict[str, float | int | None]:
    if len(values) < 2:
        return {"sample_count": len(values), "lower_95": None, "upper_95": None}
    generator = random.Random(seed)
    boot_means = sorted(
        sum(generator.choices(values, k=len(values))) / len(values)
        for _ in range(samples)
    )
    lower_index = max(0, int(0.025 * samples + 0.999999) - 1)
    upper_index = max(0, int(0.975 * samples + 0.999999) - 1)
    return {
        "sample_count": len(values),
        "lower_95": boot_means[lower_index],
        "upper_95": boot_means[min(upper_index, len(boot_means) - 1)],
    }


def _metric_summary(values: list[float], samples: int, seed: int) -> dict[str, Any]:
    if not values:
        return {
            "run_count": 0,
            "mean": None,
            "median": None,
            "bootstrap_95_ci_for_mean": _bootstrap_mean_interval([], samples, seed),
        }
    return {
        "run_count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "bootstrap_95_ci_for_mean": _bootstrap_mean_interval(values, samples, seed),
    }


def aggregate_runs(
    run_directories: list[str | Path], bootstrap_samples: int = 2000, seed: int = 42
) -> dict[str, Any]:
    """Aggregate run-level summaries without modifying source run directories."""
    if not run_directories:
        raise AggregationError("provide at least one completed run directory")
    if isinstance(bootstrap_samples, bool) or not isinstance(bootstrap_samples, int) or bootstrap_samples < 100:
        raise AggregationError("bootstrap_samples must be an integer of at least 100")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise AggregationError("seed must be an integer")

    analyses: list[dict[str, Any]] = []
    signatures: set[str] = set()
    seen_run_ids: set[str] = set()
    policy_signatures: dict[str, str] = {}
    for directory in run_directories:
        path = Path(directory).expanduser().resolve()
        try:
            analysis = analyze_run(path)
        except AnalysisError as exc:
            raise AggregationError(f"cannot aggregate {path.name}: {exc}") from exc
        run_id = analysis.get("run_id", path.name)
        if run_id in seen_run_ids:
            raise AggregationError(f"duplicate run ID {run_id!r}")
        seen_run_ids.add(run_id)
        configuration = _manifest_configuration(path / "manifest.json")
        signatures.add(_workload_signature(configuration))
        policy_config = configuration.get("policy")
        policy_type = analysis.get("policy")
        if not isinstance(policy_config, dict) or policy_config.get("type") != policy_type:
            raise AggregationError(f"run {run_id!r} has inconsistent policy metadata")
        policy_signature = json.dumps(policy_config, sort_keys=True, separators=(",", ":"))
        prior_signature = policy_signatures.setdefault(policy_type, policy_signature)
        if prior_signature != policy_signature:
            raise AggregationError(f"runs for policy {policy_type!r} use different policy settings")
        analyses.append(analysis)
    if len(signatures) != 1:
        raise AggregationError("runs have different workload configurations; aggregate matching pilots separately")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for analysis in analyses:
        policy = analysis.get("policy")
        if not isinstance(policy, str) or not policy:
            raise AggregationError(f"run {analysis.get('run_id')} has no policy label")
        grouped.setdefault(policy, []).append(analysis)

    metric_getters = {
        "interactive_response_p50_ns": lambda run: run["interactive"]["approx_response_time"]["p50_ns"],
        "interactive_response_p95_ns": lambda run: run["interactive"]["approx_response_time"]["p95_ns"],
        "interactive_turnaround_p95_ns": lambda run: run["interactive"]["turnaround_time"]["p95_ns"],
        "batch_throughput_units_per_second": lambda run: run["batch"]["throughput_units_per_second"],
        "delta_global_mean": lambda run: run["delta_fairness"]["global_delta"]["mean"],
        "delta_batch_to_interactive_mean": lambda run: run["delta_fairness"]["delta_batch_to_interactive"]["mean"],
        "delta_interactive_to_batch_mean": lambda run: run["delta_fairness"]["delta_interactive_to_batch"]["mean"],
    }
    policies: dict[str, Any] = {}
    for policy, runs in sorted(grouped.items()):
        metric_summaries: dict[str, Any] = {}
        for metric, getter in metric_getters.items():
            values: list[float] = []
            for run in runs:
                try:
                    value = getter(run)
                except (KeyError, TypeError):
                    value = None
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    values.append(float(value))
            metric_summaries[metric] = _metric_summary(values, bootstrap_samples, seed)
        policies[policy] = {
            "run_count": len(runs),
            "run_ids": [run["run_id"] for run in runs],
            "metrics": metric_summaries,
        }
    return {
        "data_kind": "measured_repeated_run_summary",
        "run_count": len(analyses),
        "workload_configuration_signature": next(iter(signatures)),
        "bootstrap": {
            "method": "percentile bootstrap over independent run-level metric values",
            "samples": bootstrap_samples,
            "seed": seed,
            "confidence_level": 0.95,
        },
        "comparisons": "descriptive only; no statistical significance claim or paired-run inference",
        "policies": policies,
    }
