"""Configuration, preflight, and initial Linux smoke-test commands."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from cpu_fairness import __version__
from cpu_fairness.config import ConfigError, load_config
from cpu_fairness.experiment import ExperimentError, run_smoke
from cpu_fairness.preflight import collect_preflight, format_preflight
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
        else:
            result = run_smoke(args.config, args.output_root)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
