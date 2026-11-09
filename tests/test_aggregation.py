import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cpu_fairness.analysis.aggregation import (
    AggregationError,
    _bootstrap_mean_interval,
    aggregate_runs,
)


class AggregationTests(unittest.TestCase):
    def _run(self, directory: Path, run_id: str, policy: str, duration: int = 5) -> Path:
        path = directory / run_id
        path.mkdir()
        (path / "manifest.json").write_text(
            json.dumps(
                {
                    "configuration": {
                        "schema_version": 1,
                        "experiment_id": run_id,
                        "duration_seconds": duration,
                        "interactive": {"arrival_interval_ms": 100},
                        "batch": {"workers": 1},
                        "policy": {"type": policy},
                    }
                }
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _analysis(run_id: str, policy: str, response_p50: int, throughput: float) -> dict:
        return {
            "run_id": run_id,
            "policy": policy,
            "interactive": {
                "approx_response_time": {"p50_ns": response_p50, "p95_ns": response_p50 * 2},
                "turnaround_time": {"p95_ns": response_p50 * 3},
            },
            "batch": {"throughput_units_per_second": throughput},
            "delta_fairness": {
                "global_delta": {"mean": 0.1},
                "delta_batch_to_interactive": {"mean": 0.2},
                "delta_interactive_to_batch": {"mean": 0.05},
            },
        }

    def test_aggregates_repeated_runs_by_policy_with_bootstrap_intervals(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [
                self._run(root, "base-1", "baseline"),
                self._run(root, "base-2", "baseline"),
                self._run(root, "nice-1", "fixed_nice"),
            ]
            analyses = {
                "base-1": self._analysis("base-1", "baseline", 100, 20.0),
                "base-2": self._analysis("base-2", "baseline", 200, 18.0),
                "nice-1": self._analysis("nice-1", "fixed_nice", 80, 15.0),
            }
            with patch(
                "cpu_fairness.analysis.aggregation.analyze_run",
                side_effect=lambda path: analyses[Path(path).name],
            ):
                result = aggregate_runs(paths, bootstrap_samples=500, seed=7)

        self.assertEqual(result["data_kind"], "measured_repeated_run_summary")
        self.assertEqual(result["policies"]["baseline"]["run_count"], 2)
        baseline = result["policies"]["baseline"]["metrics"]["interactive_response_p50_ns"]
        self.assertEqual(baseline["mean"], 150.0)
        self.assertEqual(baseline["median"], 150.0)
        self.assertEqual(baseline["bootstrap_95_ci_for_mean"]["sample_count"], 2)
        self.assertEqual(result["comparisons"], "descriptive only; no statistical significance claim or paired-run inference")

    def test_bootstrap_requires_multiple_runs_and_is_reproducible(self):
        self.assertEqual(
            _bootstrap_mean_interval([1.0], 100, 1),
            {"sample_count": 1, "lower_95": None, "upper_95": None},
        )
        self.assertEqual(
            _bootstrap_mean_interval([1.0, 2.0, 3.0], 500, 9),
            _bootstrap_mean_interval([1.0, 2.0, 3.0], 500, 9),
        )

    def test_rejects_mismatched_workload_configurations(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [
                self._run(root, "base-1", "baseline", duration=5),
                self._run(root, "base-2", "baseline", duration=10),
            ]
            analyses = {
                path.name: self._analysis(path.name, "baseline", 100, 20.0)
                for path in paths
            }
            with patch(
                "cpu_fairness.analysis.aggregation.analyze_run",
                side_effect=lambda path: analyses[Path(path).name],
            ), self.assertRaisesRegex(AggregationError, "different workload configurations"):
                aggregate_runs(paths)

    def test_rejects_different_settings_within_same_policy_group(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [
                self._run(root, "nice-1", "fixed_nice"),
                self._run(root, "nice-2", "fixed_nice"),
            ]
            for path, nice_value in zip(paths, (5, 10)):
                manifest_path = path / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["configuration"]["policy"]["batch_nice"] = nice_value
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            analyses = {
                path.name: self._analysis(path.name, "fixed_nice", 100, 20.0)
                for path in paths
            }
            with patch(
                "cpu_fairness.analysis.aggregation.analyze_run",
                side_effect=lambda path: analyses[Path(path).name],
            ), self.assertRaisesRegex(AggregationError, "different policy settings"):
                aggregate_runs(paths)


if __name__ == "__main__":
    unittest.main()
