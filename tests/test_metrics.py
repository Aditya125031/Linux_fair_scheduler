import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.analysis.metrics import AnalysisError, analyze_run, nearest_rank_summary


class RunMetricsTests(unittest.TestCase):
    def _write_run(
        self,
        root: Path,
        status: str = "completed",
        legacy_timing: bool = False,
        with_delta_trace: bool = False,
    ) -> Path:
        raw = root / "raw" / "test-run"
        processed = root / "processed" / "test-run"
        raw.mkdir(parents=True)
        processed.mkdir(parents=True)
        interactive_rows = []
        for value in [10, 20, 30, 40, 50]:
            release = 1_000
            execution_start = release + value
            completion = release + value + 100
            row = {
                "intended_release_monotonic_ns": release,
                "execution_start_monotonic_ns": execution_start,
                "completion_monotonic_ns": completion,
            }
            if legacy_timing:
                row["response_latency_ns"] = completion - release
            else:
                row["approx_response_time_ns"] = execution_start - release
                row["turnaround_time_ns"] = completion - release
            interactive_rows.append(row)
        (raw / "interactive.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in interactive_rows),
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
                "interactive": {
                    "tids": [101], "nice_value": 0,
                    "scheduler_policy": {"code": 0, "name": "SCHED_OTHER"},
                },
                "batch": {
                    "tids": [202], "nice_value": 5,
                    "scheduler_policy": {"code": 0, "name": "SCHED_OTHER"},
                },
            },
            "environment": {
                "effective_cpu_count": 1,
                "cpu_quota": {"status": "unlimited", "quota_us": None, "period_us": 100000},
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
        if with_delta_trace:
            from cpu_fairness.telemetry.parser import EVENT_COLUMNS

            trace_path = raw / "scheduler.tsv"
            trace_path.write_text(
                "\t".join(EVENT_COLUMNS)
                + "\n"
                + "0\tWAKEUP\t202\t-1\t-1\t-1\t120\t-1\t-1\t0\t0\n"
                + "0\tWAKEUP\t101\t-1\t-1\t-1\t120\t-1\t-1\t0\t0\n"
                + "1\tSWITCH\t-1\t0\t101\t0\t-1\t120\t120\t0\t-1\n"
                + "50000000\tSWITCH\t-1\t101\t202\t0\t-1\t120\t120\t0\t-1\n"
                + "100000000\tSWITCH\t-1\t202\t101\t0\t-1\t120\t120\t0\t-1\n"
                + "150000000\tSWITCH\t-1\t101\t202\t0\t-1\t120\t120\t0\t-1\n"
                + "160000000\tEND\t-1\t-1\t-1\t-1\t-1\t-1\t-1\t-1\t-1\n",
                encoding="utf-8",
            )
            manifest["outputs"]["raw_trace"] = str(trace_path)
        (raw / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return raw

    def test_analyzes_response_turnaround_wait_service_and_throughput_separately(self):
        with TemporaryDirectory() as directory:
            result = analyze_run(self._write_run(Path(directory)))

        self.assertEqual(result["policy"], "fixed_nice")
        self.assertEqual(
            result["interactive"]["approx_response_time"],
            {"sample_count": 5, "method": "nearest_rank", "p50_ns": 30, "p95_ns": 50},
        )
        self.assertEqual(
            result["interactive"]["turnaround_time"],
            {"sample_count": 5, "method": "nearest_rank", "p50_ns": 130, "p95_ns": 150},
        )
        self.assertNotEqual(
            result["interactive"]["approx_response_time"]["p50_ns"],
            result["interactive"]["turnaround_time"]["p50_ns"],
        )
        self.assertEqual(result["interactive_timing_schema"], "corrected_explicit_fields")
        self.assertFalse(result["interactive"]["per_request_cpu_service_time"]["available"])
        self.assertEqual(result["interactive"]["runnable_wait"]["p50_ns"], 200)
        self.assertEqual(result["interactive"]["runnable_wait"]["censored_sample_count"], 1)
        self.assertEqual(result["interactive"]["cpu_service_ns"], 1500)
        self.assertEqual(result["batch"]["runnable_wait"]["p50_ns"], 500)
        self.assertEqual(result["batch"]["cpu_service_ns"], 2500)
        self.assertEqual(result["batch"]["throughput_units_per_second"], 5.0)
        self.assertEqual(result["scheduler_event_counts"]["all_trace_records"], 99)
        self.assertFalse(result["metric_definitions"]["clock_domains_subtracted"])
        self.assertEqual(result["delta_fairness"]["status"], "unavailable")

    def test_analyze_run_computes_delta_windows_from_trace_and_manifest(self):
        with TemporaryDirectory() as directory:
            result = analyze_run(
                self._write_run(Path(directory), with_delta_trace=True)
            )

        delta = result["delta_fairness"]
        self.assertEqual(delta["status"], "available")
        self.assertEqual(delta["window_counts"]["with_both_classes"], 2)
        self.assertEqual(delta["delta_batch_to_interactive"]["maximum"], 1.0)
        self.assertEqual(delta["delta_interactive_to_batch"]["maximum"], 1.0)

    def test_delta_is_withheld_when_cgroup_cpu_quota_is_limited(self):
        with TemporaryDirectory() as directory:
            raw = self._write_run(Path(directory), with_delta_trace=True)
            manifest_path = raw / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["environment"]["cpu_quota"] = {
                "status": "limited",
                "quota_us": 50_000,
                "period_us": 100_000,
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = analyze_run(raw)

        self.assertEqual(result["delta_fairness"]["status"], "unavailable")
        self.assertIn("unlimited cgroup CPU quota", result["delta_fairness"]["reason"])

    def test_legacy_latency_is_labeled_and_not_used_for_corrected_metrics(self):
        with TemporaryDirectory() as directory:
            result = analyze_run(self._write_run(Path(directory), legacy_timing=True))

        self.assertEqual(
            result["interactive"]["approx_response_time"]["p50_ns"], 30
        )
        self.assertEqual(result["interactive"]["turnaround_time"]["p50_ns"], 130)
        self.assertEqual(
            result["interactive_timing_schema"], "legacy_field_timestamp_derived"
        )
        legacy = result["legacy_ambiguous_response_latency"]
        self.assertEqual(legacy["field_name"], "response_latency_ns")
        self.assertEqual(legacy["summary"]["p50_ns"], 130)
        self.assertFalse(legacy["used_for_corrected_metrics"])

    def test_rejects_missing_or_invalid_interactive_timestamps(self):
        for replacement, message in (
            ({"execution_start_monotonic_ns": None}, "execution_start_monotonic_ns"),
            ({"completion_monotonic_ns": -1}, "completion_monotonic_ns"),
            ({"execution_start_monotonic_ns": 999}, "timestamps must satisfy"),
        ):
            with self.subTest(replacement=replacement), TemporaryDirectory() as directory:
                raw = self._write_run(Path(directory))
                records = [
                    json.loads(line)
                    for line in (raw / "interactive.jsonl").read_text().splitlines()
                ]
                records[0].update(replacement)
                (raw / "interactive.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
                )
                with self.assertRaisesRegex(AnalysisError, message):
                    analyze_run(raw)

        with TemporaryDirectory() as directory:
            raw = self._write_run(Path(directory))
            records = [
                json.loads(line)
                for line in (raw / "interactive.jsonl").read_text().splitlines()
            ]
            del records[0]["execution_start_monotonic_ns"]
            (raw / "interactive.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
            )
            with self.assertRaisesRegex(AnalysisError, "execution_start_monotonic_ns"):
                analyze_run(raw)

    def test_rejects_corrected_metric_that_disagrees_with_timestamps(self):
        with TemporaryDirectory() as directory:
            raw = self._write_run(Path(directory))
            records = [
                json.loads(line)
                for line in (raw / "interactive.jsonl").read_text().splitlines()
            ]
            records[0]["approx_response_time_ns"] = 999
            (raw / "interactive.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
            )
            with self.assertRaisesRegex(AnalysisError, "does not match its source timestamps"):
                analyze_run(raw)

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
