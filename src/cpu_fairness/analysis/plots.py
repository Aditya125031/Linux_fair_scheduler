"""Dependency-free SVG plots for measured repeated-run summaries."""

from __future__ import annotations

from html import escape
import math
from pathlib import Path
from typing import Any


class PlotError(ValueError):
    """Plot input is invalid."""


def comparison_plot_data(aggregate: dict[str, Any]) -> dict[str, Any]:
    if aggregate.get("data_kind") != "measured_repeated_run_summary":
        raise PlotError("plots require measured repeated-run summaries")
    policies = aggregate.get("policies")
    if not isinstance(policies, dict) or not policies:
        raise PlotError("aggregate input has no policy summaries")
    labels: list[str] = []
    metric_data: dict[str, list[dict[str, Any] | None]] = {
        "interactive_response_p95_ns": [],
        "interactive_turnaround_p95_ns": [],
        "batch_throughput_units_per_second": [],
        "delta_global_mean": [],
        "delta_batch_to_interactive_mean": [],
        "delta_interactive_to_batch_mean": [],
    }
    run_counts: list[int] = []
    for policy, summary in sorted(policies.items()):
        metrics = summary.get("metrics", {})
        labels.append(policy)
        run_counts.append(summary.get("run_count", 0))
        for name in metric_data:
            metric_data[name].append(metrics.get(name))
    # Wait-aware decisions are simulated; no measured performance outcome is available.
    labels.append("Wait-aware (simulator only)")
    run_counts.append(0)
    for values in metric_data.values():
        values.append(None)
    return {"labels": labels, "metrics": metric_data, "run_counts": run_counts}


def _svg_panel(
    x: int,
    y: int,
    width: int,
    height: int,
    title: str,
    unit: str,
    labels: list[str],
    run_counts: list[int],
    metrics: list[dict[str, Any] | None],
    color: str,
) -> list[str]:
    left, right, top, bottom = x + 52, x + width - 14, y + 34, y + height - 78
    plot_width, plot_height = right - left, bottom - top
    values: list[float] = []
    bounds: list[tuple[float, float] | None] = []
    for metric in metrics:
        mean = metric.get("mean") if isinstance(metric, dict) else None
        ci = metric.get("bootstrap_95_ci_for_mean", {}) if isinstance(metric, dict) else {}
        low, high = ci.get("lower_95"), ci.get("upper_95")
        if isinstance(mean, (int, float)) and math.isfinite(mean):
            values.append(float(mean))
            if isinstance(low, (int, float)) and isinstance(high, (int, float)):
                values.extend((float(low), float(high)))
                bounds.append((float(low), float(high)))
            else:
                bounds.append(None)
        else:
            bounds.append(None)
    maximum = max(values, default=1.0)
    maximum = max(maximum, 1e-12) * 1.15
    output = [
        f'<g><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="7" fill="#ffffff" stroke="#cbd5e1"/>',
        f'<text x="{x+14}" y="{y+23}" font-size="15" font-weight="700" fill="#172554">{escape(title)}</text>',
    ]
    for tick in range(4):
        fraction = tick / 3
        yy = bottom - fraction * plot_height
        value = maximum * fraction
        output.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#e2e8f0"/>')
        output.append(f'<text x="{left-5}" y="{yy+4:.1f}" font-size="9" text-anchor="end" fill="#475569">{value:.3g}</text>')
    n = max(1, len(labels))
    slot = plot_width / n
    bar_width = min(38, slot * 0.48)
    for index, (label, metric, interval) in enumerate(zip(labels, metrics, bounds)):
        center = left + slot * (index + 0.5)
        mean = metric.get("mean") if isinstance(metric, dict) else None
        if isinstance(mean, (int, float)) and math.isfinite(mean):
            bar_height = float(mean) / maximum * plot_height
            output.append(f'<rect x="{center-bar_width/2:.1f}" y="{bottom-bar_height:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}"/>')
            output.append(f'<text x="{center:.1f}" y="{max(top+10,bottom-bar_height-5):.1f}" font-size="9" text-anchor="middle" fill="#0f172a">{float(mean):.3g}</text>')
            if interval is not None:
                y_low = bottom - interval[0] / maximum * plot_height
                y_high = bottom - interval[1] / maximum * plot_height
                output.append(f'<line x1="{center:.1f}" y1="{y_high:.1f}" x2="{center:.1f}" y2="{y_low:.1f}" stroke="#0f172a" stroke-width="1.4"/>')
                output.append(f'<line x1="{center-5:.1f}" y1="{y_high:.1f}" x2="{center+5:.1f}" y2="{y_high:.1f}" stroke="#0f172a"/>')
                output.append(f'<line x1="{center-5:.1f}" y1="{y_low:.1f}" x2="{center+5:.1f}" y2="{y_low:.1f}" stroke="#0f172a"/>')
        else:
            output.append(f'<text x="{center:.1f}" y="{top+plot_height*0.52:.1f}" font-size="10" text-anchor="middle" fill="#64748b">not measured</text>')
        short_label = (
            label.replace("EEVDF baseline (kernel default)", "EEVDF")
            .replace("Fixed nice ", "nice ")
            .replace(" (simulator only)", " sim")
        )
        output.append(f'<text x="{center:.1f}" y="{bottom+18}" font-size="9" text-anchor="middle" fill="#334155">{escape(short_label)}</text>')
        output.append(f'<text x="{center:.1f}" y="{bottom+31}" font-size="8" text-anchor="middle" fill="#64748b">n={run_counts[index]} runs</text>')
    output.append(f'<text x="{x+12}" y="{y+height-8}" font-size="9" fill="#64748b">{escape(unit)}; bars show run-level mean, whiskers show bootstrap 95% interval when available</text>')
    output.append('</g>')
    return output


def save_comparison_plot(aggregate: dict[str, Any], output_path: str | Path) -> Path:
    """Write measured-run SVG charts without optional packages or overwrites."""
    data = comparison_plot_data(aggregate)
    target = Path(output_path).expanduser()
    if target.suffix.lower() != ".svg":
        raise PlotError("comparison plot output must use an .svg extension")
    if not target.parent.is_dir():
        raise PlotError(f"output directory does not exist: {target.parent}")

    width, height = 1320, 790
    panels = [
        ("interactive_response_p95_ns", "Interactive approximate response p95", "milliseconds", 1e-6, "#4c78a8"),
        ("interactive_turnaround_p95_ns", "Interactive turnaround p95", "milliseconds", 1e-6, "#72a0c1"),
        ("batch_throughput_units_per_second", "Batch throughput", "work units / second", 1.0, "#f58518"),
        ("delta_global_mean", "Global Delta", "normalized deficit", 1.0, "#54a24b"),
        ("delta_batch_to_interactive_mean", "Directional Delta B to I", "normalized deficit", 1.0, "#e45756"),
        ("delta_interactive_to_batch_mean", "Directional Delta I to B", "normalized deficit", 1.0, "#b279a2"),
    ]
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="660" y="31" font-size="22" text-anchor="middle" font-weight="700" fill="#0f172a">Measured scheduler policy comparison</text>',
        '<text x="660" y="51" font-size="11" text-anchor="middle" fill="#475569">EEVDF is the kernel-default baseline; each fixed-nice level is a separate measured group.</text>',
    ]
    chart_width, chart_height = 425, 330
    for index, (key, title, unit, scale, color) in enumerate(panels):
        col, row = index % 3, index // 3
        metrics = data["metrics"][key]
        if scale != 1.0:
            metrics = [
                ({**item, "mean": item["mean"] * scale,
                  "bootstrap_95_ci_for_mean": {
                      bound: value * scale if value is not None else None
                      for bound, value in item.get("bootstrap_95_ci_for_mean", {}).items()
                  }} if isinstance(item, dict) and item.get("mean") is not None else item)
                for item in metrics
            ]
        svg.extend(_svg_panel(
            15 + col * 435,
            68 + row * 342,
            chart_width,
            chart_height,
            title,
            unit,
            data["labels"],
            data["run_counts"],
            metrics,
            color,
        ))
    svg.extend([
        '<text x="660" y="766" font-size="11" text-anchor="middle" fill="#334155">Wait-aware is an offline simulator: no measured response, throughput, or Delta outcome exists, so its bars are intentionally marked not measured.</text>',
        '</svg>',
    ])
    with target.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(svg) + "\n")
    return target.resolve()
