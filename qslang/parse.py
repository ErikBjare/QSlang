#!/bin/env python3

import re
import logging
import typing
import pytest
from typing import List, Dict, Any, Tuple, Optional
from datetime import time, datetime, timedelta

import regex

from .event import Event


log = logging.getLogger(__name__)

re_date = re.compile(r"[0-9]+-[0-9]+-[0-9]+")
re_time = re.compile(r"[~+]*[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(
    r"([~≤<>=]?[?0-9\./]+(?:k|c|d|mc|m|u|n)?(?:l|L|g|IU|x|tb?sp| ?cup|balls?|balloons?|(?= )))(?: of)?\b"
)
re_substance = re.compile(r"[-\w ]+")
re_roa = re.compile(
    r"\b(oral(?:ly)?|subcut\w*|smoked|vap(?:ed|o?r?i?z?e?d?)|spliff|chewed|buccal(?:ly)?|subl(?:ingual)?|rectal(?:ly)?|insuff(?:lated)?|intranasal|IM|intramuscular|IV|intravenous|topical|transdermal|drinked|balloon|inhaled)\b"
)
re_concentration = re.compile(r"[?0-9\.]+%")

# Needs the regex package, to handle the recursion: https://stackoverflow.com/a/26386070/965332
re_extra = regex.compile(r"[(]((?>[^()]+|(?R))*)[)]")

# regexp matches all plusses or commas not within parens or brackets
# doesn't work for nested parens or brackets
# taken from: https://stackoverflow.com/a/26634150/965332
re_split = re.compile(r"[+,]\s*(?![^()]*\))")
# re_split = regex.compile(r"[+,]\s*((?>[^()]+|(?R))*\))")


def _pop_regex(s: str, regex: typing.Pattern, group=None) -> Tuple[str, Optional[str]]:
    """
    Pop first match of regex anywhere in string.
    Will remove the entire match (group 0) from the input string,
    but can be told to return a particular subgroup.
    """
    m = regex.search(s)
    if m:
        if group:
            popped = m.group(group)
        else:
            popped = m[0]
        print(f"popped: {popped}")
        return s.replace(m[0], "").strip(), popped
    else:
        return s, None


def _dict_pop_None(d: Dict):
    """pops keys with value None in-place"""
    keys_None = [k for k in d if d[k] is None]
    for k in keys_None:
        d.pop(k)


def parse_data(data: str) -> List[Dict[str, Any]]:
    datas = []
    if re_amount.match(data):
        print(f"before split: {data}")
        for entry in (e for e in re_split.split(data)):
            d: Dict[str, Any] = {"raw": entry}
            print(f"before pop amount: {entry}")
            entry, d["amount"] = _pop_regex(entry, re_amount, group=1)
            print(f"before pop roa:    {entry}")
            entry, d["roa"] = _pop_regex(entry, re_roa)
            print(f"before pop extra:  {entry}")
            entry, extra = _pop_regex(entry, re_extra, group=1)
            print(f"after:  {entry}")
            if extra:
                d["raw_extra"] = extra
                d["subevents"] = []
                d["attributes"] = [a.strip() for a in re_split.split(extra)]
                for attribute in d["attributes"]:
                    subevents = parse_data(attribute)
                    if subevents:
                        d["subevents"].extend(subevents)
                    _, concentration = _pop_regex(attribute, re_concentration)
                    if concentration:
                        d["concentration"] = concentration

            d["substance"] = entry.strip("\\").strip()

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
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if line:
            if line[0] == "#":
                try:
                    current_date = datetime.strptime(
                        line[1:].strip().split(" - ")[0], "%Y-%m-%d"
                    )
                except Exception as e:
                    log.warning(f"Unable to parse date: {e}")
            elif re_time.match(line):
                if not current_date:
                    log.warning(f"Date unknown ('{line}'), skipping")
                    log.warning(f"First line was: '{lines[0]}'")
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


@pytest.mark.run(order=1)
def test_pop_regex():
    s, match = _pop_regex("100mg", re_amount)
    assert match
    assert not s


@pytest.mark.run(order=0)
def test_re_split():
    """
    Test that the regexp splits correctly
    """
    # Base case, pluses
    s = "1 cup of coffee+2 tbsp sugar+3 tbsp sugar"
    assert re_split.split(s) == [
        "1 cup of coffee",
        "2 tbsp sugar",
        "3 tbsp sugar",
    ]

    # Base case, commas
    s = "1 cup of coffee, 2 tbsp sugar, 3 tbsp sugar"
    assert re_split.split(s) == ["1 cup of coffee", "2 tbsp sugar", "3 tbsp sugar"]

    # Case with parens and nested child (nothing to split)
    s = "1 cup of coffee (2 tbsp sugar (from beets), 3 tbsp sugar)"
    assert re_split.split(s) == [s]

    # FIXME: Doesn't work (nested parens not supported)
    # s = "1x Generic Multivitamin (Generic Brand, 1000IU Vitamin D3 (tocopherol) + 10mg Zinc (from picolinate))"
    # assert re_split.split(s) == [s]

    # FIXME: Doesn't work
    # Mix plus and comma
    # s = "1x Generic Multivitamin, 2x Something else + 3x Another one"
    # assert re_split.split(s) == [
    #     "1x Generic Multivitamin",
    #     "2x Something",
    #     "3x Another one",
    # ]


@pytest.mark.run(order=1)
def test_re_amount():
    assert _pop_regex("1 cup of Coffee", re_amount, 1) == ("Coffee", "1 cup")


@pytest.mark.run(order=2)
def test_parse():
    test1 = """
    # 2018-04-14
    16:30 - Started working on qslang
    ~17:12 - Made progress
    18:12 - ~1dl Green tea + 5g Cocoa
    """
    events = parse(test1)
    assert events[0].timestamp == datetime(2018, 4, 14, 16, 30)
    assert events[0].data["raw"] == "Started working on qslang"

    assert events[1].timestamp == datetime(2018, 4, 14, 17, 12)
    assert events[1].data["raw"] == "Made progress"

    assert events[2].substance == "Green tea"
    assert events[2].amount == "1dl"

    assert events[3].substance == "Cocoa"
    assert events[3].amount == "5g"

    assert len(events) == 4


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


def test_complex_extras_probiotic():
    # FIXME: Broken cases
    test_str = """
    # 2018-08-20
    08:00 - 1x Complete Probiotic (Bulkpowders, 200mg Betaine HCl + 3.9B CFU)
    """
    events = parse(test_str)
    # assert len(events) == 2
    # print(events)
    assert "Complete Probiotic" == events[0].data["substance"]
    # assert len(events[0].data["subevents"]) == 1
    assert "Bulkpowders" in events[0].data["attributes"]
    assert "1x" == events[0].data["amount"]


def test_complex_extras_multivit():
    test_str = """
    # 2018-08-20
    08:00 - 1x Generic Multivitamin (Generic Brand, 1000IU Vitamin D3 + 25mg Zinc Picolinate)
    """
    events = parse(test_str)
    assert len(events) == 3
    assert len(events[0].data["subevents"]) == 2
    assert "Generic Brand" in events[0].data["attributes"]


def test_complex_nested():
    # FIXME: Broken cases
    test_str = """
    # 2018-08-20
    08:00 - 1x Generic Multivitamin (Generic Brand, 1000IU Vitamin D3 (tocopherol) + 10mg Zinc (from picolinate))
    """
    events = parse(test_str)
    print(events[0])
    assert len(events) == 3
    # assert "Generic Brand" in events[0].data["attributes"]
    # assert len(events[0].data["subevents"]) == 2
    assert events[1].data["substance"] == "Vitamin D3"


def test_parse_cup_of():
    # Handle "1 cup Coffee"
    text = """
        # 2020-01-01
        08:00 - 1 cup Coffee
    """
    events = parse(text)
    assert len(events) == 1
    # assert events[0].type == "dose"
    assert events[0].timestamp == datetime(2020, 1, 1, 8, 0)
    assert events[0].data["raw"] == "1 cup Coffee"
    assert events[0].data["substance"] == "Coffee"
    assert events[0].data["amount"] == "1 cup"

    # Handle "1 cup of Caffeine"
    text = """
        # 2020-01-01
        08:00 - 1 cup of Coffee
    """
    events = parse(text)
    assert len(events) == 1
    # assert events[0].type == "dose"
    assert events[0].timestamp == datetime(2020, 1, 1, 8, 0)
    assert events[0].data["raw"] == "1 cup of Coffee"
    assert events[0].data["substance"] == "Coffee"


def test_unknown_dose():
    text = """
        # 2022-01-01
        16:20 - ?ml Cannabis oil vaped
    """
    events = parse(text)
    assert len(events) == 1
    assert events[0].timestamp == datetime(2022, 1, 1, 16, 20)
    assert events[0].data["raw"] == "?ml Cannabis oil vaped"
    assert events[0].data["substance"] == "Cannabis oil"
    assert events[0].data["amount"] == "?ml"


def test_nested_regex():
    test_str = """
    # 2020-01-01
    10:00 - 1x Complete Multivitamin (100mg Something + 20mg Magnesium (from Citrate))
    """

    # Basic re test
    matches = re_extra.findall(test_str)
    assert len(matches) == 1
    assert "+" in matches[0]

    # Complete pop_regex test
    pattern, extra = _pop_regex(test_str, re_extra, group=1)
    print(pattern)
    print(extra)
    assert extra == "100mg Something + 20mg Magnesium (from Citrate)"
