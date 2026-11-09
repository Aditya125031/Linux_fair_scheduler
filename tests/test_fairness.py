import unittest

from cpu_fairness.analysis.fairness import (
    TaskWindow,
    analyze_delta_windows,
    calculate_delta_window,
    nice_to_weight,
)
from cpu_fairness.telemetry.parser import SchedulerEvent


class DeltaFairnessTests(unittest.TestCase):
    def test_delta_matches_capacity_normalized_example(self):
        result = calculate_delta_window(
            [
                TaskWindow(101, "batch", 0, service_ns=50, runnable_wait_ns=0),
                TaskWindow(202, "interactive", 0, service_ns=2, runnable_wait_ns=8),
            ],
            cpu_count=1,
            window_ns=50,
        )

        self.assertAlmostEqual(result["global_delta"], 0.4)
        self.assertAlmostEqual(result["interactive_mean_deficit"], 0.8)
        self.assertEqual(result["batch_mean_deficit"], 0.0)
        self.assertAlmostEqual(result["delta_batch_to_interactive"], 0.8)
        self.assertEqual(result["delta_interactive_to_batch"], 0.0)

    def test_nice_values_map_to_fair_scheduler_weights(self):
        self.assertEqual(nice_to_weight(0), 1024)
        self.assertEqual(nice_to_weight(5), 335)
        with self.assertRaises(ValueError):
            nice_to_weight(20)

    def test_directional_metric_is_unavailable_without_both_classes(self):
        result = calculate_delta_window(
            [TaskWindow(101, "batch", 0, service_ns=10, runnable_wait_ns=0)],
            cpu_count=1,
            window_ns=10,
        )
        self.assertEqual(result["global_delta"], 0)
        self.assertIsNone(result["delta_batch_to_interactive"])
        self.assertIsNone(result["delta_interactive_to_batch"])

    def test_rejects_demand_greater_than_window(self):
        with self.assertRaisesRegex(ValueError, "demand exceeds"):
            calculate_delta_window(
                [TaskWindow(101, "batch", 0, service_ns=8, runnable_wait_ns=3)],
                cpu_count=1,
                window_ns=10,
            )

    def test_trace_intervals_are_split_into_full_warmup_aligned_windows(self):
        events = [
            SchedulerEvent(0, "WAKEUP", 101, -1, -1, -1, 120, -1, -1, 0, 0, 2),
            SchedulerEvent(0, "WAKEUP", 202, -1, -1, -1, 120, -1, -1, 0, 0, 3),
            SchedulerEvent(1, "SWITCH", -1, 0, 101, 0, -1, 120, 120, 0, -1, 4),
            SchedulerEvent(10, "SWITCH", -1, 101, 202, 0, -1, 120, 120, 0, -1, 5),
            SchedulerEvent(20, "SWITCH", -1, 202, 101, 0, -1, 120, 120, 0, -1, 6),
            SchedulerEvent(30, "SWITCH", -1, 101, 202, 0, -1, 120, 120, 0, -1, 7),
        ]
        metadata = {
            101: {"workload_class": "batch", "nice_value": 0, "scheduler_policy": "SCHED_OTHER"},
            202: {"workload_class": "interactive", "nice_value": 0, "scheduler_policy": "SCHED_OTHER"},
        }

        result = analyze_delta_windows(events, metadata, 31, cpu_count=1, window_ns=10)

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["window_counts"]["full_after_warmup"], 2)
        self.assertEqual([row["start_ns"] for row in result["windows"]], [10, 20])
        self.assertEqual(result["windows"][0]["delta_interactive_to_batch"], 1.0)
        self.assertEqual(result["windows"][1]["delta_batch_to_interactive"], 1.0)

    def test_unverified_scheduler_policy_makes_metric_unavailable(self):
        result = analyze_delta_windows(
            [SchedulerEvent(0, "WAKEUP", 101, -1, -1, -1, 120, -1, -1, 0, 0, 2)],
            {101: {"workload_class": "batch", "nice_value": 0, "scheduler_policy": None}},
            100,
            cpu_count=1,
            window_ns=10,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("not verified", result["reason"])


if __name__ == "__main__":
    unittest.main()
