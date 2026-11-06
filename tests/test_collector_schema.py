import unittest
import io
import signal
import subprocess
import tempfile
from unittest.mock import patch
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

    def _collector_with_process(self, process):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        instance = collector.BpftraceCollector(root / "trace.tsv", root / "stderr.log")
        return instance, root

    def test_launch_does_not_start_new_session_and_stop_signals_and_reaps(self):
        class FakeProcess:
            pid = 4321
            stdout = io.StringIO("READY\n")

            def __init__(self):
                self.returncode = None
                self.signals = []
                self.wait_calls = []

            def poll(self):
                return self.returncode

            def send_signal(self, sig):
                self.signals.append(sig)

            def wait(self, timeout=None):
                self.wait_calls.append(timeout)
                self.returncode = -2
                return self.returncode

        process = FakeProcess()
        instance, _ = self._collector_with_process(process)
        with patch("cpu_fairness.telemetry.collector.os.sys.platform", "linux"), \
             patch("cpu_fairness.telemetry.collector.subprocess.Popen", return_value=process) as popen:
            instance.start(timeout_seconds=1)
            self.assertNotIn("start_new_session", popen.call_args.kwargs)
            metadata = instance.stop(timeout_seconds=1)
        self.assertEqual(process.signals, [signal.SIGINT])
        self.assertEqual(process.wait_calls, [1])
        self.assertEqual(metadata["returncode"], -2)

    def test_trace_records_before_ready_are_preserved_until_ready_marker(self):
        class FakeProcess:
            pid = 4323
            stdout = io.StringIO(
                "827611586942\tSWITCH\t-1\t3983\t0\t1\t-1\t120\t120\t0\t-1\n"
                "READY\n"
                "827611587010\tWAKEUP\t3983\t-1\t-1\t-1\t120\t-1\t-1\t0\t0\n"
            )

            def __init__(self):
                self.returncode = None

            def poll(self):
                return self.returncode

            def send_signal(self, sig):
                pass

            def wait(self, timeout=None):
                self.returncode = 0
                return self.returncode

        process = FakeProcess()
        instance, root = self._collector_with_process(process)
        with patch("cpu_fairness.telemetry.collector.os.sys.platform", "linux"), \
             patch("cpu_fairness.telemetry.collector.subprocess.Popen", return_value=process):
            instance.start(timeout_seconds=1)
            metadata = instance.stop(timeout_seconds=1)

        trace = (root / "trace.tsv").read_text(encoding="utf-8")
        rows = trace.splitlines()
        self.assertEqual(len(rows), 3)  # header plus both event records
        self.assertEqual(rows[1].split("\t")[1], "SWITCH")
        self.assertEqual(rows[2].split("\t")[1], "WAKEUP")
        self.assertNotIn("READY", trace)
        self.assertEqual(metadata["event_lines_written"], 2)

    def test_stop_escalates_and_reaps_after_shutdown_timeout(self):
        class SlowProcess:
            pid = 4322
            stdout = io.StringIO("READY\n")

            def __init__(self):
                self.returncode = None
                self.terminations = 0
                self.kills = 0
                self.wait_calls = 0

            def poll(self):
                return self.returncode

            def send_signal(self, sig):
                pass

            def wait(self, timeout=None):
                self.wait_calls += 1
                if self.wait_calls <= 2:
                    raise subprocess.TimeoutExpired("sudo bpftrace", timeout)
                self.returncode = -9
                return self.returncode

            def terminate(self):
                self.terminations += 1

            def kill(self):
                self.kills += 1

        process = SlowProcess()
        instance, _ = self._collector_with_process(process)
        with patch("cpu_fairness.telemetry.collector.os.sys.platform", "linux"), \
             patch("cpu_fairness.telemetry.collector.subprocess.Popen", return_value=process):
            instance.start(timeout_seconds=1)
            metadata = instance.stop(timeout_seconds=0.1)
        self.assertEqual(process.terminations, 1)
        self.assertEqual(process.kills, 1)
        self.assertEqual(process.wait_calls, 3)
        self.assertEqual(metadata["returncode"], -9)


if __name__ == "__main__":
    unittest.main()
