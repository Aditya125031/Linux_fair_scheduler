import unittest

from cpu_fairness.policies.simulator import SimulationError, simulate_wait_aware


def _measured_run(window_count: int = 8) -> dict:
    return {
        "data_kind": "measured_run_metrics",
        "run_id": "synthetic-test-run",
        "delta_fairness": {
            "status": "available",
            "windows": [
                {
                    "start_ns": index * 50,
                    "end_ns": (index + 1) * 50,
                    "tasks": [
                        {
                            "tid": 101,
                            "workload_class": "interactive",
                            "runnable_wait_ns": 20,
                        },
                        {
                            "tid": 202,
                            "workload_class": "batch",
                            "runnable_wait_ns": 40,
                        },
                    ],
                }
                for index in range(window_count)
            ],
        },
    }


class WaitAwareSimulatorTests(unittest.TestCase):
    def test_boost_is_bounded_and_cooldown_suppresses_oscillation(self):
        result = simulate_wait_aware(
            _measured_run(),
            {
                "interactive_wait_threshold_ns": 10,
                "batch_aging_wait_threshold_ns": 30,
                "boost_step": 1,
                "aging_step": 1,
                "maximum_boost_level": 2,
                "maximum_aging_level": 2,
                "cooldown_windows": 2,
            },
        )

        interactive = [row for row in result["decisions"] if row["workload_class"] == "interactive"]
        batch = [row for row in result["decisions"] if row["workload_class"] == "batch"]
        self.assertEqual(interactive[0]["action"], "request_bounded_boost")
        self.assertEqual(interactive[1]["action"], "cooldown_hold")
        self.assertLessEqual(max(row["simulated_boost_level"] for row in interactive), 2)
        self.assertLessEqual(max(row["simulated_boost_level"] for row in batch), 2)
        self.assertTrue(any(row["action"] == "request_aging_credit" for row in batch))
        self.assertEqual(result["data_kind"], "simulated_policy_decisions")
        self.assertFalse(result["hypothetical_outcomes_generated"])
        self.assertFalse(result["live_scheduler_modified"])

    def test_rejects_unavailable_or_nonmeasured_input(self):
        with self.assertRaisesRegex(SimulationError, "measured run metrics"):
            simulate_wait_aware({"data_kind": "synthetic_fixture"})
        measured = _measured_run()
        measured["delta_fairness"]["status"] = "unavailable"
        with self.assertRaisesRegex(SimulationError, "without measured scheduler windows"):
            simulate_wait_aware(measured)

    def test_rejects_unknown_config_keys(self):
        measured = _measured_run()
        with self.assertRaisesRegex(SimulationError, "unknown simulator configuration keys"):
            simulate_wait_aware(measured, {"max_boost": 99})


if __name__ == "__main__":
    unittest.main()
