#!/bin/env python3

import logging
import statistics
import fnmatch
from typing import List, Dict, Tuple, Optional
from copy import copy
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from itertools import groupby

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import click
import pint

from qslang.event import Event
from qslang.load import load_events
from qslang.dose import Dose
from qslang.util import monthrange, dayrange
from qslang.igroupby import igroupby


logger = logging.getLogger(__name__)


@click.group()
@click.option('-v', '--verbose', is_flag=True)
def main(verbose):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARN)


def _load_events(start: datetime = None, end: datetime = None, substances: List[str] = []) -> List[Event]:
    events = load_events()
    events = _filter_events(events, start, end, substances)
    events = _alcohol_preprocess(events)
    return events


@main.command()
@click.option('--start', type=click.DateTime(['%Y-%m-%d']), help='start date to filter events by')
@click.option('--end', type=click.DateTime(['%Y-%m-%d']), help='end date to filter events by')
@click.option('--substances', help='substances to filter by (comma-separated)')
def events(start: datetime, end: datetime, substances: Optional[str]):
    substances_list = substances.split(",") if substances else []
    events = _load_events(start, end, substances_list)
    print_events(events)


@main.command()
@click.option('--start', type=click.DateTime(['%Y-%m-%d']), help='start date to filter events by')
@click.option('--end', type=click.DateTime(['%Y-%m-%d']), help='end date to filter events by')
@click.option('--substances', help='substances to filter by (comma-separated)')
def doses(start: datetime, end: datetime, substances: Optional[str]):
    substances_list = substances.split(",") if substances else []
    events = _load_events(start, end, substances_list)
    events = [e for e in events if e.substance]
    if events:
        for substance, substance_events in igroupby(events, lambda e: e.substance).items():
            _print_daily_doses(substance_events, substance)
    else:
        print("No matching events found")


@main.command()
@click.option('--start', type=click.DateTime(['%Y-%m-%d']), help='start date to filter events by')
@click.option('--end', type=click.DateTime(['%Y-%m-%d']), help='end date to filter events by')
@click.option('--substances', help='substances to filter by (comma-separated)')
def substances(start, end, substances) -> None:
    substances_list = substances.split(",") if substances else []
    events = _load_events(start, end, substances_list)
    c = Counter({k: len(v) for k, v in igroupby([e for e in events if e.substance], lambda e: e.substance).items()})
    for s, n in c.most_common():
        print(f"{n}x\t{s}")
    print(f"{len(c)} substances found")


@main.command()
@click.option('--start', type=click.DateTime(['%Y-%m-%d']), help='start date to filter events by')
@click.option('--end', type=click.DateTime(['%Y-%m-%d']), help='end date to filter events by')
@click.option('--substances', help='substances to filter by (comma-separated)')
@click.option('--any', is_flag=True, help='count all matches as any match')
@click.option('--daily', is_flag=True, help='use daily resolution on the x-axis')
@click.option('--count', is_flag=True, help='count number of doses instead of amount')
@click.option('--days', is_flag=True, help='count number of days with doses')
def plot(start: Optional[datetime], end: Optional[datetime], substances: str, any: bool, daily: bool, count: bool, days: bool):
    substances_list = substances.split(",") if substances else []
    events = _load_events(start, end, substances_list)
    _plot_frequency(events, count=count or days, one_per_day=days, daily=daily, any_substance=any)


@main.command()
@click.option('--start', type=click.DateTime(['%Y-%m-%d']), help='start date to filter events by')
@click.option('--end', type=click.DateTime(['%Y-%m-%d']), help='end date to filter events by')
@click.option('--substances', help='substances to filter by (comma-separated)')
def plot_calendar(start: Optional[datetime], end: Optional[datetime], substances: str):
    substances_list = substances.split(",") if substances else []
    events = _load_events(start, end, substances_list)
    _plot_calendar(events)


def print_event(e: Event, show_misc=False) -> None:
    if e.type == "data" and 'amount' in e.data and 'substance' in e.data:
        d = e.data
        misc = copy(e.data)
        misc.pop('amount')
        misc.pop('substance')
        if e.dose:
            base_str = str(e.dose)
        else:
            base_str = f"{d['amount'] if 'amount' in d else '?'} {d['substance']}"
        misc_str = (f"  -  {misc}" if show_misc else '')
        e_str = base_str + misc_str
    else:
        e_str = str(e.data)
    print(f"{e.timestamp.isoformat()} | {e.type.ljust(7)} | " + e_str)


def print_events(events: List[Event]) -> None:
    last_date: Optional[datetime] = None
    for e in events:
        if last_date and last_date.date() != e.timestamp.date():
            print(f"{str(last_date.date()).ljust(8)} =========|=========|====== New day =====")
        print_event(e)
        last_date = e.timestamp


def _print_daily_doses(events: List[Event], substance: str, ignore_doses_fewer_than=None):
    events = [e for e in events if e.substance and e.substance.lower() == substance.lower() and e.dose]
    if not events:
        print(f"No doses found for substance '{substance}'")
        return

    grouped_by_date = igroupby(sorted(events), key=lambda e: e.timestamp.date())
    assert events[0].dose
    tot_amt = Dose(substance, events[0].dose.quantity * 0)
    for _, v in grouped_by_date.items():
        try:
            assert v[0].dose
            amt = Dose(substance, v[0].dose.quantity * 0)
            for e in v:
                if e.dose:
                    amt += e.dose
            tot_amt += amt
        except Exception as e:
            logger.warning(f"Unable to sum amounts '{v}', '{tot_amt}': {e}")

    if ignore_doses_fewer_than and ignore_doses_fewer_than > len(grouped_by_date):
        return

    # TODO: Use Counter

    print(f"{substance}:")
    print(f" - latest: {max(grouped_by_date)} ({(date.today() - max(grouped_by_date)).days} days ago)")
    print(f" - oldest: {min(grouped_by_date)} ({(date.today() - min(grouped_by_date)).days} days ago)")
    print(f" - {len(grouped_by_date)} days totalling {tot_amt.amount_with_unit}")
    print(f" - avg dose/day: {tot_amt/len(events)}")

    try:
        median_dose = statistics.median(e.dose for e in events if e.dose)  # type: ignore
        min_dose = min(e.dose for e in events if e.dose)
        max_dose = max(e.dose for e in events if e.dose)
        print(f" - min/median/max dose: {min_dose.amount_with_unit}/{median_dose.amount_with_unit}/{max_dose.amount_with_unit}")
    except pint.errors.DimensionalityError:
        logger.warning("Couldn't compute min/median/max doses due to inconsistent units")
    grouped_by_roa = igroupby(events, key=lambda e: e.roa)
    print(f" - ROAs:")
    for roa in sorted(grouped_by_roa, key=lambda v: grouped_by_roa[v]):
        print(f"   - {roa.ljust(10)}  n: {len(grouped_by_roa[roa])}")


TDate = Tuple[int, int, Optional[int]]

day_offset = timedelta(hours=-4)


def _grouped_by_date(events: List[Event], monthly=True) -> Dict[TDate, List[Event]]:
    grouped_by_date: Dict[Tuple[int, int, Optional[int]], List[Event]] = defaultdict(list)
    for period, events_grouped in groupby(events, key=lambda e: (
            (e.timestamp + day_offset).year, (e.timestamp + day_offset).month, None
            if monthly else (e.timestamp + day_offset).day)):
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
            period_counts[s][period] = c[s].quantity.to_base_units().magnitude if isinstance(c[s], Dose) else 0  # type: ignore

    return period_counts


def _count_doses(events: List[Event], one_per_day=True, monthly=True, verbose=False) -> Dict[str, TValueByDate]:
    substances = {e.substance for e in events if e.substance}
    grouped_by_date = _grouped_by_date(events, monthly=monthly)

    period_counts: Dict[str, Dict[TDate, float]] = defaultdict(lambda: defaultdict(float))
    for period in grouped_by_date.keys():
        events = grouped_by_date[period]
        grouped_by_substance = igroupby(events, key=lambda e: e.substance)
        if one_per_day:
            c = Counter({substance: len({(e.timestamp + day_offset).date() for e in events}) for substance, events in grouped_by_substance.items()})
        else:
            c = Counter({substance: len(events) for substance, events in grouped_by_substance.items()})
        unit = " days" if one_per_day else "x"

        if verbose:
            print(period)
            for k, v in c.most_common(20):
                print(f" - {v}{unit} {k}")

        for s in substances:
            period_counts[s][period] = c[s]

    return period_counts


def _plot_frequency(events, count=False, one_per_day=False, any_substance=False, daily=False, verbose=False):
    """
    Should plot frequency of use over time
    (i.e. a barchart where the bar heights are equal to the count per period)
    """

    # Filter away journal entries and sort
    events = list(sorted(filter(lambda e: e.type == "data", events)))

    if any_substance:
        for e in events:
            e.data["substance"] = "Any"

    if count or one_per_day:
        period_counts = _count_doses(events, one_per_day=one_per_day, monthly=not daily, verbose=verbose)
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


def _plot_calendar(events, cmap='Reds', fillcolor='whitesmoke', **kwargs):
    import calmap

    # Filter away journal entries and sort
    events = list(sorted(filter(lambda e: e.type == "data", events)))

    for e in events:
        e.data["substance"] = "Any"

    period_counts = _count_doses(events, one_per_day=True, monthly=False)
    assert len(period_counts) == 1

    doses = [n_dose for n_dose in next(iter(period_counts.values())).values()]
    labels = [pd.Timestamp("-".join(map(str, date))) for sd in period_counts for date in period_counts[sd].keys()]

    series = pd.Series(doses, index=labels)
    series = series[~series.index.duplicated()]
    series = series.resample('D').sum().asfreq('D')
    # print(series.tail(20))

    calmap.calendarplot(series, fillcolor=fillcolor, cmap=cmap, linewidth=1, fig_kws=kwargs)
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


def _filter_events(events, start=None, end=None, substances=[]):
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
            e.data["amount"] = str(e.dose.quantity * conc)
    return events


if __name__ == "__main__":
    main()
