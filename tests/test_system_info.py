import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.system_info import collect_system_info


class SystemInfoTests(unittest.TestCase):
    def test_system_information_is_json_compatible(self):
        info = collect_system_info()
        self.assertIsInstance(info["platform"], str)
        self.assertIsInstance(info["python_version"], str)
        self.assertIsInstance(info["is_linux"], bool)
        self.assertIsInstance(info["is_windows"], bool)
        self.assertTrue(info["logical_cpu_count"] is None or info["logical_cpu_count"] > 0)

    def test_output_directory_is_observed_without_being_created(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "not-created"
            info = collect_system_info(target)
            self.assertFalse(info["output_dir_exists"])
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
