import unittest
from pathlib import Path

from cpu_fairness.telemetry import collector


class CollectorScriptTests(unittest.TestCase):
    def test_script_contains_only_initial_events_and_machine_schema_markers(self):
        script = Path(collector.__file__).with_name("scheduler.bt").read_text(encoding="utf-8")
        self.assertIn("tracepoint:sched:sched_wakeup", script)
        self.assertIn("tracepoint:sched:sched_switch", script)
        self.assertIn("args->target_cpu", script)
        self.assertIn("args->prev_state", script)
        self.assertIn('printf("READY\\n")', script)
        self.assertIn("@clock_heartbeat", script)


if __name__ == "__main__":
    unittest.main()
