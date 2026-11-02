import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cpu_fairness.cli import main
from cpu_fairness.experiment import ExperimentError, run_smoke


class CliTests(unittest.TestCase):
    def test_info_command_reports_current_platform(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["info"]), 0)
        result = json.loads(output.getvalue())
        self.assertIn("platform", result)
        self.assertIn("is_linux", result)

    def test_validate_config_command(self):
        with TemporaryDirectory() as directory:
            config = Path(directory) / "quick.json"
            config.write_text(
                '{"schema_version":1,"experiment_id":"smoke","duration_seconds":1,'
                '"interactive":{"arrival_interval_ms":50,"burst_iterations":100},'
                '"batch":{"workers":1,"unit_iterations":100},"policy":{"type":"baseline"}}',
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["validate-config", str(config)]), 0)
            self.assertTrue(json.loads(output.getvalue())["valid"])

    def test_invalid_config_returns_error_code(self):
        with TemporaryDirectory() as directory:
            config = Path(directory) / "bad.json"
            config.write_text("{}", encoding="utf-8")
            errors = StringIO()
            with redirect_stderr(errors):
                self.assertEqual(main(["validate-config", str(config)]), 2)
            self.assertIn("error:", errors.getvalue())

    def test_smoke_refuses_to_start_on_windows(self):
        with patch("cpu_fairness.experiment.sys.platform", "win32"):
            with self.assertRaisesRegex(ExperimentError, "Linux-only"):
                run_smoke("configs/quick.json")


if __name__ == "__main__":
    unittest.main()
