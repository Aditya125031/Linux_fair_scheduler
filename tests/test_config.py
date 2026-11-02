import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.config import ConfigError, load_config, validate_config


def valid_config():
    return {
        "schema_version": 1,
        "experiment_id": "test-run",
        "duration_seconds": 1,
        "interactive": {"arrival_interval_ms": 50, "burst_iterations": 100},
        "batch": {"workers": 1, "unit_iterations": 1000},
        "policy": {"type": "baseline"},
    }


class ConfigTests(unittest.TestCase):
    def test_accepts_valid_baseline_config(self):
        self.assertEqual(validate_config(valid_config())["experiment_id"], "test-run")

    def test_accepts_fixed_nice_configuration(self):
        config = valid_config()
        config["policy"] = {"type": "fixed_nice", "batch_nice": 5}
        self.assertEqual(validate_config(config)["policy"]["batch_nice"], 5)

    def test_rejects_invalid_values(self):
        cases = [
            (lambda c: c.update(schema_version=2), "schema_version"),
            (lambda c: c.update(schema_version=True), "schema_version"),
            (lambda c: c.update(experiment_id=" "), "experiment_id"),
            (lambda c: c.update(duration_seconds=0), "duration_seconds"),
            (lambda c: c["interactive"].update(arrival_interval_ms=True), "arrival_interval_ms"),
            (lambda c: c["batch"].update(workers=0), "workers"),
            (lambda c: c["policy"].update(type="live_controller"), "policy.type"),
            (lambda c: c["policy"].update(type=[]), "policy.type"),
        ]
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                config = valid_config()
                mutate(config)
                with self.assertRaisesRegex(ConfigError, expected):
                    validate_config(config)

    def test_load_reports_invalid_json(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "invalid JSON"):
                load_config(path)

    def test_load_rejects_duplicate_keys(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "duplicate JSON key"):
                load_config(path)

    def test_load_rejects_non_finite_numbers(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nonfinite.json"
            text = json.dumps(valid_config()).replace(
                '"duration_seconds": 1', '"duration_seconds": NaN'
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "non-finite"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
