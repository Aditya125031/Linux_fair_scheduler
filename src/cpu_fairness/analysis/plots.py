"""Dependency-free SVG plots for measured repeated-run summaries."""

from __future__ import annotations

from html import escape
import json
import math
from pathlib import Path
from typing import Any

from cpu_fairness.analysis.aggregation import _policy_label
from cpu_fairness.analysis.metrics import AnalysisError, analyze_run


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
        "interactive_response_p99_ns": [],
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

    width, height = 1320, 1135
    panels = [
        ("interactive_response_p95_ns", "Interactive approximate response p95", "milliseconds", 1e-6, "#4c78a8"),
        ("interactive_response_p99_ns", "Interactive approximate response p99", "milliseconds", 1e-6, "#a0cbe8"),
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
        '<text x="660" y="1109" font-size="11" text-anchor="middle" fill="#334155">Wait-aware is an offline simulator: no measured response, throughput, or Delta outcome exists, so its bars are intentionally marked not measured.</text>',
        '</svg>',
    ])
    with target.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(svg) + "\n")
    return target.resolve()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as exc:
        raise PlotError(f"cannot read graph input {path}: {exc}") from exc


def _output_path(prefix: Path, suffix: str) -> Path:
    return prefix.with_name(f"{prefix.name}.{suffix}.svg")


def _write_cdf(
    path: Path,
    title: str,
    x_label: str,
    series: list[tuple[str, list[float], str]],
    log_x: bool = False,
) -> None:
    width, height = 900, 540
    left, right, top, bottom = 80, 820, 65, 420
    flattened = [value for _, values, _ in series for value in values if math.isfinite(value) and value >= 0]
    if log_x:
        transform = lambda value: math.log10(max(value, 1e-3))
    else:
        transform = lambda value: value
    low = min((transform(value) for value in flattened), default=0.0)
    high = max((transform(value) for value in flattened), default=1.0)
    if high <= low:
        high = low + 1.0
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="450" y="30" text-anchor="middle" font-size="20" font-weight="700" fill="#0f172a">{escape(title)}</text>',
    ]
    for tick in range(6):
        fraction = tick / 5
        yy = bottom - fraction * (bottom - top)
        elements.extend([
            f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#e2e8f0"/>',
            f'<text x="{left-9}" y="{yy+4:.1f}" text-anchor="end" font-size="10" fill="#475569">{fraction:.1f}</text>',
        ])
    for name, samples, color in series:
        ordered = sorted(value for value in samples if math.isfinite(value) and value >= 0)
        if not ordered:
            continue
        points = [f'{left},{bottom}']
        for index, value in enumerate(ordered, start=1):
            xx = left + (transform(value) - low) / (high - low) * (right - left)
            yy = bottom - index / len(ordered) * (bottom - top)
            points.append(f'{xx:.1f},{yy:.1f}')
        dash = ' stroke-dasharray="5 3"' if " / batch" in name or " / I→B" in name else ""
        elements.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"{dash}/>')
    for tick in range(6):
        fraction = tick / 5
        value = low + fraction * (high - low)
        label = f"10^{value:.0f}" if log_x else f"{value:.3g}"
        xx = left + fraction * (right - left)
        elements.extend([
            f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{bottom}" stroke="#f1f5f9"/>',
            f'<text x="{xx:.1f}" y="{bottom+18}" text-anchor="middle" font-size="10" fill="#475569">{label}</text>',
        ])
    if not flattened:
        elements.append('<text x="450" y="245" text-anchor="middle" font-size="16" fill="#64748b">No eligible samples in the supplied runs</text>')
    elements.extend([
        f'<text x="450" y="442" text-anchor="middle" font-size="12" fill="#334155">{escape(x_label)}{" (log scale)" if log_x else ""}</text>',
        '<text x="22" y="242" transform="rotate(-90 22 242)" text-anchor="middle" font-size="12" fill="#334155">Empirical cumulative probability</text>',
    ])
    legend_y = 466
    for index, (name, _, color) in enumerate(series):
        col, row = index % 3, index // 3
        xx, yy = 85 + col * 270, legend_y + row * 23
        elements.extend([
            f'<line x1="{xx}" y1="{yy}" x2="{xx+24}" y2="{yy}" stroke="{color}" stroke-width="3"/>',
            f'<text x="{xx+30}" y="{yy+4}" font-size="10" fill="#334155">{escape(name)}</text>',
        ])
    elements.append('</svg>')
    with path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(elements) + "\n")


def _collect_diagnostic_data(run_directories: list[str | Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    palette = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#b279a2", "#72b7b2"]
    labels = sorted({
        _policy_label(json.loads((Path(directory).expanduser() / "manifest.json").read_text(encoding="utf-8"))["configuration"]["policy"])
        for directory in run_directories
    })
    colors = {label: palette[index % len(palette)] for index, label in enumerate(labels)}
    for directory in run_directories:
        run_path = Path(directory).expanduser().resolve()
        try:
            manifest = json.loads((run_path / "manifest.json").read_text(encoding="utf-8"))
            config = manifest["configuration"]
            label = _policy_label(config["policy"])
            processes = manifest["processes"]
            interactive_tid = processes["interactive"]["tids"][0]
            batch_tid = processes["batch"]["tids"][0]
            outputs = manifest.get("outputs", {})
            interactive_path = Path(outputs.get("interactive_jsonl", run_path / "interactive.jsonl"))
            batch_path = Path(outputs.get("batch_summary", run_path / "batch.json"))
            wait_path = Path(outputs.get("wait_episodes", run_path.parent.parent / "processed" / run_path.name / "wait_episodes.jsonl"))
            service_path = Path(outputs.get("task_accounting", run_path.parent.parent / "processed" / run_path.name / "task_accounting.json"))
            requests = _read_jsonl(interactive_path)
            response_ns = [
                row["execution_start_monotonic_ns"] - row["intended_release_monotonic_ns"]
                for row in requests
                if isinstance(row.get("execution_start_monotonic_ns"), int)
                and isinstance(row.get("intended_release_monotonic_ns"), int)
            ]
            waits = [row for row in _read_jsonl(wait_path) if row.get("complete") is True and isinstance(row.get("wait_ns"), int)]
            accounting = json.loads(service_path.read_text(encoding="utf-8"))
            service = {row["tid"]: row["cpu_service_ns"] for row in accounting if isinstance(row, dict)}
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            analysis = analyze_run(run_path, include_delta_windows=True)
            delta = analysis.get("delta_fairness", {})
            windows = delta.get("windows", []) if delta.get("status") == "available" else []
            records.append({
                "run_id": analysis["run_id"], "label": label, "color": colors[label],
                "response_ns": response_ns,
                "wait_interactive_ns": [row["wait_ns"] for row in waits if row.get("tid") == interactive_tid],
                "wait_batch_ns": [row["wait_ns"] for row in waits if row.get("tid") == batch_tid],
                "interactive_service_ns": service.get(interactive_tid),
                "batch_service_ns": service.get(batch_tid),
                "response_p95_ns": analysis["interactive"]["approx_response_time"]["p95_ns"],
                "throughput": batch["completed_units"] * 1_000_000_000 / batch["duration_monotonic_ns"],
                "delta_global": [row["global_delta"] for row in windows if row.get("global_delta") is not None],
                "delta_b2i": [row["delta_batch_to_interactive"] for row in windows if row.get("delta_batch_to_interactive") is not None],
                "delta_i2b": [row["delta_interactive_to_batch"] for row in windows if row.get("delta_interactive_to_batch") is not None],
            })
        except (OSError, KeyError, TypeError, json.JSONDecodeError, AnalysisError) as exc:
            raise PlotError(f"cannot collect graph data from {run_path}: {exc}") from exc
    return records


def _save_tradeoff_chart(path: Path, records: list[dict[str, Any]]) -> None:
    width, height = 900, 560
    left, right, top, bottom = 85, 850, 60, 455
    xs = [row["response_p95_ns"] / 1_000_000 for row in records if isinstance(row["response_p95_ns"], int)]
    ys = [row["throughput"] for row in records]
    if not xs or not ys:
        raise PlotError("response and throughput values are unavailable for trade-off chart")
    xmax, ymax = max(xs) * 1.1 or 1.0, max(ys) * 1.1 or 1.0
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="450" y="30" text-anchor="middle" font-size="20" font-weight="700">Per-run response / throughput trade-off</text>',
    ]
    for tick in range(6):
        f = tick / 5
        xx, yy = left + f * (right-left), bottom - f * (bottom-top)
        svg.extend([
            f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{bottom}" stroke="#e2e8f0"/>',
            f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#e2e8f0"/>',
            f'<text x="{xx:.1f}" y="{bottom+18}" text-anchor="middle" font-size="10">{xmax*f:.3g}</text>',
            f'<text x="{left-8}" y="{yy+4:.1f}" text-anchor="end" font-size="10">{ymax*f:.3g}</text>',
        ])
    for row in records:
        if not isinstance(row["response_p95_ns"], int):
            continue
        xx = left + (row["response_p95_ns"] / 1_000_000) / xmax * (right-left)
        yy = bottom - row["throughput"] / ymax * (bottom-top)
        svg.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="6" fill="{row["color"]}"/>')
        svg.append(f'<text x="{xx+7:.1f}" y="{yy-7:.1f}" font-size="8" fill="#334155">{escape(row["run_id"][-8:])}</text>')
    label_colors = {row["label"]: row["color"] for row in records}
    for index, (label, color) in enumerate(sorted(label_colors.items())):
        xx = left + index * 180
        svg.extend([
            f'<circle cx="{xx+5}" cy="500" r="5" fill="{color}"/>',
            f'<text x="{xx+15}" y="504" font-size="9" fill="#334155">{escape(label)}</text>',
        ])
    svg.extend([
        '<text x="465" y="530" text-anchor="middle" font-size="12">Approximate response p95 (milliseconds)</text>',
        '<text x="20" y="255" transform="rotate(-90 20 255)" text-anchor="middle" font-size="12">Batch throughput (units/second)</text>',
        '</svg>',
    ])
    with path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(svg) + "\n")


def save_diagnostic_plots(
    run_directories: list[str | Path], output_prefix: str | Path
) -> list[Path]:
    """Write request, wait, service, Delta-window, and trade-off SVG diagnostics."""
    if not run_directories:
        raise PlotError("provide completed run directories")
    prefix = Path(output_prefix).expanduser()
    if not prefix.parent.is_dir():
        raise PlotError(f"output directory does not exist: {prefix.parent}")
    records = _collect_diagnostic_data(run_directories)
    paths = {
        name: _output_path(prefix, name)
        for name in ("response-cdf", "runnable-wait-cdf", "cpu-service", "delta-windows-cdf", "latency-throughput")
    }
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(existing[0])
    labels = sorted({row["label"] for row in records})
    colors = {row["label"]: row["color"] for row in records}
    response_series = [
        (f"{label} (n={sum(len(row['response_ns']) for row in records if row['label'] == label)})", [value / 1_000_000 for row in records if row["label"] == label for value in row["response_ns"]], colors[label])
        for label in labels
    ]
    _write_cdf(paths["response-cdf"], "Interactive response-time distribution", "Approximate response time (milliseconds)", response_series, log_x=True)
    wait_series = []
    for label in labels:
        interactive_waits = [value / 1_000 for row in records if row["label"] == label for value in row["wait_interactive_ns"]]
        batch_waits = [value / 1_000 for row in records if row["label"] == label for value in row["wait_batch_ns"]]
        wait_series.append((f"{label} / interactive (n={len(interactive_waits)})", interactive_waits, colors[label]))
        wait_series.append((f"{label} / batch (n={len(batch_waits)})", batch_waits, colors[label]))
    wait_series = [series for series in wait_series if series[1]]
    _write_cdf(paths["runnable-wait-cdf"], "Runnable-wait distributions by workload class", "Complete runnable waits (microseconds)", wait_series, log_x=True)
    service_series = []
    for label in labels:
        for role, key in (("interactive", "interactive_service_ns"), ("batch", "batch_service_ns")):
            values = [row[key] / 1_000_000 for row in records if row["label"] == label and isinstance(row[key], int)]
            if values:
                service_series.append((f"{label} / {role} (n={len(values)})", values, colors[label]))
    _write_cdf(paths["cpu-service"], "Per-target-task CPU service across runs", "Observed scheduler service (milliseconds)", service_series)
    delta_series = []
    delta_keys = (("global", "delta_global"), ("B→I", "delta_b2i"), ("I→B", "delta_i2b"))
    for label in labels:
        for direction, key in delta_keys:
            values = [value for row in records if row["label"] == label for value in row[key]]
            if values:
                delta_series.append((f"{label} / {direction} (n={len(values)})", values, colors[label]))
    _write_cdf(paths["delta-windows-cdf"], "Delta distributions across eligible scheduler windows", "Normalized deficit per scheduler window", delta_series)
    _save_tradeoff_chart(paths["latency-throughput"], records)
    return [path.resolve() for path in paths.values()]
