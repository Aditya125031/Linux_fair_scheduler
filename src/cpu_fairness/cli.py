"""Configuration, preflight, and initial Linux smoke-test commands."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from cpu_fairness import __version__
from cpu_fairness.analysis.aggregation import AggregationError, aggregate_runs
from cpu_fairness.analysis.metrics import AnalysisError, analyze_run
from cpu_fairness.analysis.plots import PlotError, save_comparison_plot
from cpu_fairness.config import ConfigError, load_config
from cpu_fairness.experiment import ExperimentError, run_pilot, run_smoke
from cpu_fairness.preflight import collect_preflight, format_preflight
from cpu_fairness.policies.simulator import (
    SimulationError,
    load_simulator_config,
    simulate_wait_aware,
)
from cpu_fairness.system_info import collect_system_info


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cpu-fairness",
        description="Portable setup and configuration tools for the scheduler study.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser("info", help="show current host information")
    info_parser.add_argument("--output-dir", help="existing directory to report free space for")

    config_parser = subparsers.add_parser("validate-config", help="validate a JSON run configuration")
    config_parser.add_argument("path", help="path to the JSON configuration")

    preflight_parser = subparsers.add_parser("preflight", help="check Linux tracing prerequisites")
    preflight_parser.add_argument("--json", action="store_true", help="print machine-readable JSON")

    smoke_parser = subparsers.add_parser("smoke", help="run one short Linux mixed-workload experiment")
    smoke_parser.add_argument("--config", default="configs/quick.json")
    smoke_parser.add_argument("--output-root", default="results")

    pilot_parser = subparsers.add_parser(
        "run-pilot", help="run sequential baseline/fixed-nice repeats (maximum 5 pairs)"
    )
    pilot_parser.add_argument("--repeats", type=int, default=3)
    pilot_parser.add_argument("--output-root", default="results")
    pilot_parser.add_argument("--baseline-config", default="configs/quick.json")
    pilot_parser.add_argument("--fixed-nice-config", default="configs/fixed_nice_quick.json")

    analysis_parser = subparsers.add_parser(
        "analyze-run", help="summarize metrics from one completed run"
    )
    analysis_parser.add_argument("run_directory", help="path to results/raw/<run-id>")
    analysis_parser.add_argument(
        "--include-delta-windows",
        action="store_true",
        help="include detailed per-window Delta records in the JSON output",
    )

    aggregate_parser = subparsers.add_parser(
        "aggregate-runs", help="compare repeated runs with matching workload settings"
    )
    aggregate_parser.add_argument("run_directories", nargs="+", help="completed results/raw/<run-id> directories")
    aggregate_parser.add_argument("--bootstrap-samples", type=int, default=2000)
    aggregate_parser.add_argument("--seed", type=int, default=42)

    plot_parser = subparsers.add_parser(
        "plot-runs", help="plot measured summaries from matching repeated runs"
    )
    plot_parser.add_argument("run_directories", nargs="+", help="completed results/raw/<run-id> directories")
    plot_parser.add_argument("--output", default="results/figures/repeated_run_comparison.png")
    plot_parser.add_argument("--bootstrap-samples", type=int, default=2000)
    plot_parser.add_argument("--seed", type=int, default=42)

    simulator_parser = subparsers.add_parser(
        "simulate-run", help="produce bounded simulated decisions from one measured run"
    )
    simulator_parser.add_argument("run_directory", help="path to results/raw/<run-id>")
    simulator_parser.add_argument("--config", default="configs/wait_aware.json")
    simulator_parser.add_argument("--output", help="new decisions JSON file; fails if the path exists")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "info":
            result = collect_system_info(args.output_dir)
        elif args.command == "validate-config":
            config = load_config(args.path)
            result = {
                "valid": True,
                "path": args.path,
                "experiment_id": config["experiment_id"],
                "policy": config["policy"]["type"],
            }
        elif args.command == "preflight":
            result = collect_preflight()
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(format_preflight(result))
            return 0 if result.get("ready") else 2
        elif args.command == "analyze-run":
            result = analyze_run(args.run_directory, include_delta_windows=args.include_delta_windows)
        elif args.command == "aggregate-runs":
            result = aggregate_runs(args.run_directories, args.bootstrap_samples, args.seed)
        elif args.command == "plot-runs":
            summary = aggregate_runs(args.run_directories, args.bootstrap_samples, args.seed)
            result = {
                "data_kind": "measured_comparison_plot",
                "run_count": summary["run_count"],
                "output": str(save_comparison_plot(summary, args.output)),
            }
        elif args.command == "simulate-run":
            run_path = Path(args.run_directory).expanduser().resolve()
            measured = analyze_run(run_path, include_delta_windows=True)
            simulation = simulate_wait_aware(measured, load_simulator_config(args.config))
            output_path = (
                Path(args.output).expanduser()
                if args.output
                else run_path.parent.parent / "processed" / run_path.name / "simulated_policy_decisions.json"
            )
            with output_path.open("x", encoding="utf-8") as stream:
                json.dump(simulation, stream, indent=2, sort_keys=True)
                stream.write("\n")
            result = {
                "data_kind": "simulated_policy_decision_summary",
                "source_run_id": simulation["source_run_id"],
                "decision_count": simulation["decision_count"],
                "hypothetical_outcomes_generated": False,
                "live_scheduler_modified": False,
                "output": str(output_path.resolve()),
            }
        elif args.command == "run-pilot":
            result = run_pilot(
                repeats=args.repeats,
                output_root=args.output_root,
                baseline_config=args.baseline_config,
                fixed_nice_config=args.fixed_nice_config,
            )
        else:
            result = run_smoke(args.config, args.output_root)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except AnalysisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except AggregationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except SimulationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except PlotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except FileExistsError as exc:
        print(f"error: refusing to overwrite existing output {exc.filename}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
