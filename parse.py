#!/bin/env python3

import re
import logging
import typing
from typing import List, Dict, Any, Tuple, Optional
from datetime import time, datetime, timedelta

from event import Event


log = logging.getLogger(__name__)

re_date = re.compile(r"[0-9]+-[0-9]+-[0-9]+")
re_time = re.compile(r"[~+]*[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(r"[~≤<>=]?[?0-9\.]+(?:k|c|d|mc|m|u|n)?(?:l|L|g|IU|x| ?tb?sp|(?= ))\b")
re_extra = re.compile(r"[(].*[)]")
re_substance = re.compile(r"[-\w ]=")
re_roa = re.compile(r"\b(oral(?:ly)?|subcut\w*|smoked|vap(?:ed|o?r?i?z?e?d?)|spliff|chewed|buccal(?:ly)?|subl(?:ingual)?|rectal(?:ly)?|insuff(?:lated)?|intranasal|IM|intramuscular|IV|intravenous|topical|transdermal|drinked|balloon)\b")
re_concentration = re.compile(r"[?0-9\.]+%")


def _pop_regex(s: str, regex: typing.Pattern) -> Tuple[str, Optional[str]]:
    """pop first match of regex anywhere in string"""
    m = regex.findall(s)
    if m:
        popped = m[0]
        return s.replace(popped, "").strip(), popped
    else:
        return s, None


def test_pop_regex():
    s, match = _pop_regex("100mg", re_amount)
    assert match
    assert not s


def _dict_pop_None(d: Dict):
    """pops keys with value None in-place"""
    keys_None = [k for k in d if d[k] is None]
    for k in keys_None:
        d.pop(k)


def parse_data(data: str) -> List[Dict[str, Any]]:
    datas = []
    if re_amount.match(data):
        # regexp matches all plusses or commas not within parens or brackets
        # taken from: https://stackoverflow.com/a/26634150/965332
        for entry in (e for e in re.split(r'[+,]\s*(?![^()]*\))', data)):
            d: Dict[str, Any] = {"raw": entry}
            entry, d["amount"] = _pop_regex(entry, re_amount)
            entry, d["roa"] = _pop_regex(entry, re_roa)
            entry, extra = _pop_regex(entry, re_extra)
            if extra:
                extra = d["raw_extra"] = extra.strip("()")
                d["subevents"] = []
                d["attributes"] = [a.strip() for a in extra.split(",")]
                for attribute in d["attributes"]:
                    subevents = parse_data(attribute)
                    if subevents:
                        d["subevents"].extend(subevents)
                    _, concentration = _pop_regex(attribute, re_concentration)
                    if concentration:
                        d["concentration"] = concentration

            d["substance"] = entry.strip("\\").strip().strip(")")

            datas.append(d)
            if "subevents" in d:
                datas.extend(d["subevents"])

    # Remove None data fields
    for d in datas:
        _dict_pop_None(d)

    return datas


def parse_time(s: str) -> Tuple[time, List[str]]:
    tags = []
    s = s.split(" ")[0]
    if "+" in s:
        tags.append("time-tomorrow")
    if "~" in s:
        tags.append("time-approximate")
    s = s.strip("+~").strip("+").strip("~")
    # Remove extra +01:00
    s = s.split("+")[0]
    # Remove eventual second precision
    s = ":".join(s.split(":")[:2])
    try:
        t = datetime.strptime(s, "%H:%M").time()
    except ValueError as e:
        log.warning(f"Tried to parse time: {s}")
        raise e
    return t, tags


def parse(text: str) -> List[Event]:
    now = datetime.now()
    events = []  # type: List[Event]

    current_date = None
    for line in text.split("\n"):
        line = line.strip()
        if line:
            if line[0] == "#":
                try:
                    current_date = datetime.strptime(line[1:].strip().split(" - ")[0], "%Y-%m-%d")
                except Exception as e:
                    log.debug(f"Unable to parse date: {e}")
            elif re_time.match(line):
                if not current_date:
                    log.warning("Date unknown, skipping")
                    continue

                try:
                    t, tags = parse_time(line.split("-")[0].strip())
                except ValueError:
                    continue

                timestamp = datetime.combine(current_date.date(), t)
                if "time-tomorrow" in tags:
                    timestamp += timedelta(days=1)

                # Check if timestamp is in future (likely result of date in the future)
                if timestamp > now:
                    log.warning("Timestamp was in the future")

                data = "-".join(line.split("-")[1:]).strip()
                if re_amount.match(data):
                    # Data entry
                    for entry in parse_data(data):
                        events.append(Event(timestamp, "data", entry))
                else:
                    # Journal entry
                    events.append(Event(timestamp, "journal", {"raw": data}))
            elif line:
                log.debug(f"Couldn't identify line-type: {line}")

    return events


def test_parse():
    test1 = """
    # 2018-04-14
    16:30 - Started working on qslang
    ~17:12 - Made progress
    18:12 - ~1dl Green tea + 5g Cocoa
    """
    events = parse(test1)
    assert len(events) == 4
    assert events[0].timestamp == datetime(2018, 4, 14, 16, 30)
    assert events[0].data["raw"] == "Started working on qslang"

    assert events[1].timestamp == datetime(2018, 4, 14, 17, 12)
    assert events[1].data["raw"] == "Made progress"

    assert events[2].substance == "Green tea"
    assert events[2].amount == "1dl"

    assert events[3].substance == "Cocoa"
    assert events[3].amount == "5g"


def test_parse_amount():
    test_str = """
    # 2018-04-14
    12:00 - 30 situps
    12:01 - 30x situps
    12:02 - 2tbsp sugar
    """
    events = parse(test_str)
    assert len(events) == 3
    assert events[0].amount == "30"
    assert events[1].amount == "30x"
    assert events[2].amount == "2tbsp"


def test_parse_roa():
    test_str = """
    # 2018-04-14
    12:00 - 1x Otrivin intranasal
    12:01 - 1x Somethingwithoralinit subcutaneous
    """
    events = parse(test_str)
    assert len(events) == 2
    assert events[0].substance == "Otrivin"
    assert events[0].roa == "intranasal"
    assert events[1].substance == "Somethingwithoralinit"
    assert events[1].roa == "subcutaneous"


def test_parse_with_plus_in_extras():
    test_str = """
    # 2018-04-14
    12:00 - 1x Something (50mg Caffeine + 100mg L-Theanine)
    """
    events = parse(test_str)
    assert len(events) == 3

    assert events[0].substance == "Something"
    assert events[0].amount == "1x"

    assert events[1].substance == "Caffeine"
    assert events[1].amount == "50mg"

    assert events[2].substance == "L-Theanine"
    assert events[2].amount == "100mg"


def test_alcoholic_drink():
    test_str = """
    # 2018-08-18
    ~21:00 - 33cl Beer (Pistonhead Kustom Lager, 5.9%)
    """
    events = parse(test_str)
    assert events[0].data["concentration"] == "5.9%"
    assert len(events) == 1


def test_complex_extras():
    test_str = """
    # 2018-08-20
    08:00 - 1x Generic Multivitamin (Generic Brand, 1000IU Vitamin D3 + 25mg Zinc Picolinate)
    """
    events = parse(test_str)
    assert len(events) == 3
    assert len(events[0].data["subevents"]) == 2
    assert "Generic Brand" in events[0].data["attributes"]
