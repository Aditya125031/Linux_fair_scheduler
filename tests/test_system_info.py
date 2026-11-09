import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cpu_fairness.system_info import _cgroup_cpu_quota, collect_system_info


class SystemInfoTests(unittest.TestCase):
    def test_system_information_is_json_compatible(self):
        info = collect_system_info()
        self.assertIsInstance(info["platform"], str)
        self.assertIsInstance(info["python_version"], str)
        self.assertIsInstance(info["is_linux"], bool)
        self.assertIsInstance(info["is_windows"], bool)
        self.assertTrue(info["logical_cpu_count"] is None or info["logical_cpu_count"] > 0)
        self.assertTrue(
            info["effective_cpu_count"] is None or info["effective_cpu_count"] > 0
        )
        self.assertTrue(
            info["cpu_affinity"] is None or len(info["cpu_affinity"]) == info["effective_cpu_count"]
        )
        self.assertIn(info["cpu_quota"]["status"], {"unlimited", "limited", "unknown"})

    def test_output_directory_is_observed_without_being_created(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "not-created"
            info = collect_system_info(target)
            self.assertFalse(info["output_dir_exists"])
            self.assertFalse(target.exists())

    def test_cpu_quota_check_walks_up_when_leaf_has_no_cpu_max(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "cgroup"
            leaf = root / "user.slice" / "user-1000.slice" / "session.scope"
            leaf.mkdir(parents=True)
            (root / "cpu.max").write_text("max 100000\n", encoding="ascii")
            (root / "user.slice" / "cpu.max").write_text("max 100000\n", encoding="ascii")
            membership = Path(directory) / "self.cgroup"
            membership.write_text("0::/user.slice/user-1000.slice/session.scope\n", encoding="utf-8")

            result = _cgroup_cpu_quota(membership, root)

        self.assertEqual(result["status"], "unlimited")
        self.assertEqual(result["checked_cgroup_count"], 2)

    def test_cpu_quota_check_detects_a_limited_ancestor(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "cgroup"
            leaf = root / "user.slice" / "user-1000.slice" / "session.scope"
            leaf.mkdir(parents=True)
            (root / "cpu.max").write_text("max 100000\n", encoding="ascii")
            (root / "user.slice" / "cpu.max").write_text("50000 100000\n", encoding="ascii")
            membership = Path(directory) / "self.cgroup"
            membership.write_text("0::/user.slice/user-1000.slice/session.scope\n", encoding="utf-8")

            result = _cgroup_cpu_quota(membership, root)

        self.assertEqual(result["status"], "limited")
        self.assertEqual(result["cpu_equivalents"], 0.5)


if __name__ == "__main__":
    unittest.main()
