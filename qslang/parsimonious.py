#!/bin/env python3
"""
A reimplementation of the (somewhat broken) pop-regex parser.
We will use the parsimonious library to parse the string.
We will comment step by step how the parser works.
"""

import logging
from collections.abc import Generator
from datetime import (
    date,
    datetime,
    time,
    timedelta,
)
from typing import Any

import parsimonious
from parsimonious.nodes import Node, NodeVisitor

from .event import Event

logger = logging.getLogger(__name__)


def flatten(ls: list[Any]) -> list[Any]:
    """Flatten a list of lists."""
    if not isinstance(ls, list):
        raise TypeError("Expected a list")
    return [item for sublist in ls for item in sublist]


class ParseError:
    def __init__(self, e: BaseException, s: str, date: str):
        self.e = e
        self.s = s
        self.date = date

    def __repr__(self):
        return f"<ParseError: {self.e}, string: {self.s}, date: {self.date}>"


# Step 1: Create a parsimonious grammar
# We will use a simple grammar that will parse the following string:
#   "08:20 - 1x Something (50mg Caffeine + 100mg L-Theanine)"
# The grammar is a series of rules, each of which is a sequence of tokens.
grammar = parsimonious.Grammar(
    r"""
    entries     = day_header? ws (entry)*

    day_header  = '#' ws date (ws "-" ws ~"[a-z0-9 ]+"i)? nl?
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
    amount      = (unknown ws unit?) / (approx? fraction ws unit?) / (approx? number ws unit?)
    number      = ~"[0-9]+[.]?[0-9]*"
    unit        = prefixlessunit / (siprefix? baseunit)
    prefixlessunit = "cup" / "x" / "IU" / "GDU" / "B" / "serving" / ~"puff(s)?"
    siprefix    = "n" / "u" / "mc" / "m" / "c" / "d"
    baseunit    = "g" / "l"
    substance   = ~"[a-z0-9\-äåö]+"i (ws !roa ~"[a-z0-9\-åäö]+"i)*
    extra       = "(" extra_data (ws "," ws extra_data)* ")"
    extra_data  = percent / dose_list / short_note
    short_note  = ratio? ws ~"[A-Z][^,)\n]+"i?
    ratio       = ~"[0-9]+:[0-9]+"
    fraction    = ~"[0-9]+\/[0-9]+"
    percent     = ~"[>]"? number "%" ws substance?
    roa         = "oral" / ~"vap(ed|orized)?" / "intranasal" / ~"insuff(lated)?" / ~"subcut(aneous)?" / ~"subl(ingual)?" / "smoked" / "spliff" / "inhaled" / "buccal" / "rectal"

    approx = "~"
    unknown = "?"
    next_day = "+"
    """
)


def parse(s: str) -> list[Event]:
    visitor = Visitor()
    visitor.grammar = grammar
    events: list[Event] = visitor.parse(s.strip())  # type: ignore
    return events


def parse_defer_errors(s: str) -> tuple[list[Event], list[ParseError]]:
    """
    Tries to parse strings into a list of events.
    If some entries can't be read: store the resulting errors in a list.

    returns both the events and errors.
    """
    entries: list[Event | ParseError] = _parse_continue_on_err(s)
    events = []
    errors = []
    for e in entries:
        if isinstance(e, Event):
            events.append(e)
        elif isinstance(e, ParseError):
            # logger.warning(f"Error while parsing: {e}")
            errors.append(e)
        else:
            print(e)
            raise TypeError(f"Unexpected type: {type(e)}")
    # check how many have 1900-1-1 as date
    n_no_date = len([e for e in events if e.timestamp.date() <= date(1901, 1, 1)])
    if n_no_date:
        logger.warning(f"{n_no_date} events have no date")
    return events, errors


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
    def generic_visit(self, node, visited_children) -> list:
        if node.expr_name:
            logger.warning(f"GENERIC HIT: {node.expr_name}   {visited_children}")
        return visited_children

    def visit_entries(self, node, visited_children) -> list[Event]:
        day_header, _, entries = visited_children
        day = None

        # Check if first entry is day header
        if day_header:
            (day,) = day_header
            assert isinstance(day, date)

        # Parse all entries
        events: list[Event] = []
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

    def visit_entry(self, node, visited_children, day=None) -> list[Event]:
        _, time_prefix, time, _, _, _, entries, _, _ = visited_children

        if day is None:
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
                    type="dose" if "substance" in data else "journal",
                    data=data,
                )
            )
        return events

    def visit_day_header(self, node, visited_children) -> date:
        _, _, day, *_ = visited_children
        assert isinstance(day, date)
        return day

    def visit_approx(self, node, visited_children) -> str:
        return "approx"

    def visit_next_day(self, node, visited_children) -> str:
        return "next_day"

    def visit_unknown(self, node, visited_children) -> str:
        return "unknown"

    def visit_entry_data(self, node, visited_children) -> list[dict[str, Any]]:
        doses_or_note = visited_children[0]
        if isinstance(doses_or_note, list):
            return doses_or_note
        elif isinstance(doses_or_note, dict):
            return [doses_or_note]
        else:
            raise ValueError(f"Unknown entry data: {doses_or_note}")

    def visit_extra_data(self, node, visited_children) -> dict:
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

    def visit_dose_list(self, node, visited_children) -> list[dict[str, Any]]:
        first_dose, more_doses = visited_children
        doses = [first_dose]
        for c in more_doses:
            if c:
                _, _, _, dose = c
                doses.append(dose)

        assert all(isinstance(d, dict) for d in doses)
        return doses

    def visit_dose(self, node, visited_children) -> dict[str, Any]:
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

    def visit_extra(self, node, visited_children) -> list:
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

    def visit_ratio(self, node, visited_children) -> str:
        return node.text

    def visit_siprefix(self, node, visited_children) -> str:
        return node.text

    def visit_baseunit(self, node, visited_children) -> str:
        return node.text

    def visit_amount(self, node, visited_children) -> dict[str, Any]:
        visited_children = visited_children[0]
        if len(visited_children) == 4:
            (approx, amount, _, unit) = visited_children
            d = {
                "amount": amount,
                "unit": unit[0] if unit else "unknown",
            }
            if approx:
                d["approx"] = True
            return d
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

    def visit_percent(self, node, visited_children) -> dict[str, Any]:
        return {"note": node.text}

    def visit_fraction(self, node, visited_children) -> float:
        return eval(node.text)

    def visit_time_prefix(self, node, visited_children) -> str:
        return visited_children

    def visit_ws(self, node, visited_children) -> None:
        return None

    def visit_nl(self, node, visited_children) -> None:
        return None


def _parse_continue_on_err(s: str) -> list[Event | ParseError]:
    """
    We want to parse events row by row, so we can handle errors (which ``parse`` cannot).

    To do this, we need to parse line by line, returning errors with correct timestamps
    determined by previous day header. If an event cannot be read, return an 'ParseError'
    instead, for filtering by the caller.
    """
    entries: list[Event | ParseError] = []
    day_header = ""
    for line in s.splitlines():
        line = line.strip()

        # skip empty lines
        if not line:
            continue

        if line.startswith("# 20"):  # assumption will break for dates >=2100-1-1
            day_header = line
            continue

        try:
            events = parse(day_header + "\n" + line)
            if events:
                entries.extend(events)
        except Exception as e:
            # Useful in testing to get stacktraces
            # logger.exception(e)
            entries.append(ParseError(e, line, day_header[2:]))

    return entries
