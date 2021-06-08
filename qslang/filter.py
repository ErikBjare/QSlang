from typing import List
from datetime import datetime

from qslang import Event


def filter_events_by_args(events: List[Event], args: List[str]) -> List[Event]:
    if not args:
        print("Missing argument")

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


def test_filter_events_by_args() -> None:
    events = [
        Event(datetime.now(), "dose", {"substance": "test"}),
        Event(datetime.now(), "dose", {"substance": "test2"}),
    ]
    res = filter_events_by_args(events, ["test"])
    assert len(res) == 1


def filter_events(events, start=None, end=None, substances=[]):
    if start:
        events = [e for e in events if e.timestamp >= start]
    if end:
        events = [e for e in events if e.timestamp <= end]
    if substances:
        events = filter_events_by_args(events, substances)
    return events
