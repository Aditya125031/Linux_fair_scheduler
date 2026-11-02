import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.preflight import _read_os_release, collect_preflight, tracepoint_fields


class PreflightTests(unittest.TestCase):
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
