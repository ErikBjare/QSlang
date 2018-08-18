#!/bin/env python3

import re
import logging
from typing import List, Dict, Any, Tuple
from datetime import time, datetime

from event import Event


log = logging.getLogger(__name__)

re_date = re.compile(r"[0-9]+-[0-9]+-[0-9]+")
re_time = re.compile(r"[~+]*[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(r"[~≤]?[?0-9\.]+(k|c|d|mc|m|u|n)?(l|L|g|IU|x)?")
re_extra = re.compile(r"\(.*\)")
re_roa = re.compile(r"(orall?y?|buccal|subcut|smoked|vaporized|insuffl?a?t?e?d?|chewed|subli?n?g?u?a?l?|intranasal|spliff)")


def parse_data(data: str) -> List[Dict[str, Any]]:
    datas = []
    if re_amount.match(data):
        for entry in (e.strip() for e in data.split("+") if e.strip()):
            d = {"raw": entry}

            m_amount = re_amount.match(entry)
            if m_amount:
                d["amount"] = m_amount[0]
                entry = entry.replace(d["amount"], "").strip()

            m_roa = re_roa.findall(entry)
            if m_roa:
                d["roa"] = m_roa[0]
                entry = entry.replace(d["roa"], "").strip()

            m_extra = re_extra.findall(entry)
            if m_extra:
                d["extra"] = m_extra[0].strip("()")
                entry = entry.replace("(" + d["extra"] + ")", "").strip()

            d["substance"] = entry.strip("\\").strip().strip(")")
            datas.append(d)
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


def _test_parse_with_plus_in_extras():
    # FIXME: This test doesn't pass
    test_str = """
    # 2018-04-14
    12:00 - 1x Something (with a + in the extras)
    """
    events = parse(test_str)
    assert len(events) == 1
