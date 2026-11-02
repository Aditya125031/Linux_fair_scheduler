import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.workloads.batch_worker import run_batch
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


if __name__ == "__main__":
    unittest.main()
