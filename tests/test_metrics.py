import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.analysis.metrics import AnalysisError, analyze_run, nearest_rank_summary


class RunMetricsTests(unittest.TestCase):
    def _write_run(self, root: Path, status: str = "completed") -> Path:
        raw = root / "raw" / "test-run"
        processed = root / "processed" / "test-run"
        raw.mkdir(parents=True)
        processed.mkdir(parents=True)
        (raw / "interactive.jsonl").write_text(
            "".join(
                json.dumps({"response_latency_ns": value}) + "\n"
                for value in [10, 20, 30, 40, 50]
            ),
            encoding="utf-8",
        )
        (raw / "batch.json").write_text(
            json.dumps({"completed_units": 20, "duration_monotonic_ns": 4_000_000_000}),
            encoding="utf-8",
        )
        (processed / "analysis.json").write_text(
            json.dumps({"event_counts": {"all_trace_records": 99}, "warnings": []}),
            encoding="utf-8",
        )
        (processed / "wait_episodes.jsonl").write_text(
            "".join(
                json.dumps(row) + "\n"
                for row in [
                    {"tid": 101, "wait_ns": 100, "complete": True},
                    {"tid": 101, "wait_ns": 200, "complete": True},
                    {"tid": 101, "wait_ns": 300, "complete": True},
                    {"tid": 101, "wait_ns": None, "complete": False},
                    {"tid": 202, "wait_ns": 500, "complete": True},
                ]
            ),
            encoding="utf-8",
        )
        (processed / "task_accounting.json").write_text(
            json.dumps(
                [
                    {"tid": 101, "cpu_service_ns": 1500, "incomplete_service_intervals": 0},
                    {"tid": 202, "cpu_service_ns": 2500, "incomplete_service_intervals": 1},
                ]
            ),
            encoding="utf-8",
        )
        manifest = {
            "run_id": "test-run",
            "status": status,
            "configuration": {"policy": {"type": "fixed_nice", "batch_nice": 5}},
            "processes": {
                "interactive": {"tids": [101], "nice_value": 0},
                "batch": {"tids": [202], "nice_value": 5},
            },
            "policy_application": {"runner_nice_value": 0, "batch_nice_target": 5},
            "warnings": [],
            "outputs": {
                "interactive_jsonl": str(raw / "interactive.jsonl"),
                "batch_summary": str(raw / "batch.json"),
                "analysis": str(processed / "analysis.json"),
                "wait_episodes": str(processed / "wait_episodes.jsonl"),
                "task_accounting": str(processed / "task_accounting.json"),
            },
        }
        (raw / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return raw

    def test_analyzes_latency_wait_service_and_batch_throughput_separately(self):
        with TemporaryDirectory() as directory:
            result = analyze_run(self._write_run(Path(directory)))

        self.assertEqual(result["policy"], "fixed_nice")
        self.assertEqual(
            result["interactive"]["response_latency"],
            {"sample_count": 5, "method": "nearest_rank", "p50_ns": 30, "p95_ns": 50},
        )
        self.assertEqual(result["interactive"]["runnable_wait"]["p50_ns"], 200)
        self.assertEqual(result["interactive"]["runnable_wait"]["censored_sample_count"], 1)
        self.assertEqual(result["interactive"]["cpu_service_ns"], 1500)
        self.assertEqual(result["batch"]["runnable_wait"]["p50_ns"], 500)
        self.assertEqual(result["batch"]["cpu_service_ns"], 2500)
        self.assertEqual(result["batch"]["throughput_units_per_second"], 5.0)
        self.assertEqual(result["scheduler_event_counts"]["all_trace_records"], 99)
        self.assertFalse(result["metric_definitions"]["clock_domains_subtracted"])

    def test_nearest_rank_reports_empty_sample_count_without_inventing_values(self):
        self.assertEqual(
            nearest_rank_summary([]),
            {"sample_count": 0, "method": "nearest_rank", "p50_ns": None, "p95_ns": None},
        )

    def test_rejects_noncompleted_run(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AnalysisError, "only runs with manifest status"):
                analyze_run(self._write_run(Path(directory), status="failed"))

    def test_rejects_malformed_workload_log_instead_of_skipping_record(self):
        with TemporaryDirectory() as directory:
            raw = self._write_run(Path(directory))
            with (raw / "interactive.jsonl").open("a", encoding="utf-8") as stream:
                stream.write("not json\n")
            with self.assertRaisesRegex(AnalysisError, "interactive workload log line 6"):
                analyze_run(raw)


if __name__ == "__main__":
    unittest.main()
