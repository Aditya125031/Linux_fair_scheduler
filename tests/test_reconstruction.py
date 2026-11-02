import unittest

from cpu_fairness.analysis.reconstruction import reconstruct
from cpu_fairness.telemetry.parser import SchedulerEvent


def event(timestamp, kind, *, tid=-1, prev=-1, next_=-1, state=-1, line=1):
    return SchedulerEvent(
        timestamp_ns=timestamp,
        event=kind,
        tid=tid,
        prev_tid=prev,
        next_tid=next_,
        prev_state=state,
        prio=-1,
        prev_prio=-1,
        next_prio=-1,
        cpu=0,
        target_cpu=-1,
        line_number=line,
    )


class ReconstructionTests(unittest.TestCase):
    def test_wakeup_to_schedule_wait_is_reconstructed(self):
        events = [
            event(100, "WAKEUP", tid=101, line=1),
            event(350, "SWITCH", prev=200, next_=101, state=1, line=2),
            event(500, "SWITCH", prev=101, next_=200, state=1, line=3),
        ]
        waits, tasks, warnings = reconstruct(events, {101}, 600)
        self.assertEqual(waits[0].wait_ns, 250)
        self.assertTrue(waits[0].complete)
        self.assertEqual(tasks[101].cpu_service_ns, 150)
        self.assertEqual(warnings, [])

    def test_runnable_preemption_to_reschedule_wait(self):
        events = [
            event(400, "SWITCH", prev=200, next_=101, state=1, line=1),
            event(500, "SWITCH", prev=101, next_=200, state=0, line=2),
            event(800, "SWITCH", prev=200, next_=101, state=1, line=3),
            event(900, "SWITCH", prev=101, next_=200, state=1, line=4),
        ]
        waits, tasks, warnings = reconstruct(events, {101}, 950)
        self.assertEqual(waits[0].wait_ns, 300)
        self.assertEqual(tasks[101].cpu_service_ns, 200)
        self.assertEqual(warnings, [])

    def test_duplicate_wakeup_keeps_original_ready_time(self):
        events = [
            event(100, "WAKEUP", tid=101, line=1),
            event(150, "WAKEUP", tid=101, line=2),
            event(350, "SWITCH", prev=200, next_=101, state=1, line=3),
        ]
        waits, _tasks, warnings = reconstruct(events, {101}, 400)
        self.assertEqual(waits[0].wait_ns, 250)
        self.assertIn("duplicate wakeup", warnings[0])

    def test_unfinished_wait_is_censored_not_complete(self):
        waits, _tasks, _warnings = reconstruct(
            [event(100, "WAKEUP", tid=101)], {101}, 200
        )
        self.assertEqual(waits[0].wait_ns, 100)
        self.assertFalse(waits[0].complete)
        self.assertEqual(waits[0].reason, "trace_end_censored")

    def test_running_interval_at_trace_end_is_marked_incomplete(self):
        events = [event(150, "SWITCH", prev=200, next_=101, state=1)]
        _waits, tasks, _warnings = reconstruct(events, {101}, 200)
        self.assertEqual(tasks[101].cpu_service_ns, 50)
        self.assertEqual(tasks[101].incomplete_service_intervals, 1)


if __name__ == "__main__":
    unittest.main()
