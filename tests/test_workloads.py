import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cpu_fairness.workloads.batch_worker import _set_nice_value, run_batch
from cpu_fairness.workloads.interactive import run_interactive


class WorkloadTests(unittest.TestCase):
    def test_interactive_workload_emits_monotonic_jsonl(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_interactive(0.025, 5, 100, root / "interactive.jsonl", root / "ready.json")
            rows = [json.loads(line) for line in (root / "interactive.jsonl").read_text().splitlines()]
            self.assertGreaterEqual(len(rows), 1)
            self.assertGreater(result["tgid"], 0)
            self.assertGreater(result["tid"], 0)
            self.assertLessEqual(
                rows[0]["intended_release_monotonic_ns"],
                rows[0]["execution_start_monotonic_ns"],
            )
            self.assertIn("response_latency_ns", rows[0])

    def test_batch_workload_emits_structured_summary(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_batch(0.02, 100, "batch-test", root / "batch.json", root / "ready.json")
            row = json.loads((root / "batch.json").read_text())
            self.assertEqual(row["worker_id"], "batch-test")
            self.assertGreater(row["tgid"], 0)
            self.assertGreater(row["tid"], 0)
            self.assertGreater(row["completed_units"], 0)
            self.assertEqual(result["completion_status"], "completed")

    def test_batch_workload_sets_nice_before_ready_identity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("cpu_fairness.workloads.batch_worker.os.setpriority", create=True) as setpriority, \
                 patch("cpu_fairness.workloads.batch_worker.os.getpriority", return_value=5, create=True), \
                 patch("cpu_fairness.workloads.batch_worker.os.PRIO_PROCESS", 0, create=True):
                result = run_batch(
                    0.02, 100, "batch-nice", root / "batch.json", root / "ready.json",
                    nice_value=5,
                )
            setpriority.assert_called_once_with(0, 0, 5)
            ready = json.loads((root / "ready.json").read_text())
            summary = json.loads((root / "batch.json").read_text())
            self.assertEqual(ready["nice_value"], 5)
            self.assertEqual(summary["nice_value"], 5)
            self.assertEqual(result["nice_value"], 5)

    def test_batch_workload_rejects_nice_value_outside_unprivileged_range(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "0 through 19"):
                run_batch(0.01, 10, "batch-invalid", Path(directory) / "out.json", nice_value=-1)

    def test_batch_workload_reports_nice_permission_failure(self):
        with patch(
            "cpu_fairness.workloads.batch_worker.os.setpriority",
            side_effect=PermissionError("permission denied"),
            create=True,
        ), patch("cpu_fairness.workloads.batch_worker.os.PRIO_PROCESS", 0, create=True):
            with self.assertRaisesRegex(RuntimeError, "could not set batch nice value to 5"):
                _set_nice_value(5)


if __name__ == "__main__":
    unittest.main()
