#!/bin/env python3

import logging
import statistics
import fnmatch
from typing import List, Dict, Tuple, Optional, Union
from copy import copy
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from itertools import groupby

import matplotlib.pyplot as plt
import numpy as np

from event import Event
from load import load_events
from dose import Dose, Q_
from util import MsgCounterHandler, monthrange, dayrange
from igroupby import igroupby


log = logging.getLogger(__name__)


def print_event(e: Event, show_misc=False) -> None:
    if e.type == "data" and 'amount' in e.data and 'substance' in e.data:
        d = e.data
        misc = copy(e.data)
        misc.pop('amount')
        misc.pop('substance')
        e_str = f"{d['amount'] if 'amount' in d else '?'} {d['substance']}" + (f"  -  {misc}" if show_misc else '')
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
                if e.dose:
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


def _print_substancelist(events: List[Event]) -> None:
    c = Counter({k: len(v) for k, v in igroupby([e for e in events if e.substance], lambda e: e.substance).items()})
    for s, n in c.most_common():
        print(f"{n}x\t{s}")
    print(f"{len(c)} substances found")


def _print_usage() -> None:
    print("Usage: python3 main.py <subcommand>")
    print("Subcommands:")
    print(" - events")
    print(" - substances")
    print(" - doses [substance or #tag]")
    print(" - plot [substance or #tag]")


TDate = Tuple[int, int, Optional[int]]


def _grouped_by_date(events: List[Event], monthly=True, offset=True) -> Dict[TDate, List[Event]]:
    grouped_by_date: Dict[Tuple[int, int, Optional[int]], List[Event]] = defaultdict(list)
    offset = timedelta(hours=6) if offset else timedelta(0)
    for period, events_grouped in groupby(events, key=lambda e: (
            (e.timestamp + offset).year, (e.timestamp + offset).month, None
            if monthly else (e.timestamp + offset).day)):
        grouped_by_date[period] = list(events_grouped)
    return grouped_by_date


TValueByDate = Dict[TDate, float]


def _dosesum(doses):
    doses = list(doses)
    if not doses:
        return 0
    acc = doses[0]
    for dose in doses[1:]:
        acc += dose
    return acc


def _sum_doses(events: List[Event], monthly=True) -> Dict[str, TValueByDate]:
    substances = {e.substance for e in events if e.substance}
    events = [e for e in events if e.dose]
    grouped_by_date = _grouped_by_date(events, monthly=monthly)

    period_counts: Dict[str, Dict[TDate, float]] = defaultdict(lambda: defaultdict(float))
    for period in grouped_by_date.keys():
        events_g_date = grouped_by_date[period]
        events_g_substance = igroupby(events_g_date, key=lambda e: e.substance)
        c = Counter({substance: _dosesum(e.dose for e in _events)
                     for substance, _events in events_g_substance.items() if substance})

        print(period)
        for k, v in c.most_common(20):
            assert k
            print(f" - {v}")

        for s in substances:
            period_counts[s][period] = c[s].amount if isinstance(c[s], Dose) else 0  # type: ignore

    return period_counts


def _count_doses(events: List[Event], one_per_day=True, monthly=True) -> Dict[str, TValueByDate]:
    substances = {e.substance for e in events if e.substance}
    grouped_by_date = _grouped_by_date(events, monthly=monthly)

    period_counts: Dict[str, Dict[TDate, float]] = defaultdict(lambda: defaultdict(float))
    for period in grouped_by_date.keys():
        events = grouped_by_date[period]
        grouped_by_substance = igroupby(events, key=lambda e: e.substance)
        if one_per_day:
            c = Counter({substance: len({e.timestamp.date() for e in events}) for substance, events in grouped_by_substance.items()})
        else:
            c = Counter({substance: len(events) for substance, events in grouped_by_substance.items()})
        unit = " days" if one_per_day else "x"

        print(period)
        for k, v in c.most_common(20):
            print(f" - {v}{unit} {k}")

        for s in substances:
            period_counts[s][period] = c[s]

    return period_counts


def _plot_frequency(events, count=False, count_by_date=False, any_substance=False, daily=False):
    """
    Should plot frequency of use over time
    (i.e. a barchart where the bar heights are equal to the count per period)
    """

    # Filter away journal entries and sort
    events = list(sorted(filter(lambda e: e.type == "data", events)))

    if any_substance:
        for e in events:
            e.data["substance"] = "Any"

    if count:
        period_counts = _count_doses(events, one_per_day=count_by_date, monthly=not daily)
    else:
        period_counts = _sum_doses(events, monthly=not daily)

    labels = [date for sd in period_counts for date in period_counts[sd].keys()]
    if daily:
        labels = dayrange(min(labels), max(labels))
    else:
        labels = [(*m, None) for m in monthrange(min(labels)[:2], max(labels)[:2])]
    labels_str = ["-".join([str(n) for n in t if n]) for t in labels]

    stackheight = np.zeros(len(labels))
    for substance, value_by_date in period_counts.items():
        n = [value_by_date[label] if label in value_by_date else 0 for label in labels]
        plt.bar(labels_str, n, label=substance, bottom=stackheight)
        stackheight += np.array(n)

    plt.xticks(rotation='vertical')
    plt.legend()
    plt.show()


def filter_events_by_args(events: List[Event], args: List[str]):
    if not args:
        print("Missing argument")

    matches = []
    for e in events:
        for arg in args:
            if (e.substance and fnmatch.fnmatch(e.substance.lower(), arg.lower())) or \
               arg[0] == "#" and arg.strip("#").lower() in set(map(lambda e: e.lower(), e.tags)):
                matches.append(e)
                break
    return matches


def _datetime_arg(s):
    d = datetime(*[int(d) for d in s.split("-")])
    return d


def _build_argparser():
    import argparse

    parser = argparse.ArgumentParser(prog='PROG')
    parser.add_argument('-v', '--verbose', action='store_true', help='print verbose logging')
    parser.add_argument('--start', type=_datetime_arg, help='start date to filter events by')
    parser.add_argument('--end', type=_datetime_arg, help='end date to filter events by')

    subparsers = parser.add_subparsers(dest='subcommand')

    events = subparsers.add_parser('events', help='list events')
    substances = subparsers.add_parser('substances', help='list substances')
    doses = subparsers.add_parser('doses', help='print information about doses')
    plot = subparsers.add_parser('plot', help='plot doses over time')

    for subparser in [events, substances, doses, plot]:
        subparser.add_argument('substances', nargs='*', help='substances or #tags to include')

    plot.add_argument('--any', action='store_true', help='count all matches as any match')
    plot.add_argument('--daily', action='store_true', help='use daily resolution on the x-axis')
    plot.add_argument('--count', action='store_true', help='count number of doses instead of amount')
    plot.add_argument('--count-by-date', action='store_true', help='count only one dose per day (only makes sense if --count is given)')

    return parser


def _filter_events(events, start, end, substances):
    if start:
        events = [e for e in events if e.timestamp >= start]
    if end:
        events = [e for e in events if e.timestamp <= end]
    if substances:
        events = filter_events_by_args(events, substances)
    return events


_alcohol_conc_assumptions = {
    "gin": 0.4,
    "vodka": 0.4,
    "whiskey": 0.4,
    "beer": 0.05,
    "wine": 0.12,
}


def _alcohol_preprocess(events: List[Event]) -> List[Event]:
    for e in events:
        if not e.substance or not e.dose:
            continue
        if 'Alcohol' in e.tags:
            conc_str = e.data.get("concentration", None)
            if conc_str:
                if "?" not in conc_str:
                    conc = 0.01 * float(conc_str.strip("%"))
            elif e.substance.lower() in _alcohol_conc_assumptions:
                conc = _alcohol_conc_assumptions[e.substance.lower()]
            else:
                print(f"Concentration unknown for event: {e}")
                continue
            e.data["substance"] = "Alcohol"
            e.data["amount"] = e.dose.quantity * conc
    return events


def main():
    msgcounter = MsgCounterHandler()

    parser = _build_argparser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR)
    logging.getLogger().addHandler(msgcounter)

    events = load_events()
    events = _filter_events(events, args.start, args.end, args.substances)
    events = _alcohol_preprocess(events)

    if args.subcommand == "events":
        print_events(events)
    elif args.subcommand == "doses":
        if events:
            for substance, substance_events in igroupby(events, lambda e: e.substance).items():
                _print_daily_doses(substance_events, substance)
        else:
            print("No matching events found")
    elif args.subcommand == "substances":
        _print_substancelist(events)
    elif args.subcommand == "plot":
        _plot_frequency(events, count=args.count, count_by_date=args.count_by_date, daily=args.daily, any_substance=args.any)
    else:
        parser.print_help()

    if msgcounter.level2count:
        print(f'Messages logged: {dict(msgcounter.level2count)}')


if __name__ == "__main__":
    main()
