import unittest
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
        self.assertEqual(result["metrics"]["interactive_response_p95_ns"], [{"mean": 2_000_000}])
        self.assertEqual(result["metrics"]["batch_throughput_units_per_second"], [{"mean": 10.0}])
        self.assertEqual(result["labels"][-1], "Wait-aware (simulator only)")
        self.assertEqual(result["metrics"]["delta_interactive_to_batch_mean"][-2], {"mean": 0.05})
        self.assertIsNone(result["metrics"]["delta_interactive_to_batch_mean"][-1])

    def test_rejects_nonmeasured_input(self):
        with self.assertRaisesRegex(PlotError, "measured repeated-run summaries"):
            comparison_plot_data({"data_kind": "simulated_policy_decisions"})

    def test_saves_svg_without_optional_dependencies_and_refuses_overwrite(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.svg"
            saved = save_comparison_plot(self._aggregate(), output)
            self.assertEqual(saved, output.resolve())
            chart = output.read_text(encoding="utf-8")
            self.assertIn("Wait-aware is an offline simulator", chart)
            self.assertIn("not measured", chart)
            with self.assertRaises(FileExistsError):
                save_comparison_plot(self._aggregate(), output)


if __name__ == "__main__":
    unittest.main()
