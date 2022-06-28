from typing import List
from datetime import datetime

from qslang import Event


def filter_events_by_args(events: List[Event], args: List[str]) -> List[Event]:
    if not args:
        raise ValueError("Missing argument")

    matches = []
    for e in events:
        for arg in args:
            if (e.substance and e.substance.lower() == arg.lower()) or (
                arg[0] == "#"
                and arg.strip("#").lower() in set(map(lambda t: t.lower(), e.tags))
            ):
                matches.append(e)
                break
    return matches


def filter_events(events, start=None, end=None, substances=[]):
    if start:
        events = [e for e in events if e.timestamp >= start]
    if end:
        events = [e for e in events if e.timestamp <= end]
    if substances:
        events = filter_events_by_args(events, substances)
    return events


def test_filter_events_by_args() -> None:
    events = [
        Event(datetime.now(), "dose", {"substance": "test"}),
        Event(datetime.now(), "dose", {"substance": "test2"}),
    ]
    res = filter_events_by_args(events, ["test"])
    assert len(res) == 1


def test_filter_subst_with_space() -> None:
    events = [
        Event(datetime.now(), "dose", {"substance": "cannabis oil"}),
    ]
    res = filter_events_by_args(events, ["cannabis oil"])
    assert len(res) == 1
