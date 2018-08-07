#!/bin/env python3

import sys
import re
import logging
import json
import statistics
import itertools
from typing import List, Dict, Any, Tuple, Union
from copy import copy
from collections import namedtuple, Counter, defaultdict
from datetime import date, time, datetime
from pathlib import Path
from itertools import groupby
from functools import reduce

from dataclasses import dataclass, field

log = logging.getLogger(__name__)

re_date = re.compile(r"[0-9]+-[0-9]+-[0-9]+")
re_time = re.compile(r"[~+]*[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(r"[~]?[?0-9\.]+(k|c|d|mc|m|u|n)?(l|L|g|IU|x)?")
re_extra = re.compile(r"\(.*\)")
re_roa = re.compile(r"(orall?y?|buccal|subcut|smoked|vaporized|insuffl?a?t?e?d?|chewed|subli?n?g?u?a?l?|intranasal|spliff)")

re_evernote_author = re.compile(r'>author:(.+)$')
re_evernote_source = re.compile(r'>source:(.+)$')


@dataclass(order=True)
class Event:
    timestamp: datetime
    type: str
    data: dict = field(compare=False)


def _load_standard_notes() -> List[str]:
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


def _load_evernote() -> List[str]:
    notes = []
    d = Path("./data/private/Evernote")
    dateset = set()
    for p in d.glob("*.md"):
        data = p.read_text()

        # A bad idea for filtering away notes that were not mine, but might still be useful for tagging with metadata
        if False:
            authors = re_evernote_author.findall(data)
            if authors and "erik" not in authors[0]:
                print(f" - Skipped note from other author: {authors}")
                continue

            source = re_evernote_source.findall(data)
            if not authors and not source:
                print(f" - Skipping note without author or source")
                continue

            if source and "android" not in source[0]:
                print(f" - Source was something else than android: {source}")

        dates = re_date.findall(str(p))
        if dates:
            dateset.add(dates[0])
            notes.append(data)
    # pprint(sorted(dates))
    return notes


def load_events():
    notes = []
    notes += _load_standard_notes()
    notes += _load_evernote()

    events = [e for note in notes for e in parse(note)]
    return events


def _load_substance_map():
    p = Path("data/substance_map.csv")
    if p.is_file():
        with p.open() as f:
            return dict(line.split(",") for line in f.readlines())
    else:
        return {}


substance_map = _load_substance_map()


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
            if d["substance"].lower() in substance_map:
                d["substance"] = substance_map[d["substance"].lower()]
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
        print(f"Tried to parse time: {s}")
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


def split_amtstr(s: str) -> Tuple[float, str, str]:
    try:
        n, p, u = _r.findall(s)[0]
        return float(n), p, u
    except Exception as e:
        raise Exception(f"Unable to split amount string: {s} ({e})")


def test_split_amtstr():
    assert split_amtstr("0g") == (0.0, "", "g")


def _norm_amount(n: float, p: str) -> float:
    if p == "d":
        n *= 0.1
    elif p == "c":
        n *= 0.01
    elif p == "m":
        n *= 0.001
    elif p == "mc":
        n *= 0.000001
    return n


def _best_prefix(n: float) -> Tuple[str, float]:
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


def _fmt_amount(amount: float, unit: str) -> str:
    p, pf = _best_prefix(amount)
    return f"{round(amount / pf, 4)}{p}{unit}"


class Dose:
    def __init__(self, substance: str, amount: str) -> None:
        self.substance: str = substance
        n, p, u = split_amtstr(amount)
        self.amount: float = _norm_amount(n, p)
        self.unit: str = u

    def __str__(self) -> str:
        return f"{self.amount_with_unit} {self.substance}"

    @property
    def amount_with_unit(self) -> str:
        return _fmt_amount(self.amount, self.unit)

    def __add__(self, other: "Dose") -> "Dose":
        assert self.substance == other.substance
        assert self.unit == other.unit
        return Dose(self.substance, _sum_amount(self.amount_with_unit, other.amount_with_unit))


def _sum_amount(a1: str, a2: str) -> str:
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


def _annotate_doses(events: List[Event]) -> List[Event]:
    for e in events:
        try:
            e.data["dose"] = Dose(e.data["substance"], e.data["amount"])
        except Exception as exc:
            log.warning(f"Unable to annotate dose: {exc}")
            events.remove(e)
    return events


def _print_daily_doses(events: List[Event], substance: str, ignore_doses_fewer_than=None):
    events = [e for e in events if isinstance(e.data, dict) and e.data["substance"].lower() == substance.lower()]
    events = _annotate_doses(events)
    if not events:
        print(f"No doses found for substance '{substance}'")
        return
    unit = events[0].data["dose"].unit

    grouped_by_date = {k: list(v) for k, v in groupby(sorted(events), key=lambda e: e.timestamp.date())}
    tot_amt = Dose(substance, f"0{unit}")
    for _, v in grouped_by_date.items():
        try:
            amt = reduce(lambda amt, e2: amt + e2.data["dose"], v, Dose(substance, f"0{unit}"))
            tot_amt += amt
        except Exception as e:
            log.warning(f"Unable to parse amount '{v}': {e}")

    median_dose = statistics.median(e.data["dose"].amount for e in events if "dose" in e.data)
    min_dose = min(e.data["dose"].amount for e in events if "dose" in e.data)
    max_dose = max(e.data["dose"].amount for e in events if "dose" in e.data)

    if ignore_doses_fewer_than and ignore_doses_fewer_than > len(grouped_by_date):
        return

    def _roa_key(e):
        return e.data["roa"] if "roa" in e.data else "unknown"

    # TODO: Use Counter

    print(f"{substance}:")
    print(f" - latest: {max(grouped_by_date)} ({(date.today() - max(grouped_by_date)).days} days ago)")
    print(f" - oldest: {min(grouped_by_date)} ({(date.today() - min(grouped_by_date)).days} days ago)")
    print(f" - {len(grouped_by_date)} days totalling {tot_amt.amount_with_unit}")
    print(f" - avg dose/day: {_fmt_amount(tot_amt.amount/len(events), unit)}")
    print(f" - min/median/max dose: {_fmt_amount(min_dose, unit)}/{_fmt_amount(median_dose, unit)}/{_fmt_amount(max_dose, unit)}")
    grouped_by_roa = {k: list(v) for k, v in groupby(sorted(events, key=_roa_key), key=_roa_key)}
    print(f" - ROAs:")
    for roa in sorted(grouped_by_roa, key=lambda v: grouped_by_roa[v]):
        print(f"   - {roa.ljust(10)}  n: {len(grouped_by_roa[roa])}")


def _print_substancelist(events):
    events = [e for e in events if isinstance(e.data, dict)]
    events = _annotate_doses(events)
    substances = {e.data["substance"] for e in events}
    for substance in sorted(substances):
        _print_daily_doses(events, substance, ignore_doses_fewer_than=2)


def _print_usage():
    print("Usage: python3 main.py <subcommand>")
    print("Subcommands:")
    print(" - events")
    print(" - doses <substances>")
    print(" - plot <substances>")


def test_evernote():
    _load_evernote()


class MsgCounterHandler(logging.Handler):
    """https://stackoverflow.com/a/31142078/965332"""
    level2count = None

    def __init__(self, *args, **kwargs):
        super(MsgCounterHandler, self).__init__(*args, **kwargs)
        self.level2count = {}

    def emit(self, record):
        levelname = record.levelname
        if levelname not in self.level2count:
            self.level2count[levelname] = 0
        self.level2count[levelname] += 1


def _substance(e: Event):
    # TODO: Turn into a helper method on Event?
    if isinstance(e.data, dict):
        return e.data["substance"].strip()
    else:
        return "unknown/journal"


def _plot_frequency(events, count=True):
    """
    Should plot frequency of use over time
    (i.e. a barchart where the bar heights are equal to the count per period)
    """
    import matplotlib.pyplot as plt
    import numpy as np

    events = list(sorted(events))
    by_period = groupby(events, key=lambda e: (e.timestamp.year, e.timestamp.month))
    period_counts = defaultdict(list)
    labels = []
    substances = {_substance(e) for e in events}

    grouped_by_date = defaultdict(list)
    for period, events in by_period:
        grouped_by_date[period] = list(events)
        labels.append("-".join(map(str, period)))

    def _fill_blank_dates(labels):
        (min_year, min_month) = map(int, min(labels).split("-"))
        (max_year, max_month) = map(int, max(labels).split("-"))
        g = itertools.product(range(min_year, max_year + 1), range(1, 13))
        g = itertools.dropwhile(lambda t: t < (min_year, min_month), g)
        return list(itertools.takewhile(lambda t: t <= (max_year, max_month), g))

    labels = ["-".join(map(str, t)) for t in _fill_blank_dates(labels)]
    for period in _fill_blank_dates(labels):
        events = grouped_by_date[period]
        grouped_by_substance = groupby(sorted(events, key=_substance), key=_substance)
        if count:
            c = Counter({substance: len(list(events)) for substance, events in grouped_by_substance})
            unit = "x"
        else:
            events = _annotate_doses(events)
            c = Counter({substance: sum(e.data["dose"].amount for e in events) for substance, events in grouped})
            unit = events[0].data["dose"].unit

        print(period)
        for k, v in c.most_common(10):
            print(f" - {v}{unit} {k}")

        for s in sorted(substances):
            period_counts[s].append(c[s])

    stackheight = np.zeros(len(labels))
    for substance, n in period_counts.items():
        plt.bar(labels, n, label=substance, bottom=stackheight)
        stackheight += np.array(n)

    plt.xticks(labels, rotation='vertical')
    plt.legend()
    plt.show()


def main():
    msgcounter = MsgCounterHandler()

    verbose = "-v" in sys.argv
    if verbose:
        sys.argv.remove("-v")
    logging.basicConfig(level=logging.DEBUG if verbose else logging.ERROR)

    logging.getLogger().addHandler(msgcounter)

    events = load_events()

    if sys.argv[1:]:

        if sys.argv[1] == "events":
            for e in events:
                print(e)
        elif sys.argv[1] == "doses":
            if len(sys.argv) < 3:
                print("Missing argument")
            else:
                for substance in sys.argv[2:]:
                    _print_daily_doses(events, substance)
        elif sys.argv[1] == "substances":
            _print_substancelist(events)
        elif sys.argv[1] == "plot":
            substances = sys.argv[2:]
            if substances:
                events = [e for e in events if _substance(e) in substances]
            _plot_frequency(events)
        else:
            _print_usage()
    else:
        _print_usage()

    if msgcounter.level2count:
        print(f'Messages logged: {msgcounter.level2count}')


if __name__ == "__main__":
    main()
