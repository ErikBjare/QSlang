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
#   "08:20 - 1x Something (50mg Caffeine + 100mg L-Theanine)"
# The grammar is a series of rules, each of which is a sequence of tokens.
grammar = parsimonious.Grammar(
    r"""
    entries     = day_header? ws (entry)*

    day_header  = '#' ws date nl?
    entry       = ws time_prefix* time ws "-" ws entry_data ws nl?
    entry_data  = dose_list / note
    note        = ~"[A-Z][^\n]+"i

    date        = ~"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}"
    time        = ~"[0-9?]{1,2}:[0-9?]{1,2}"
    time_prefix = approx / next_day

    ws          = ~"[ ]*"
    nl          = ~"\n+"

    dose        = patient? ws amount ws substance ws extra? ws roa?
    dose_list   = dose (ws "+" ws dose)*
    patient     = "{" ~"[a-z]+"i "}"
    amount      = (approx? number ws unit?) / (unknown ws unit?)
    number      = ~"[0-9]+[.]?[0-9]*"
    unit        = prefixlessunit / (siprefix? baseunit)
    prefixlessunit = "cup" / "x" / "IU" / "GDU" / "serving"
    siprefix    = "n" / "u" / "mc" / "m" / "c" / "d"
    baseunit    = "g" / "l"
    substance   = ~"[a-z0-9\-]+"i (ws !roa ~"[a-z0-9\-]+"i)*
    extra       = "(" extra_data (ws "," ws extra_data)* ")"
    extra_data  = dose_list / short_note / percent
    short_note  = ~"[A-Z][^,)\n]+"i
    percent     = number "%" ws substance?
    roa         = "oral" / "vape" / "vaporized" / "intranasal" / "insufflated" / "subcutaneous" / "subl" / "smoked" / "spliff"

    approx = "~"
    unknown = "?"
    next_day = "+"
    """
)


def parse(s: str) -> List[Event]:
    visitor = Visitor()
    visitor.grammar = grammar
    return visitor.parse(s.strip())


def parse_to_node(string, rule=None) -> Node:
    _grammar = grammar
    if rule is not None:
        _grammar = _grammar[rule]
    return _grammar.parse(
        string,
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
                yield parse_to_node(entry, rule="day_header")
            else:
                yield parse_to_node(entry, rule="entry")


class Visitor(NodeVisitor):
    def generic_visit(self, node, visited_children) -> List:
        if node.expr_name:
            logger.warning(f"GENERIC HIT: {node.expr_name}   {visited_children}")
        return visited_children

    def visit_entries(self, node, visited_children) -> List[Event]:
        day_header, _, entries = visited_children
        day = None

        # Check if first entry is day header
        if day_header:
            (day,) = day_header
            assert isinstance(day, date)

        # Parse all entries
        events: List[Event] = []
        for entry in entries:
            for event in entry:
                if event:
                    assert isinstance(event, Event)
                    if day:
                        event.timestamp = event.timestamp.combine(
                            day, event.timestamp.time()
                        )
                    if event.data.pop("next_day", None):
                        event.timestamp += timedelta(days=1)
                    events.append(event)

        for e in events:
            assert isinstance(e, Event)

        return events

    def visit_entry(self, node, visited_children, day=None) -> List[Event]:
        _, time_prefix, time, _, _, _, entries, _, _ = visited_children

        if day is None:
            logger.warning("No day specified for entry, assuming 1900-01-01")
            day = date(1900, 1, 1)

        timestamp = datetime.combine(day, time)

        events = []
        for data in entries:
            for (p,) in time_prefix:
                if p == "next_day":
                    data["next_day"] = True
                elif p == "approx":
                    data["approx"] = True
                else:
                    raise ValueError(f"Unknown time prefix: {p}")

            events.append(
                Event(
                    timestamp=timestamp,
                    type="dose" if "substance" in data else "note",
                    data=data,
                )
            )
        return events

    def visit_day_header(self, node, visited_children) -> date:
        _, _, day, _ = visited_children
        assert isinstance(day, date)
        return day

    def visit_approx(self, node, visited_children) -> str:
        return "approx"

    def visit_next_day(self, node, visited_children) -> str:
        return "next_day"

    def visit_entry_data(self, node, visited_children) -> List[Dict[str, Any]]:
        doses_or_note = visited_children[0]
        if isinstance(doses_or_note, list):
            return doses_or_note
        elif isinstance(doses_or_note, dict):
            return [doses_or_note]
        else:
            raise ValueError(f"Unknown entry data: {doses_or_note}")

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

        extra_data = {"notes": _notes, "subdoses": _subdoses}
        return extra_data

    def visit_dose_list(self, node, visited_children) -> List[Dict[str, Any]]:
        first_dose, more_doses = visited_children
        doses = [first_dose]
        for c in more_doses:
            if c:
                _, _, _, dose = c
                doses.append(dose)

        assert all(isinstance(d, dict) for d in doses)
        return doses

    def visit_dose(self, node, visited_children) -> Dict[str, Any]:
        patient, _, dose, _, substance, a1, extras, a2, roa = visited_children
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
        if patient:
            d["patient"] = patient[0]

        if extras:
            for e in extras:
                d["notes"].extend(e["notes"])
                d["subdoses"].extend(e["subdoses"])

        if not d["notes"]:
            del d["notes"]
        if not d["subdoses"]:
            del d["subdoses"]

        return d

    def visit_date(self, node, visited_children) -> date:
        return datetime.strptime(node.text, "%Y-%m-%d").date()

    def visit_time(self, node, visited_children) -> time:
        if node.text == "??:??":
            logger.warning("Entry with unknown time, assuming 00:00")
            return time(0, 0)
        return datetime.strptime(node.text, "%H:%M").time()

    def visit_extra(self, node, visited_children) -> List:
        _, extra, *more = visited_children
        if more:
            more, _ = more
            assert _ == []
            for c in more:
                _, _, _, more_extra = c
                extra["notes"].extend(more_extra["notes"])
                extra["subdoses"].extend(more_extra["subdoses"])

        return extra

    def visit_note(self, node, visited_children) -> dict:
        return {"note": node.text}

    def visit_short_note(self, node, visited_children) -> dict:
        return {"note": node.text}

    def visit_siprefix(self, node, visited_children) -> str:
        return node.text

    def visit_baseunit(self, node, visited_children) -> str:
        return node.text

    def visit_amount(self, node, visited_children) -> Dict[str, Any]:
        visited_children = visited_children[0]
        if len(visited_children) == 4:
            (_, amount, _, unit) = visited_children
            return {"amount": amount, "unit": unit[0] if unit else "unknown"}
        elif len(visited_children) == 3:
            (_, amount, unit) = visited_children
            return {"amount": "unknown", "unit": unit[0] if unit else "unknown"}
        else:
            raise ValueError(f"Unknown amount: {visited_children}")

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

    def visit_patient(self, node, visited_children) -> str:
        return node.text[1:-1]

    def visit_percent(self, node, visited_children) -> Dict[str, Any]:
        return {"note": node.text}

    def visit_time_prefix(self, node, visited_children) -> str:
        return visited_children

    def visit_ws(self, node, visited_children) -> None:
        return None

    def visit_nl(self, node, visited_children) -> None:
        return None


# Tests parsing with visitor


def test_parse_notes():
    parsed = parse("09:00 - One journal entry\n\n10:00 - Another journal entry")
    assert len(parsed) == 2
    assert parsed[0].type == "note"
    assert parsed[0].data == {"note": "One journal entry"}
    assert parsed[1].type == "note"
    assert parsed[1].data == {"note": "Another journal entry"}


def test_parse_multidose():
    s = "09:00 - 100mg Caffeine + 200mg L-Theanine"
    assert parse(s)


def test_parse_multivit():
    s = "09:00 - 1x Multivitamin (100mg Magnesium (from Citrate) + 10mg Zinc (from Picolinate))"
    assert parse(s)


def test_parse_nested():
    s = "09:30 - 1x Something (2x Something-Else (10mg Substance-A + 10mg Substance-B) + 10mg Substance-C) oral"
    assert parse(s)


def test_parse_simple():
    print("Simple example, no day header")
    s = """09:30 - 1 cup Coffee oral"""
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(1900, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"
    assert parsed[0].data["dose"] == {"amount": 1, "unit": "cup", "roa": "oral"}


def test_parse_header():
    print("\nHeader example")
    s = """
    # 2020-01-01

    09:30 - 1 cup Coffee
    """
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(2020, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"


def test_parse_subdoses():
    print("\nSubdoses example")
    s = """
    09:30 - 1 cup Coffee (100mg Caffeine + 50mg L-Theanine)
    """
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(1900, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"
    assert parsed[0].data.get("subdoses", []) == [
        {"substance": "Caffeine", "dose": {"amount": 100, "unit": "mg"}},
        {"substance": "L-Theanine", "dose": {"amount": 50, "unit": "mg"}},
    ]


def test_parse_complex():
    print("\nComplex example")
    # Complex example
    s = """
    09:30 - 1 cup Coffee (strong, milk, ~100mg Caffeine + 50mg L-Theanine + 1mg LOL)
    """
    parsed = parse(s)
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


def test_parse_event():
    s = "# 2020-01-01\n09:30 - 1x Something (50mg Caffeine + 100mg L-Theanine)"
    print(parse(s))


def test_parse_alcohol():
    s = "# 2020-01-01\n18:30 - 4cl Gin (Tanqueray, 47%)"
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].data["notes"] == [{"note": "Tanqueray"}, {"note": "47%"}]


def test_parse_patient():
    parsed = parse("# 2020-01-01\n09:30 - 100mcg LSD\n09:30 - {F} 100mcg LSD")
    assert "patient" not in parsed[0].data
    assert parsed[1].data["patient"] == "F"


# Parse to node tests


@pytest.mark.run(order=0)
def test_parse_node_dayheader():
    assert parse_to_node("# 2020-1-1", rule="day_header")
    assert parse_to_node("# 2020-01-01", rule="day_header")


@pytest.mark.run(order=0)
def test_parse_node_entry():
    assert parse_to_node("10:00 - 100mg Caffeine", rule="entry")
    assert parse_to_node("10:00 - 1 cup Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_full():
    assert parse_to_node("10:00 - 100mg Caffeine", rule="entries")
    assert parse_to_node("10:00 - 1 cup Coffee\n11:00 - 50mg Caffeine", rule="entries")


@pytest.mark.run(order=0)
def test_parse_node_unknown():
    assert parse_to_node("10:00 - ?dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_approx_time():
    assert parse_to_node("~10:00 - 1dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_approx_amount():
    assert parse_to_node("10:00 - ~1dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_next_day():
    assert parse_to_node("+01:00 - 0.5mg Melatonin", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_extra():
    assert parse_to_node("(100mg Caffeine + 200mg L-Theanine)", rule="extra")


# Test parse entries


@pytest.mark.run(order=0)
def test_parse_entries():
    entries = list(parse_entries("10:00 - 100mg Caffeine"))
    assert len(entries) == 1

    entries = list(parse_entries("10:00 - 1 cup Coffee\n\n11:00 - 50mg Caffeine"))
    assert len(entries) == 2


def test_parse_notes():
    s = """
    09:30 - Just a plain note

    09:40 - 1x Something (with a note)
    """
    assert list(parse_entries(s))


def test_parse_day_example():
    s = """
    # 2020-01-01

    09:30 - 1 cup Coffee (100mg Caffeine + 50mg L-Theanine)

    21:30 - 0.5mg Melatonin subl
    """
    assert list(parse_entries(s))


def test_parse_next_day():
    s = """
    # 2017-06-08

    10:00 - 100mg Caffeine

    +00:30 - 0.5mg Melatonin subl
    """
    entries = parse(s)
    print(entries)
    assert len(entries) == 2
    assert entries[0].timestamp == datetime(2017, 6, 8, 10, 0)
    assert entries[1].timestamp == datetime(2017, 6, 9, 0, 30)
