import io
import unittest

from cpu_fairness.telemetry.parser import EVENT_COLUMNS, TraceParseError, parse_trace_stream


class TraceParserTests(unittest.TestCase):
    def test_parses_records_and_end_timestamp(self):
        header = "\t".join(EVENT_COLUMNS)
        wake = "100\tWAKEUP\t101\t-1\t-1\t-1\t120\t-1\t-1\t0\t0"
        end = "900\tEND\t-1\t-1\t-1\t-1\t-1\t-1\t-1\t-1\t-1"
        events, end_timestamp = parse_trace_stream(io.StringIO(f"{header}\n{wake}\n{end}\n"))
        self.assertEqual(events[0].tid, 101)
        self.assertEqual(events[0].timestamp_ns, 100)
        self.assertEqual(end_timestamp, 900)

    def test_malformed_record_is_not_silently_discarded(self):
        header = "\t".join(EVENT_COLUMNS)
        with self.assertRaisesRegex(TraceParseError, "line 2"):
            parse_trace_stream(io.StringIO(f"{header}\n100\tWAKEUP\tbad\n"))

    def test_unknown_event_is_rejected(self):
        header = "\t".join(EVENT_COLUMNS)
        row = "100\tMAP\t-1\t-1\t-1\t-1\t-1\t-1\t-1\t-1\t-1"
        with self.assertRaisesRegex(TraceParseError, "unsupported event"):
            parse_trace_stream(io.StringIO(f"{header}\n{row}\n"))


if __name__ == "__main__":
    unittest.main()
