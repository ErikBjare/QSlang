import re
from typing import List, Dict, Any, Tuple, Union
from copy import copy
from collections import namedtuple
from datetime import date, time, datetime
from pathlib import Path
from itertools import groupby
from functools import reduce
import logging
import json

log = logging.getLogger(__name__)

re_date = re.compile(r"[0-9]+-[0-9]+-[0-9]+")
re_time = re.compile(r"[~+]*[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(r"[~]?[?0-9\.]+(k|c|d|mc|m|u|n)?(l|g|IU|x)?")
re_extra= re.compile(r"\(.*\)")
re_roa = re.compile(r"(oral|buccal|subcut|smoked|vaporized|insuff)")

Event = namedtuple("Event", ["timestamp", "type", "data"])


def load_standard_notes() -> List[str]:
    notes = []
    p = Path("./data/private")
    for path in p.glob("*Archive*.txt"):
        with open(path) as f:
            data = json.load(f)
            for entry in sorted(data["items"], key=lambda e: e["content"]["title"] if "title" in e["content"] else ""):
                if "title" in entry["content"] and "text" in entry["content"]:
                    title = entry["content"]["title"]
                    text = entry["content"]["text"]
                    if re_date.match(title):
                        # print(title)
                        # print(text)
                        notes.append(f"# {title}\n\n{text}")
                else:
                    log.debug("Unknown note type")
                    # print(entry["content"])
                    title = None

    return notes


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

            d["substance"] = entry
            datas.append(d)
    return datas


def parse_time(s: str) -> Tuple[time, List[str]]:
    tags = []
    if "+" in s:
        tags.append("time-tomorrow")
    if "~" in s:
        tags.append("time-approximate")
    s = s.strip("+~").strip("+").strip("~")
    t = datetime.strptime(s, "%H:%M").time()
    return t, tags


def parse(text: str) -> List[Event]:
    events = []  # type: List[Event]

    current_date = None
    for line in text.split("\n"):
        line = line.strip()
        if line:
            if line[0] == "#":
                try:
                    current_date = datetime.strptime(line[1:].strip().split(" - ")[0], "%Y-%m-%d")
                except Exception as e:
                    log.debug(e)
            elif re_time.match(line):
                if not current_date:
                    log.warning("Date unknown, skipping")
                    continue
                t, tags = parse_time(line.split("-")[0].strip())
                timestamp = datetime.combine(current_date.date(), t)
                data = "-".join(line.split("-")[1:]).strip()
                if re_amount.match(data):
                    # Data entry
                    for entry in parse_data(data):
                        events.append(Event(timestamp, "data", entry))
                else:
                    # Journal entry
                    events.append(Event(timestamp, "journal", data))
            elif line:
                log.debug(f"Couldn't identify line-type: {line}")

    return events


def print_event(e: Event) -> None:
    d = e.data
    if e.type == "data":
        e_str = f"{d['amount'] if 'amount' in d else '?'} {d['substance']}"
    else:
        e_str = e.data
    print(f"{e.timestamp.isoformat()} | {e.type.ljust(7)} | " + e_str)


def print_events(events: List[Event]) -> None:
    for e in events:
        print_event(e)


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


_r = re.compile(r"([0-9]+\.?[0-9]*e?-?[0-9]*)(mc|d|c|m)?(l|g)?")


def split_amtstr(s):
    try:
        n, p, u = _r.findall(s)[0]
        return float(n), p, u
    except Exception as e:
        raise Exception(f"Unable to split amount string: {s} ({e})")


def test_split_amtstr():
    assert split_amtstr("0g") == (0.0, "", "g")


def _norm_amount(n, p):
    if p == "d":
        n *= 0.1
    elif p == "c":
        n *= 0.01
    elif p == "m":
        n *= 0.001
    elif p == "mc":
        n *= 0.000001
    return n


def _best_prefix(n) -> Tuple[str, float]:
    if 1e-6 <= n < 1e-3:
        return "mc", 0.000001
    elif 1e-3 <= n < 1e-0:
        return "m", 0.001
    # elif 1e-2 <= n < 1e-1:
    #     return "c", 0.01
    # elif 1e-1 <= n < 1e0:
    #     return "d", 0.1
    else:
        return "", 1


def _fmt_amount(amount, unit):
    p, pf = _best_prefix(amount)
    return f"{round(amount / pf, 4)}{p}{unit}"


class Dose:
    def __init__(self, substance: str, amount: str) -> None:
        self.substance: str = substance
        n, p, u = split_amtstr(amount)
        self.amount: float = _norm_amount(n, p)
        self.unit: str = u

    def __str__(self):
        return f"{self.amount_with_unit} {self.substance}"

    @property
    def amount_with_unit(self) -> str:
        return _fmt_amount(self.amount, self.unit)

    def __add__(self, other: "Dose"):
        assert self.substance == other.substance
        assert self.unit == other.unit
        return Dose(self.substance, _sum_amount(self.amount_with_unit, other.amount_with_unit))


def _sum_amount(a1, a2):
    n1, p1, u1 = split_amtstr(a1)
    n2, p2, u2 = split_amtstr(a2)
    assert u1 == u2  # amounts have to have the same units
    n = sum(_norm_amount(n, p) for n, p in ((n1, p1), (n2, p2)))
    p, pf = _best_prefix(n)
    n /= pf
    return f"{n}{p}{u1}"


def test_sum_amount():
    assert _sum_amount("0g", "1g") == "1.0g"
    assert _sum_amount("1mg", "10mg") == "11.0mg"
    assert _sum_amount("500mcg", "1mg") == "1.5mg"

    assert _sum_amount("1ml", "2ml") == "3.0ml"
    assert _sum_amount("1dl", "4dl") == "500.0ml"
    assert _sum_amount("1.0dl", "0l") == "100.0ml"

    assert _sum_amount("33cl", "1l") == "1.33l"


def _annotate_doses(events: List[Event]):
    for e in events:
        try:
            e.data["dose"] = Dose(e.data["substance"], e.data["amount"])
        except Exception as exc:
            log.warn(f"Unable to annotate dose: {exc}")
            events.remove(e)
    return events


def _print_daily_doses(events, substance):
    events = [e for e in events if isinstance(e.data, dict) and e.data["substance"] == substance]
    events = _annotate_doses(events)
    unit = events[0].data["dose"].unit

    grouped_by_date = {k: list(v) for k, v in groupby(sorted(events, key=lambda e: e.timestamp.date()), key=lambda e: e.timestamp.date())}
    tot_amt = Dose(substance, f"0{unit}")
    for k, v in grouped_by_date.items():
        try:
            amt = reduce(lambda amt, e2: amt + e2.data["dose"], v, Dose(substance, f"0{unit}"))
            tot_amt += amt
            #print(k, amt)
            # amt = reduce(lambda amt, e2: _sum_amount(amt, e2.data["amount"]), v, "0g")
            # tot_amt = _sum_amount(tot_amt, amt)
            # print(k, amt, substance)
        except Exception as e:
            log.warning(f"Unable to parse amount: {e}")
    print(f"{len(grouped_by_date)} days totalling {tot_amt}, avg dose/day: {_fmt_amount(tot_amt.amount/len(events), unit)}")


if __name__ == "__main__":
    logging.basicConfig()

    notes = load_standard_notes()

    events = [e for note in notes for e in parse(note)]
    for e in events:
        # print(e)
        pass

    _print_daily_doses(events, "Caffeine")
    _print_daily_doses(events, "Beer")
    _print_daily_doses(events, "Wine")
