"""Strict parser for the initial scheduler trace TSV schema."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


EVENT_COLUMNS = (
    "timestamp_ns",
    "event",
    "tid",
    "prev_tid",
    "next_tid",
    "prev_state",
    "prio",
    "prev_prio",
    "next_prio",
    "cpu",
    "target_cpu",
)


class TraceParseError(ValueError):
    """A malformed event line; raw trace files are left untouched."""


@dataclass(frozen=True)
class SchedulerEvent:
    timestamp_ns: int
    event: str
    tid: int
    prev_tid: int
    next_tid: int
    prev_state: int
    prio: int
    prev_prio: int
    next_prio: int
    cpu: int
    target_cpu: int
    line_number: int


def parse_trace_stream(stream: TextIO) -> tuple[list[SchedulerEvent], int | None]:
    """Parse TSV scheduler records and return events plus END timestamp."""
    reader = csv.DictReader(stream, delimiter="\t")
    if tuple(reader.fieldnames or ()) != EVENT_COLUMNS:
        raise TraceParseError(f"unexpected TSV header: {reader.fieldnames!r}")
    events: list[SchedulerEvent] = []
    end_timestamp: int | None = None
    for line_number, row in enumerate(reader, start=2):
        if None in row or any(value is None for value in row.values()):
            raise TraceParseError(f"line {line_number}: wrong number of columns: {row!r}")
        try:
            timestamp = int(row["timestamp_ns"])
            kind = row["event"]
            if kind == "END":
                if end_timestamp is not None:
                    raise ValueError("duplicate END marker")
                end_timestamp = timestamp
                continue
            if kind not in {"WAKEUP", "SWITCH"}:
                raise ValueError(f"unsupported event type {kind!r}")
            values = {key: int(row[key]) for key in EVENT_COLUMNS if key not in {"event", "timestamp_ns"}}
        except (TypeError, ValueError) as exc:
            raise TraceParseError(f"line {line_number}: {exc}; raw={row!r}") from exc
        events.append(
            SchedulerEvent(
                timestamp_ns=timestamp,
                event=kind,
                line_number=line_number,
                **values,
            )
        )
    return events, end_timestamp


def read_trace(path: str | Path) -> tuple[list[SchedulerEvent], int | None]:
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        return parse_trace_stream(stream)
