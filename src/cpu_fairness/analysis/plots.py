"""Optional plots for real repeated-run summaries."""

from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
from typing import Any


class PlotError(ValueError):
    """Plot input is invalid or the optional plotting dependency is missing."""


def comparison_plot_data(aggregate: dict[str, Any]) -> dict[str, Any]:
    if aggregate.get("data_kind") != "measured_repeated_run_summary":
        raise PlotError("plots require measured repeated-run summaries")
    policies = aggregate.get("policies")
    if not isinstance(policies, dict) or not policies:
        raise PlotError("aggregate input has no policy summaries")
    labels: list[str] = []
    response_p95_ms: list[float | None] = []
    throughput: list[float | None] = []
    delta_values: dict[str, list[float | None]] = {
        "ΔB→I": [],
        "ΔI→B": [],
        "Global Δ": [],
    }
    run_counts: list[int] = []
    for policy, summary in sorted(policies.items()):
        metrics = summary.get("metrics", {})
        labels.append(policy)
        response = metrics.get("interactive_response_p95_ns", {}).get("mean")
        response_p95_ms.append(response / 1_000_000 if response is not None else None)
        throughput.append(metrics.get("batch_throughput_units_per_second", {}).get("mean"))
        delta_values["ΔB→I"].append(metrics.get("delta_batch_to_interactive_mean", {}).get("mean"))
        delta_values["ΔI→B"].append(metrics.get("delta_interactive_to_batch_mean", {}).get("mean"))
        delta_values["Global Δ"].append(metrics.get("delta_global_mean", {}).get("mean"))
        run_counts.append(summary.get("run_count", 0))
    return {
        "labels": labels,
        "interactive_response_p95_ms": response_p95_ms,
        "batch_throughput_units_per_second": throughput,
        "delta": delta_values,
        "run_counts": run_counts,
    }


def save_comparison_plot(aggregate: dict[str, Any], output_path: str | Path) -> Path:
    """Save a compact measured-only comparison chart without overwriting files."""
    data = comparison_plot_data(aggregate)
    target = Path(output_path).expanduser()
    if target.suffix.lower() != ".png":
        raise PlotError("comparison plot output must use a .png extension")
    if not target.parent.is_dir():
        raise PlotError(f"output directory does not exist: {target.parent}")
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise PlotError("Matplotlib is optional; install the project analysis extra to create plots") from exc

    labels = [
        f"{policy}\n(n={aggregate['policies'][policy].get('run_count', 0)})"
        for policy in data["labels"]
    ]

    def means_and_errors(metric_name: str, scale: float = 1.0):
        means: list[float] = []
        lower: list[float] = []
        upper: list[float] = []
        for policy in data["labels"]:
            metric = aggregate["policies"][policy].get("metrics", {}).get(metric_name, {})
            mean = metric.get("mean")
            interval = metric.get("bootstrap_95_ci_for_mean", {})
            if mean is None:
                means.append(math.nan)
                lower.append(0.0)
                upper.append(0.0)
            else:
                means.append(mean * scale)
                ci_low, ci_high = interval.get("lower_95"), interval.get("upper_95")
                lower.append(max(0.0, (mean - ci_low) * scale) if ci_low is not None else 0.0)
                upper.append(max(0.0, (ci_high - mean) * scale) if ci_high is not None else 0.0)
        return means, (lower, upper)

    figure, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    try:
        response, response_error = means_and_errors("interactive_response_p95_ns", 1 / 1_000_000)
        axes[0].bar(labels, response, yerr=response_error, capsize=3, color="#4c78a8")
        axes[0].set_title("Interactive response p95")
        axes[0].set_ylabel("Milliseconds")

        throughput, throughput_error = means_and_errors("batch_throughput_units_per_second")
        axes[1].bar(labels, throughput, yerr=throughput_error, capsize=3, color="#f58518")
        axes[1].set_title("Batch throughput")
        axes[1].set_ylabel("Work units / second")

        delta_metrics = {
            "ΔB→I": "delta_batch_to_interactive_mean",
            "ΔI→B": "delta_interactive_to_batch_mean",
            "Global Δ": "delta_global_mean",
        }
        positions = list(range(len(labels)))
        width = 0.22
        for offset, (name, metric_name) in enumerate(delta_metrics.items()):
            values, errors = means_and_errors(metric_name)
            axes[2].bar(
                [position + (offset - 1) * width for position in positions],
                values,
                width=width,
                yerr=errors,
                capsize=2,
                label=name,
            )
        axes[2].set_xticks(positions, labels)
        axes[2].set_title("Measured Delta run means")
        axes[2].set_ylabel("Normalized deficit")
        axes[2].legend(fontsize="small")
        for axis in axes:
            axis.tick_params(axis="x", rotation=20)
            axis.grid(axis="y", alpha=0.25)
        figure.suptitle("Measured repeated-run means (bootstrap 95% CI where available)")
        figure.tight_layout()
        image = BytesIO()
        figure.savefig(image, format="png", dpi=160)
        with target.open("xb") as stream:
            stream.write(image.getvalue())
    finally:
        plt.close(figure)
    return target.resolve()
