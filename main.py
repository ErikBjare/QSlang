#!/bin/env python3

import sys
import logging
import statistics
import itertools
from typing import List
from copy import copy
from collections import Counter, defaultdict
from datetime import date
from itertools import groupby
from functools import reduce

import matplotlib.pyplot as plt
import numpy as np

from event import Event
from load import load_events
from dose import Dose, _fmt_amount


log = logging.getLogger(__name__)


def print_event(e: Event) -> None:
    if e.type == "data" and 'amount' in e.data and 'substance' in e.data:
        d = e.data
        misc = copy(e.data)
        misc.pop('amount')
        misc.pop('substance')
        e_str = f"{d['amount'] if 'amount' in d else '?'} {d['substance']}  -  {misc}"
    else:
        e_str = str(e.data)
    print(f"{e.timestamp.isoformat()} | {e.type.ljust(7)} | " + e_str)


def print_events(events: List[Event]) -> None:
    for e in events:
        print_event(e)


def _print_daily_doses(events: List[Event], substance: str, ignore_doses_fewer_than=None):
    events = [e for e in events if e.substance and e.substance.lower() == substance.lower() and e.dose]
    if not events:
        print(f"No doses found for substance '{substance}'")
        return

    unit = next(map(lambda e: e.unit, events))

    grouped_by_date = igroupby(sorted(events), key=lambda e: e.timestamp.date())
    tot_amt = Dose(substance, f"0{unit}")
    for _, v in grouped_by_date.items():
        try:
            amt = Dose(substance, f"0{unit}")
            for e in v:
                amt += e.dose
            tot_amt += amt
        except Exception as e:
            log.warning(f"Unable to sum amounts '{v}', '{tot_amt}': {e}")

    median_dose = statistics.median(e.dose.amount for e in events if e.dose)
    min_dose = min(e.dose.amount for e in events if e.dose)
    max_dose = max(e.dose.amount for e in events if e.dose)

    if ignore_doses_fewer_than and ignore_doses_fewer_than > len(grouped_by_date):
        return

    # TODO: Use Counter

    print(f"{substance}:")
    print(f" - latest: {max(grouped_by_date)} ({(date.today() - max(grouped_by_date)).days} days ago)")
    print(f" - oldest: {min(grouped_by_date)} ({(date.today() - min(grouped_by_date)).days} days ago)")
    print(f" - {len(grouped_by_date)} days totalling {tot_amt.amount_with_unit}")
    print(f" - avg dose/day: {_fmt_amount(tot_amt.amount/len(events), unit)}")
    print(f" - min/median/max dose: {_fmt_amount(min_dose, unit)}/{_fmt_amount(median_dose, unit)}/{_fmt_amount(max_dose, unit)}")
    grouped_by_roa = igroupby(events, key=lambda e: e.roa)
    print(f" - ROAs:")
    for roa in sorted(grouped_by_roa, key=lambda v: grouped_by_roa[v]):
        print(f"   - {roa.ljust(10)}  n: {len(grouped_by_roa[roa])}")


def _print_substancelist(events):
    substances = {e.substance for e in events if e.substance}
    for substance in sorted(substances):
        _print_daily_doses(events, substance, ignore_doses_fewer_than=2)


def _print_usage():
    print("Usage: python3 main.py <subcommand>")
    print("Subcommands:")
    print(" - events")
    print(" - substances")
    print(" - doses <substances>")
    print(" - plot <substances>")


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


def igroupby(l, key=lambda x: x):
    return {k: list(v) for k, v in groupby(sorted(l, key=key), key=key)}


def _plot_frequency(events, count=True, count_by_date=True):
    """
    Should plot frequency of use over time
    (i.e. a barchart where the bar heights are equal to the count per period)
    """

    # Filter away journal entries and sort
    events = list(sorted(filter(lambda e: e.type == "data", events)))

    labels = []
    substances = {e.substance for e in events}

    grouped_by_date = defaultdict(list)
    for period, events_grouped in groupby(events, key=lambda e: (e.timestamp.year, e.timestamp.month)):
        grouped_by_date[period] = list(events_grouped)
        labels.append(period)

    def _fill_blank_dates(labels_tuples):
        (min_year, min_month) = min(labels_tuples)
        (max_year, max_month) = max(labels_tuples)
        g = itertools.product(range(min_year, max_year + 1), range(1, 13))
        g = itertools.dropwhile(lambda t: t < (min_year, min_month), g)
        return list(itertools.takewhile(lambda t: t <= (max_year, max_month), g))

    period_counts = defaultdict(list)
    labels = _fill_blank_dates(labels)
    for period in labels:
        events = grouped_by_date[period]
        grouped_by_substance = igroupby(events, key=lambda e: e.substance)
        if count:
            if count_by_date:
                c = Counter({substance: len({e.timestamp.date() for e in events}) for substance, events in grouped_by_substance.items()})
            else:
                c = Counter({substance: len(events) for substance, events in grouped_by_substance.items()})
            unit = "x"
        else:
            c = Counter({substance: sum(e.data["dose"].amount for e in events if "dose" in e.data) for substance, events in grouped_by_substance.items()})
            unit = events[0].data["dose"].unit if events and "dose" in events[0].data else ""

        print(period)
        for k, v in c.most_common(20):
            print(f" - {v}{unit} {k}")

        for s in sorted(substances):
            period_counts[s].append(c[s])

    stackheight = np.zeros(len(labels))
    for substance, n in period_counts.items():
        plt.bar(["-".join(map(str, t)) for t in labels], n, label=substance, bottom=stackheight)
        stackheight += np.array(n)

    plt.xticks(rotation='vertical')
    plt.legend()
    plt.show()


def filter_events_by_args(events: List[Event], args: List[str]):
    if not args:
        print("Missing argument")

    return [e for e in events
            if e.substance in args or set(args).intersection(set(e.tags))]


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
            print_events(events)
        elif sys.argv[1] == "doses":
            args = sys.argv[2:]
            for arg in args:
                _print_daily_doses(filter_events_by_args(events, [arg]), arg)
        elif sys.argv[1] == "substances":
            _print_substancelist(events)
        elif sys.argv[1] == "plot":
            args = sys.argv[2:]
            if args:
                events = filter_events_by_args(events, args)
            _plot_frequency(events)
        else:
            _print_usage()
    else:
        _print_usage()

    if msgcounter.level2count:
        print(f'Messages logged: {msgcounter.level2count}')


if __name__ == "__main__":
    main()
