import unittest
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.analysis.plots import PlotError, comparison_plot_data, save_comparison_plot


class PlotDataTests(unittest.TestCase):
    @staticmethod
    def _aggregate():
        def metric(mean, low, high):
            return {
                "mean": mean,
                "bootstrap_95_ci_for_mean": {"lower_95": low, "upper_95": high},
            }

        return {
            "data_kind": "measured_repeated_run_summary",
            "policies": {
                "baseline": {
                    "run_count": 2,
                    "metrics": {
                        "interactive_response_p95_ns": metric(2_000_000, 1_500_000, 2_500_000),
                        "batch_throughput_units_per_second": metric(20.0, 18.0, 22.0),
                        "delta_batch_to_interactive_mean": metric(0.2, 0.1, 0.3),
                        "delta_interactive_to_batch_mean": metric(0.05, 0.0, 0.1),
                        "delta_global_mean": metric(0.1, 0.05, 0.15),
                    },
                }
            },
        }

    def test_prepares_only_measured_policy_summaries_and_preserves_missing_values(self):
        result = comparison_plot_data(
            {
                "data_kind": "measured_repeated_run_summary",
                "policies": {
                    "baseline": {
                        "run_count": 2,
                        "metrics": {
                            "interactive_response_p95_ns": {"mean": 2_000_000},
                            "batch_throughput_units_per_second": {"mean": 10.0},
                            "delta_batch_to_interactive_mean": {"mean": 0.2},
                            "delta_interactive_to_batch_mean": {"mean": None},
                            "delta_global_mean": {"mean": 0.1},
                        },
                    }
                },
            }
        )
        self.assertEqual(result["interactive_response_p95_ms"], [2.0])
        self.assertEqual(result["batch_throughput_units_per_second"], [10.0])
        self.assertEqual(result["delta"]["ΔB→I"], [0.2])
        self.assertIsNone(result["delta"]["ΔI→B"][0])

    def test_rejects_nonmeasured_input(self):
        with self.assertRaisesRegex(PlotError, "measured repeated-run summaries"):
            comparison_plot_data({"data_kind": "simulated_policy_decisions"})

    def test_saves_png_without_overwriting(self):
        if importlib.util.find_spec("matplotlib") is None:
            self.skipTest("optional Matplotlib is not installed")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.png"
            saved = save_comparison_plot(self._aggregate(), output)
            self.assertEqual(saved, output.resolve())
            self.assertGreater(output.stat().st_size, 0)
            with self.assertRaises(FileExistsError):
                save_comparison_plot(self._aggregate(), output)


if __name__ == "__main__":
    unittest.main()
