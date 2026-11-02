import sys
import unittest
from unittest.mock import patch, Mock
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.preflight import _read_os_release, _tracefs_root, collect_preflight, tracepoint_fields


class PreflightTests(unittest.TestCase):
    def test_tracefs_root_uses_noninteractive_privileged_directory_check(self):
        with patch("cpu_fairness.preflight.subprocess.run") as run:
            run.return_value = Mock(returncode=0)
            root = _tracefs_root("/usr/bin/sudo")
        self.assertEqual(root, Path("/sys/kernel/tracing"))
        self.assertEqual(run.call_args.args[0][:3], ["/usr/bin/sudo", "-n", "test"])
        self.assertEqual(run.call_args.kwargs["timeout"], 5)

    def test_tracefs_root_handles_sudo_failures_and_timeout(self):
        with patch("cpu_fairness.preflight.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("sudo", 5)):
            self.assertIsNone(_tracefs_root("/usr/bin/sudo"))
        with patch("cpu_fairness.preflight.subprocess.run", return_value=Mock(returncode=1)):
            self.assertIsNone(_tracefs_root("/usr/bin/sudo"))

    def test_preflight_reads_formats_through_sudo_and_validates_fields(self):
        wakeup = "field:int pid; offset:0; size:4; signed:1;\nfield:int prio; offset:4; size:4; signed:1;\nfield:int target_cpu; offset:8; size:4; signed:1;\n"
        switch = "field:int prev_pid; offset:0; size:4; signed:1;\nfield:int prev_prio; offset:4; size:4; signed:1;\nfield:long prev_state; offset:8; size:8; signed:1;\nfield:int next_pid; offset:16; size:4; signed:1;\nfield:int next_prio; offset:20; size:4; signed:1;\n"
        responses = [Mock(returncode=0), Mock(returncode=0, stdout=wakeup), Mock(returncode=0, stdout=switch)]
        with patch("cpu_fairness.preflight.sys.platform", "linux"), \
             patch("cpu_fairness.preflight.shutil.which", side_effect=lambda name: "/usr/bin/sudo" if name == "sudo" else None), \
             patch("cpu_fairness.preflight.subprocess.run", side_effect=responses) as run, \
             patch("cpu_fairness.preflight.os.geteuid", return_value=1000), \
             patch("cpu_fairness.preflight.Path.is_file", return_value=False):
            result = collect_preflight()
        self.assertTrue(result["checks"]["tracefs"]["ok"])
        self.assertTrue(all(item["ok"] for item in result["checks"]["tracepoints"].values()))
        self.assertEqual(run.call_args_list[1].args[0][1:3], ["-n", "cat"])

    def test_preflight_reports_missing_tracepoints_fields_sudo_failure_and_timeout(self):
        with patch("cpu_fairness.preflight.sys.platform", "linux"), \
             patch("cpu_fairness.preflight.shutil.which", side_effect=lambda name: "/usr/bin/sudo" if name == "sudo" else None), \
             patch("cpu_fairness.preflight.subprocess.run", side_effect=[Mock(returncode=0), Mock(returncode=1, stderr="permission denied"), Mock(returncode=1, stderr="missing")]), \
             patch("cpu_fairness.preflight.os.geteuid", return_value=1000), \
             patch("cpu_fairness.preflight.Path.is_file", return_value=False):
            result = collect_preflight()
        self.assertFalse(result["checks"]["tracepoints"]["sched_wakeup"]["available"])

        # A readable format with missing required fields remains available but fails validation.
        with patch("cpu_fairness.preflight.sys.platform", "linux"), \
             patch("cpu_fairness.preflight.shutil.which", side_effect=lambda name: "/usr/bin/sudo" if name == "sudo" else None), \
             patch("cpu_fairness.preflight.subprocess.run", side_effect=[Mock(returncode=0), Mock(returncode=0, stdout="field:int pid; offset:0; size:4; signed:1;\\n"), Mock(returncode=1, stderr="missing")]), \
             patch("cpu_fairness.preflight.os.geteuid", return_value=1000), \
             patch("cpu_fairness.preflight.Path.is_file", return_value=False):
            result = collect_preflight()
        wakeup = result["checks"]["tracepoints"]["sched_wakeup"]
        self.assertTrue(wakeup["available"])
        self.assertIn("prio", wakeup["missing_fields"])
        self.assertFalse(result["checks"]["tracepoints"]["sched_switch"]["available"])

        with patch("cpu_fairness.preflight.sys.platform", "linux"), \
             patch("cpu_fairness.preflight.shutil.which", side_effect=lambda name: "/usr/bin/sudo" if name == "sudo" else None), \
             patch("cpu_fairness.preflight.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("sudo", 5)), \
             patch("cpu_fairness.preflight.os.geteuid", return_value=1000), \
             patch("cpu_fairness.preflight.Path.is_file", return_value=False):
            result = collect_preflight()
        self.assertFalse(result["checks"]["tracefs"]["ok"])

    def test_reads_tracepoint_format_field_names(self):
        content = (
            "field:unsigned short common_type; offset:0; size:2; signed:0;\n"
            "field:int pid; offset:4; size:4; signed:1;\n"
            "field:char comm[16]; offset:8; size:16; signed:1;\n"
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "format"
            path.write_text(content, encoding="utf-8")
            self.assertEqual(tracepoint_fields(path), {"common_type", "pid", "comm"})

    def test_reads_os_release_distribution_fields(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "os-release"
            path.write_text(
                'ID=ubuntu\nVERSION_ID="26.04.1"\nPRETTY_NAME="Ubuntu 26.04.1 LTS"\n',
                encoding="utf-8",
            )
            self.assertEqual(_read_os_release(path)["PRETTY_NAME"], "Ubuntu 26.04.1 LTS")

    @unittest.skipIf(sys.platform.startswith("linux"), "Windows-only platform guard")
    def test_non_linux_preflight_stops_before_linux_probes(self):
        result = collect_preflight()
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["linux_platform"]["ok"])
        self.assertEqual(set(result["checks"]), {"linux_platform"})


if __name__ == "__main__":
    unittest.main()
