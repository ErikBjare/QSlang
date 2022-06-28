#!/bin/env python3
"""
A reimplementation of the (somewhat broken) pop-regex parser.
We will use the parsimonious library to parse the string.
We will comment step by step how the parser works.
"""

import logging
import pytest
from typing import List, Dict, Any, Generator, Iterator
from datetime import time, date, datetime, timedelta

import parsimonious
from parsimonious.nodes import Node, NodeVisitor

from .event import Event


logger = logging.getLogger(__name__)


def flatten(ls: List[Any]) -> List[Any]:
    """Flatten a list of lists."""
    if not isinstance(ls, list):
        raise TypeError("Expected a list")
    return [item for sublist in ls for item in sublist]


# Step 1: Create a parsimonious grammar
# We will use a simple grammar that will parse the following string:
#   "1x Something (50mg Caffeine + 100mg L-Theanine)"
# The grammar is a series of rules, each of which is a sequence of tokens.
grammar = parsimonious.Grammar(
    r"""
    entries     = day_header? ws (entry (nl entry)*)?

    day_header  = '#' ws date
    entry       = time_prefix* time ws "-" ws entry_data
    entry_data  = dose_list / note
    note        = ~"[A-Z][^,)\n]+"i

    date        = ~"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}"
    time_prefix = approx / next_day
    time        = ~"[0-9]{1,2}:[0-9]{1,2}"
    ws          = ~"\s*"
    nl          = "\n"+

    dose        = amount ws substance ws extra? ws roa?
    dose_list   = dose (ws "+" ws dose)*
    amount      = (approx? number ws unit?) / (unknown ws unit?)
    number      = ~"[0-9]+[.]?[0-9]*"
    unit        = prefixlessunit / (siprefix? baseunit)
    prefixlessunit = "cup" / "x" / "IU" / "GDU"
    siprefix    = "n" / "u" / "mc" / "m" / "c" / "d"
    baseunit    = "g" / "l"
    substance   = ~"[A-Z][A-Za-z0-9\-]*"
    extra       = "(" extra_data (ws "," ws extra_data)* ")"
    extra_data  = dose_list / note
    roa         = ( "oral" / "vape" / "intranasal" / "subcutaneous" / "subl" )

    approx = "~"
    unknown = "?"
    next_day = "+"
    """
)


def parse(string, rule=None) -> Node:
    _grammar = grammar
    if rule is not None:
        _grammar = _grammar[rule]
    return _grammar.parse(
        string.strip(),
    )


def parse_entries(s: str) -> Generator[Node, None, None]:
    """
    Parse entries one by one, instead of as a whole.
    Returns a generator of ``parsimonious.nodes.Node`` objects, one for each entry.
    """
    for entry in s.split("\n"):
        entry = entry.strip()
        if entry:
            if entry[0] == "#":
                yield parse(entry, rule="day_header")
            else:
                yield parse(entry, rule="entry")


class Visitor(NodeVisitor):
    # def visit(self, node):
    #     if not isinstance(node, Node):
    #         print(node)
    #     return super().visit(node)

    def generic_visit(self, node, visited_children) -> List:
        if node.expr_name:
            print("GENERIC HIT:", node.expr_name, visited_children)
        return visited_children

    def visit_ws(self, node, visited_children) -> None:
        return None

    def visit_nl(self, node, visited_children) -> None:
        return None

    def visit_approx(self, node, visited_children) -> str:
        # TODO: Annotate event object
        return "~"

    def visit_entries(self, node, visited_children) -> List[Event]:
        visited_children = [[c2 for c2 in c if c2] for c in visited_children if c]
        day = None

        # Check if first entry is day header
        if len(visited_children) > 0 and isinstance(visited_children[0][0], date):
            day = visited_children[0][0]
            del visited_children[0]

        # Parse all entries
        events: List[Event] = []
        for entry in visited_children[0]:
            event = entry[0]
            if event:
                assert isinstance(event, Event)
                if day:
                    event.timestamp = event.timestamp.combine(
                        day, event.timestamp.time()
                    )
                events.append(event)

        for e in events:
            assert isinstance(e, Event)

        return events

    def visit_entry(self, node, visited_children, day=None) -> Event:
        logger.warning(visited_children)
        _, time, _, _, _, entry_data = visited_children

        if day is None:
            logger.warning("No day specified for entry, assuming 1900-01-01")
            day = date(1900, 1, 1)

        timestamp = datetime.combine(day, time)
        return Event(
            timestamp=timestamp,
            type="dose",
            data=entry_data,
        )

    def visit_entry_data(self, node, visited_children) -> Dict[str, Any]:
        assert len(visited_children) == 1
        assert len(visited_children[0]) == 1
        dose = visited_children[0][0]
        assert "substance" in dose
        return dose

    def visit_extra_data(self, node, visited_children) -> Dict:
        _notes = []
        _subdoses = []
        for child in visited_children:
            if isinstance(child, dict):
                _notes.append(child)
            elif isinstance(child, list):
                _subdoses.extend(child)
            else:
                raise ValueError(f"Unknown child type: {child}")

        for c in _notes:
            assert "note" in c
        for c in _subdoses:
            assert "substance" in c

        print("subdoses", _subdoses)
        extra_data = {"notes": _notes, "subdoses": _subdoses}
        print("extra_data", extra_data)
        return extra_data

    def visit_dose_list(self, node, visited_children) -> List[Dict[str, Any]]:
        print("\nvisit_dose_list:")
        print(visited_children)
        doses = [visited_children.pop(0)]
        visited_children = flatten(visited_children)
        for c in visited_children:
            if c:
                _, _, _, dose = c
                doses.append(dose)

        assert all(isinstance(d, dict) for d in doses)
        return doses

    def visit_dose(self, node, visited_children) -> Dict[str, Any]:
        dose, _, substance, a1, extras, a2, roa = visited_children
        assert a1 is None
        assert a2 is None
        d = {
            "substance": substance,
            "dose": {**dose},
            "subdoses": [],
            "notes": [],
        }

        if roa:
            d["dose"]["roa"] = roa[0]

        if extras:
            print("")
            print("extras:")
            # notes, *subdoses = extras
            for e in extras:
                print(f" - {e}")
                d["notes"].extend(e["notes"])
                d["subdoses"].extend(e["subdoses"])

        if not d["notes"]:
            del d["notes"]
        if not d["subdoses"]:
            del d["subdoses"]

        return d

    def visit_day_header(self, node, visited_children) -> date:
        day = visited_children[2]
        assert isinstance(day, date)
        return day

    def visit_date(self, node, visited_children) -> date:
        return datetime.strptime(node.text, "%Y-%m-%d").date()

    def visit_time(self, node, visited_children) -> time:
        return datetime.strptime(node.text, "%H:%M").time()

    def visit_extra(self, node, visited_children) -> List:
        logger.warning(visited_children)
        _, extra, *more = visited_children
        if more:
            more, _ = more
            assert _ == []
            for c in more:
                logger.warning(f" - {c}")
                _, _, _, more_extra = c
                extra["notes"].extend(more_extra["notes"])
                extra["subdoses"].extend(more_extra["subdoses"])

        return extra

    def visit_note(self, node, visited_children) -> dict:
        return {"note": node.text}

    def visit_siprefix(self, node, visited_children) -> str:
        return node.text

    def visit_baseunit(self, node, visited_children) -> str:
        return node.text

    def visit_amount(self, node, visited_children) -> Dict[str, Any]:
        assert len(visited_children) == 1
        (_, amount, _, unit) = visited_children[0]
        return {"amount": amount, "unit": unit[0]}

    def visit_unit(self, node, visited_children) -> str:
        return node.text

    def visit_prefixlessunit(self, node, visited_children) -> str:
        return node.text

    def visit_number(self, node, visited_children) -> float:
        return float(node.text)

    def visit_substance(self, node, visited_children) -> str:
        return node.text

    def visit_roa(self, node, visited_children) -> str:
        return node.text


def parse_with_visitor(s: str) -> List[Event]:
    visitor = Visitor()
    visitor.grammar = grammar
    return visitor.parse(s.strip())


def test_parse_with_visitor_simple():
    print("Simple example, no day header")
    s = """09:30 - 1 cup Coffee oral"""
    parsed = parse_with_visitor(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(1900, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"
    assert parsed[0].data["dose"] == {"amount": 1, "unit": "cup", "roa": "oral"}


def test_parse_with_visitor_header():
    print("\nHeader example")
    s = """
    # 2020-01-01

    09:30 - 1 cup Coffee
    """
    parsed = parse_with_visitor(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(2020, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"


def test_parse_with_visitor_subdoses():
    print("\nSubdoses example")
    s = """
    09:30 - 1 cup Coffee (100mg Caffeine + 50mg L-Theanine)
    """
    parsed = parse_with_visitor(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(1900, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"
    assert parsed[0].data.get("subdoses", []) == [
        {"substance": "Caffeine", "dose": {"amount": 100, "unit": "mg"}},
        {"substance": "L-Theanine", "dose": {"amount": 50, "unit": "mg"}},
    ]


def test_parse_with_visitor_complex():
    print("\nComplex example")
    # Complex example
    s = """
    09:30 - 1 cup Coffee (strong, milk, ~100mg Caffeine + 50mg L-Theanine + 1mg LOL)
    """
    parsed = parse_with_visitor(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(1900, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"
    assert parsed[0].data.get("notes", []) == [
        {"note": "strong"},
        {"note": "milk"},
    ]
    assert parsed[0].data.get("subdoses", []) == [
        {"substance": "Caffeine", "dose": {"amount": 100, "unit": "mg"}},
        {"substance": "L-Theanine", "dose": {"amount": 50, "unit": "mg"}},
        {"substance": "LOL", "dose": {"amount": 1, "unit": "mg"}},
    ]


def parsed_to_event(day: date, parsed: Node) -> Event:
    dt = datetime.combine(
        day, datetime.strptime(parsed.children[1].text, "%H:%M").time()
    )
    _type = "dose"  # TODO: parse type
    content = parsed.children[5].text
    assert content
    data = {"raw": content}
    return Event(dt, _type, data)


def parsed_to_events(parsed: Iterator[Node]) -> List[Event]:
    """Convert a list of parsed entries to a list of events."""
    events: List[Event] = []
    day = None
    for entry in parsed:
        print(entry.prettily())
        if day is None:
            assert entry.expr_name == "day_header"
            day = datetime.strptime(entry.children[2].text, "%Y-%m-%d").date()
        else:
            events.append(parsed_to_event(day, entry))
    return events


def test_parse_event():
    s = "# 2020-01-01\n09:30 - 1x Something (50mg Caffeine + 100mg L-Theanine)"
    parsed = parsed_to_events(parse_entries(s))
    print(parsed)


@pytest.mark.run(order=0)
def test_parse_dayheader():
    assert parse("# 2020-1-1", rule="day_header")
    assert parse("# 2020-01-01", rule="day_header")


@pytest.mark.run(order=0)
def test_parse_entry():
    assert parse("10:00 - 100mg Caffeine", rule="entry")
    assert parse("10:00 - 1 cup Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_entries():
    entries = parse_entries("10:00 - 100mg Caffeine")
    for entry in entries:
        print(entry.prettily())

    entries = parse_entries("10:00 - 1 cup Coffee\n\n11:00 - 50mg Caffeine")
    for entry in entries:
        print(entry.prettily())


@pytest.mark.run(order=0)
def test_parse_entries_full():
    assert parse("10:00 - 100mg Caffeine", rule="entries")
    # Not working, not sure why
    # assert parse("10:00 - 1 cup Coffee\n\n11:00 - 50mg Caffeine", rule="entries")


@pytest.mark.run(order=0)
def test_parse_unknown():
    assert parse("10:00 - ?dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_approx_time():
    assert parse("~10:00 - 1dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_approx_amount():
    assert parse("10:00 - ~1dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_next_day():
    assert parse("+01:00 - 0.5mg Melatonin", rule="entry")


@pytest.mark.run(order=0)
def test_parse_extra():
    assert parse("(100mg Caffeine + 200mg L-Theanine)", rule="extra")


def test_parse_multivit():
    s = "09:00 - 1x Multivitamin (100mg Magnesium (from Citrate) + 10mg Zinc (from Picolinate))"
    parsed = parse(s)
    assert parsed


def test_parse_recursive():
    s = "09:30 - 1x Something (2x Something-Else (10mg Substance-A + 10mg Substance-B) + 10mg Substance-C) oral"
    parsed = parse(s)
    assert parsed


def test_parse_notes():
    s = """
    09:30 - Just a plain note

    09:40 - 1x Something (with a note)
    """
    parsed = list(parse_entries(s))
    assert parsed


def test_parse_day_example():
    s = """
    # 2020-01-01

    09:30 - 1 cup Coffee (100mg Caffeine + 50mg L-Theanine)

    21:30 - 0.5mg Melatonin subl
    """
    parsed = list(parse_entries(s))
    for entry in parsed:
        print(entry.prettily())
