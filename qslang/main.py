#!/bin/env python3

import json
import logging
import statistics
from collections import Counter, defaultdict
from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from itertools import groupby

import calplot
import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pint

from . import (
    Dose,
    Event,
    load_events,
    print_events,
)
from .avg_times import mean_time
from .config import load_config, set_global_testing
from .igroupby import igroupby
from .pharmacokinetics import effectspan as _effectspan
from .util import dayrange, monthrange

logger = logging.getLogger(__name__)

# TODO: Make configurable
start_of_day = timedelta(hours=4)


@click.group()
@click.option("-v", "--verbose", is_flag=True)
@click.option("--testing", is_flag=True, help="run with testing config & data")
def main(verbose=False, testing=True):
    """QSlang is a tool to parse and analyze dose logs, for science."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname).4s | %(module)-8s |  %(message)s",
    )

    if testing:
        set_global_testing()
    load_config()


@main.command(help="print list of all doses")
@click.option(
    "--start", type=click.DateTime(["%Y-%m-%d"]), help="start date to filter events by"
)
@click.option(
    "--end", type=click.DateTime(["%Y-%m-%d"]), help="end date to filter events by"
)
@click.option("--substances", help="substances to filter by (comma-separated)")
def events(start: datetime, end: datetime, substances: str | None):
    substances_list = substances.split(",") if substances else []
    events = load_events(start, end, substances_list)
    print_events(events)


@main.command(help="print summary of doses for each substance")
@click.option(
    "--start", type=click.DateTime(["%Y-%m-%d"]), help="start date to filter events by"
)
@click.option(
    "--end", type=click.DateTime(["%Y-%m-%d"]), help="end date to filter events by"
)
@click.option("--substances", help="substances to filter by (comma-separated)")
def summary(start: datetime, end: datetime, substances: str) -> None:
    # TODO: rename function to something more descriptive, like 'summary'?
    substances_list = substances.split(",") if substances else []
    events = load_events(start, end, substances_list)
    events = [e for e in events if e.substance]

    if events:
        for substance, substance_events in igroupby(
            events, lambda e: e.substance
        ).items():
            assert substance
            _print_daily_doses(substance_events, substance)
    else:
        print("No matching events found")


@main.command(help="print effect spans")
@click.option(
    "--start", type=click.DateTime(["%Y-%m-%d"]), help="start date to filter events by"
)
@click.option(
    "--end", type=click.DateTime(["%Y-%m-%d"]), help="end date to filter events by"
)
@click.option("--substances", help="substances to filter by (comma-separated)")
@click.option("--normalize", help="consider all substances a particular substance")
def effectspan(start: datetime, end: datetime, substances: str, normalize: str):
    substances_list = substances.split(",") if substances else []
    events = load_events(start, end, substances_list)
    events = [e for e in events if e.substance]

    if normalize:
        for e in events:
            e.data["substance"] = normalize

    if events:
        effectspans = _effectspan(
            [
                (e.timestamp.replace(tzinfo=timezone.utc), e.dose)
                for e in events
                if e.dose
            ]
        )
        for span in effectspans:
            # will break horribly if any ; in output
            data = span.data
            data["doses"] = [{"amount": d.amount_with_unit} for d in data["doses"]]
            print(
                "; ".join(
                    [
                        span.timestamp.isoformat(),
                        str(span.duration.total_seconds()),
                        json.dumps(data),
                    ]
                )
            )
    else:
        print("No matching events found")


@main.command(help="plot effect spans in a barchart")
@click.option(
    "--start", type=click.DateTime(["%Y-%m-%d"]), help="start date to filter events by"
)
@click.option(
    "--end", type=click.DateTime(["%Y-%m-%d"]), help="end date to filter events by"
)
@click.option("--substances", help="substances to filter by (comma-separated)")
def plot_effectspan(start, end, substances):
    substances_list = substances.split(",") if substances else []
    events = load_events(start, end, substances_list)
    events = [e for e in events if e.substance]

    bars_by_substance = {}

    if events:
        effectspans = _effectspan(
            [
                (e.timestamp.replace(tzinfo=timezone.utc), e.dose)
                for e in events
                if e.dose
            ]
        )

        # now that we have effectspans, we need to plot each span in a bar diagram
        # there can be multiple spans per day
        # we will build the bars grouped by substance

        for substance in {span.data["substance"] for span in effectspans}:
            # list of bars, with (x, y_start, duration) for each bar
            bars = []
            for span in effectspans:
                if span.data["substance"] == substance:
                    bars.append(
                        (
                            span.timestamp.date(),
                            span.timestamp.time(),
                            span.duration,
                        )
                    )

            # split bars crossing the 24h mark
            for bar in bars:
                bar_end_hour = bar[1].hour + bar[2].total_seconds() / 3600
                if bar_end_hour > 24:
                    # create a new bar for the time past midnight
                    bars.append(
                        (
                            bar[0] + timedelta(days=1),
                            time(0, 0),
                            timedelta(hours=bar_end_hour - 24),
                        )
                    )
                    # shorten the original bar
                    bars[bars.index(bar)] = (
                        bar[0],
                        bar[1],
                        timedelta(hours=24 - bar[1].hour),
                    )

            # transform to (x, height, bottom) for each bar
            bars_mpl = [
                (x, duration.total_seconds() / 3600, y_start.hour + y_start.minute / 60)
                for x, y_start, duration in bars
            ]
            bars_by_substance[substance] = bars_mpl

        # plot
        fig, ax = plt.subplots()
        ax.set_xlabel("Date")
        ax.set_ylabel("Hour")

        for subst, subst_bars in bars_by_substance.items():
            x, height, bottom = zip(*subst_bars)
            ax.bar(
                x,
                height,
                bottom=bottom,
                label=subst,
            )
        # ax.bar(x, height, bottom=bottom)
        # invert axis such that each day starts at the top
        ax.set_ylim(0, 24)
        ax.invert_yaxis()
        plt.title("Effectspans where subject is under influence of substance")
        plt.legend()
        plt.show()


@main.command(help="plot percent of time spent under effects of a substance")
@click.option(
    "--start", type=click.DateTime(["%Y-%m-%d"]), help="start date to filter events by"
)
@click.option(
    "--end", type=click.DateTime(["%Y-%m-%d"]), help="end date to filter events by"
)
@click.option("--substances", help="substances to filter by (comma-separated)")
def plot_influence(start, end, substances):
    substances_list = substances.split(",") if substances else []
    events = load_events(start, end, substances_list)
    events = [e for e in events if e.substance]

    if events:
        effectspans = _effectspan(
            [
                (e.timestamp.replace(tzinfo=timezone.utc), e.dose)
                for e in events
                if e.dose
            ]
        )

        # count the number of hours spent under the influence of each substance, by day
        # we will build a dict of {substance: {date: hours}}
        # TODO: Handle spans that cross the day boundary
        hours_by_substance_by_day: dict[str, dict[date, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for span in effectspans:
            substance = span.data["substance"]
            day = (span.timestamp - day_offset).date()
            hours_by_substance_by_day[substance][day] += (
                span.duration.total_seconds() / 3600
            )

        # plot
        fig, ax = plt.subplots()
        ax.set_xlabel("Date")
        ax.set_ylabel("Hours")

        # plot bars
        for subst, hours_by_day in hours_by_substance_by_day.items():
            x = list(hours_by_day.keys())
            y = list(hours_by_day.values())
            ax.bar(x, y, label=subst)

            # plot a line for the moving average, with pandas
            df = pd.DataFrame({"days": x, "hours": y})
            df = df.set_index("days")
            df = df.reindex(
                pd.date_range(start=df.index.min(), end=df.index.max()), fill_value=0
            )
            df["rolling"] = df["hours"].rolling(7).mean()
            ax.plot(df.index, df["rolling"], label=f"{subst} 7D MA")

        ax.set_ylim(0, 24)
        plt.title("Hours spent under the influence of substance")
        plt.legend()
        plt.show()


@main.command(help="print list of substances")
@click.option(
    "--start", type=click.DateTime(["%Y-%m-%d"]), help="start date to filter events by"
)
@click.option(
    "--end", type=click.DateTime(["%Y-%m-%d"]), help="end date to filter events by"
)
@click.option("--substances", help="substances to filter by (comma-separated)")
@click.option(
    "--group-day",
    is_flag=True,
    help="group by day, counting each day with a dose instead of each dose",
)
def substances(start, end, substances, group_day=True) -> None:
    substances_list = substances.split(",") if substances else []
    events = load_events(start, end, substances_list)
    # group by substance
    # then, if group_day, group by day and then count number of days
    c = Counter(
        {
            k: len(v)
            if not group_day
            else len({d for d in [e.timestamp.date() for e in v if e.timestamp.date()]})
            for k, v in igroupby(
                [e for e in events if e.substance],
                lambda e: e.substance,
            ).items()
        }
    )

    for s, n in c.most_common():
        print(f"{n}x\t{s}")
    print(f"{len(c)} substances found")


@main.command(help="plot doses over time in a barchart")
@click.option(
    "--start", type=click.DateTime(["%Y-%m-%d"]), help="start date to filter events by"
)
@click.option(
    "--end", type=click.DateTime(["%Y-%m-%d"]), help="end date to filter events by"
)
@click.option("--substances", help="substances to filter by (comma-separated)")
@click.option("--any", is_flag=True, help="count all matches as any match")
@click.option("--daily", is_flag=True, help="use daily resolution on the x-axis")
@click.option("--count", is_flag=True, help="count number of doses instead of amount")
@click.option("--days", is_flag=True, help="count number of days with doses")
def plot(
    start: datetime | None,
    end: datetime | None,
    substances: str,
    any: bool,
    daily: bool,
    count: bool,
    days: bool,
):
    substances_list = substances.split(",") if substances else []
    events = load_events(start, end, substances_list)
    _plot_frequency(
        events, count=count or days, one_per_day=days, daily=daily, any_substance=any
    )


@main.command(help="plot doses in a calendar")
@click.option(
    "--start", type=click.DateTime(["%Y-%m-%d"]), help="start date to filter events by"
)
@click.option(
    "--end", type=click.DateTime(["%Y-%m-%d"]), help="end date to filter events by"
)
@click.option("--substances", help="substances to filter by (comma-separated)")
def plot_calendar(start: datetime | None, end: datetime | None, substances: str):
    substances_list = substances.split(",") if substances else []
    events = load_events(start, end, substances_list)
    _plot_calendar(events)


def _print_daily_doses(
    events: list[Event], substance: str, ignore_doses_fewer_than=None
):
    events = [
        e
        for e in events
        if e.substance and e.substance.lower() == substance.lower() and e.dose
    ]
    if not events:
        logger.info(f"No doses found for substance '{substance}'")
        return

    # NOTE: Respects the 'start of day' setting when grouping by date
    grouped_by_date = igroupby(
        sorted(events), key=lambda e: (e.timestamp - start_of_day).date()
    )
    assert events[0].dose
    # outer accumulator (all days)
    tot_amt = Dose(substance, events[0].dose.quantity * 0)
    for _, v in grouped_by_date.items():
        valid_doses = [
            entry.dose
            for entry in v
            if entry.dose
            and entry.dose.quantity.magnitude > 0
            and entry.dose.quantity.units != "dimensionless"
        ]

        # if no valid doses, skip day
        if not valid_doses:
            continue

        # find first non-zero non-dimensionless dose to use as accumulator
        # FIXME: accumulate by unit type (g, l, x, puffs, etc)
        initdose = valid_doses[0]

        try:
            # inner accumulator (per day)
            amt = Dose(substance, initdose.quantity * 0)
            for e in v:
                if e.dose and e.dose.quantity.magnitude > 0:
                    amt += e.dose
            # add to outer accumulator
            tot_amt += amt
        except Exception as e:
            logger.exception(f"Unable to sum amounts '{v}', '{tot_amt}': {e}")
            # logger.warning(f"initdose: {initdose}")
            # logger.warning(f"dose to add: {e}")

    if ignore_doses_fewer_than and ignore_doses_fewer_than > len(grouped_by_date):
        return

    # TODO: Use Counter

    print(f"{substance}:")
    print(
        f" - latest: {max(grouped_by_date)} ({(date.today() - max(grouped_by_date)).days} days ago)"
    )
    print(
        f" - oldest: {min(grouped_by_date)} ({(date.today() - min(grouped_by_date)).days} days ago)"
    )
    print(f" - {len(grouped_by_date)} days totalling {tot_amt.amount_with_unit}")
    print(f" - avg dose/day: {tot_amt/len(events)}")

    firstlast_dose_times: tuple[list[datetime], list[datetime]] = tuple(
        zip(
            *[
                (
                    min(e.timestamp - start_of_day for e in events) + start_of_day,
                    max(e.timestamp - start_of_day for e in events) + start_of_day,
                )
                for events in grouped_by_date.values()
            ]
        )
    )  # type: ignore
    first_dose_times, last_dose_times = firstlast_dose_times

    avg_time_of_first_dose = mean_time([t.time() for t in first_dose_times])
    avg_time_of_last_dose = mean_time([t.time() for t in last_dose_times])
    print(
        f" - avg time of first/last daily dose: {avg_time_of_first_dose}/{avg_time_of_last_dose}"
    )

    try:
        median_dose = statistics.median(e.dose for e in events if e.dose)  # type: ignore
        min_dose = min(e.dose for e in events if e.dose)
        max_dose = max(e.dose for e in events if e.dose)
        print(
            f" - min/median/max dose: {min_dose.amount_with_unit}/{median_dose.amount_with_unit}/{max_dose.amount_with_unit}"
        )
    except (pint.errors.DimensionalityError, AssertionError):
        logger.warning(
            "Couldn't compute min/median/max doses due to inconsistent units"
        )
    grouped_by_roa = igroupby(events, key=lambda e: e.roa)
    print(" - ROAs:")
    for roa in sorted(grouped_by_roa, key=lambda v: grouped_by_roa[v]):
        print(f"   - {roa.ljust(10)}  n: {len(grouped_by_roa[roa])}")


TDate = tuple[int, int, int | None]

day_offset = timedelta(hours=-4)


def _grouped_by_date(events: list[Event], monthly=True) -> dict[TDate, list[Event]]:
    grouped_by_date: dict[TDate, list[Event]] = defaultdict(list)
    for period, events_grouped in groupby(
        events,
        key=lambda e: (
            (e.timestamp + day_offset).year,
            (e.timestamp + day_offset).month,
            None if monthly else (e.timestamp + day_offset).day,
        ),
    ):
        grouped_by_date[period] = list(events_grouped)
    return grouped_by_date


TValueByDate = dict[TDate, float]


def _dosesum(doses):
    doses = list(doses)
    if not doses:
        return 0
    acc = doses[0]
    for dose in doses[1:]:
        acc += dose
    return acc


def _sum_doses(events: list[Event], monthly=True) -> dict[str, TValueByDate]:
    substances = {e.substance for e in events if e.substance}
    events = [e for e in events if e.dose]
    grouped_by_date = _grouped_by_date(events, monthly=monthly)

    period_counts: dict[str, dict[TDate, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for period in grouped_by_date.keys():
        events_g_date = grouped_by_date[period]
        events_g_substance = igroupby(events_g_date, key=lambda e: e.substance)
        c = Counter(
            {
                substance: _dosesum(e.dose for e in _events)
                for substance, _events in events_g_substance.items()
                if substance
            }
        )

        for k, v in c.most_common(20):
            assert k
            print(f" - {v}")

        for s in substances:
            period_counts[s][period] = c[s].quantity.to_base_units().magnitude if isinstance(c[s], Dose) else 0  # type: ignore

    return period_counts


def _count_doses(
    events: list[Event], one_per_day=True, monthly=True, verbose=False
) -> dict[str, TValueByDate]:
    substances = {e.substance for e in events if e.substance}
    grouped_by_date = _grouped_by_date(events, monthly=monthly)

    period_counts: dict[str, dict[TDate, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for period in grouped_by_date.keys():
        events = grouped_by_date[period]
        grouped_by_substance = igroupby(events, key=lambda e: e.substance)
        c = Counter(
            {
                substance: (
                    len({(e.timestamp + day_offset).date() for e in events})
                    if one_per_day
                    else len(events)
                )
                for substance, events in grouped_by_substance.items()
            }
        )
        unit = " days" if one_per_day else "x"

        if verbose:
            print(period)
            for k, v in c.most_common(20):
                print(f" - {v}{unit} {k}")

        for s in substances:
            period_counts[s][period] = c[s]

    return period_counts


def _plot_frequency(
    events,
    count=False,
    one_per_day=False,
    any_substance=False,
    daily=False,
    verbose=False,
    figsize: tuple[int, int] | None = None,
):
    """
    Should plot frequency of use over time
    (i.e. a barchart where the bar heights are equal to the count per period)
    """
    plt.figure(figsize=figsize if figsize else None)

    # Filter away journal entries and sort
    events = list(sorted(filter(lambda e: e.type == "dose", events)))
    assert events

    if any_substance:
        for e in events:
            e.data["substance"] = "Any"

    if count or one_per_day:
        period_counts = _count_doses(
            events, one_per_day=one_per_day, monthly=not daily, verbose=verbose
        )
    else:
        period_counts = _sum_doses(events, monthly=not daily)

    labels: list[tuple[int, int, int]] = [
        (date[0], date[1], date[2] or 0)
        for sd in period_counts
        for date in period_counts[sd].keys()
    ]
    if daily:
        labels = dayrange(min(labels), max(labels))
    else:
        labels = [(m[0], m[1], 1) for m in monthrange(min(labels)[:2], max(labels)[:2])]
    fmt = "%Y-%m-%d" if daily else "%Y-%m"
    labels_date = [datetime(*t).strftime(fmt) for t in labels]

    stackheight = np.zeros(len(labels))
    for substance, value_by_date in period_counts.items():
        n = [
            value_by_date.get(label if daily else (*label[:2], None), 0)
            for label in labels
        ]
        # check that n is not all zeros (indication of indexing error)
        assert any(n)
        plt.bar(labels_date, n, label=substance, bottom=stackheight)
        stackheight += np.array(n)

    plt.xticks(rotation="vertical")
    plt.legend()
    plt.show()


def _plot_calendar(
    events,
    cmap="YlGn",
    fillcolor="whitesmoke",
    figsize=None,
    one_per_day=True,
    **kwargs,
):
    # suitable values for cmap: Reds, YlGn

    # Filter away journal entries and sort
    events = list(sorted(filter(lambda e: e.type == "dose", events)))
    assert events, "No events found"

    for e in events:
        e.data["substance"] = "Any"

    # TODO: use dose or dose equivalents instead of count
    period_counts = _count_doses(events, one_per_day=False, monthly=False)
    assert len(period_counts) == 1

    doses = [n_dose for n_dose in next(iter(period_counts.values())).values()]
    labels = [
        pd.Timestamp("-".join(map(str, date)))
        for sd in period_counts
        for date in period_counts[sd].keys()
    ]

    series = pd.Series(doses, index=labels)
    series = series[~series.index.duplicated()]
    series = series.resample("D").sum().asfreq("D")

    calplot.calplot(
        series,
        fillcolor=fillcolor,
        cmap=cmap,
        linewidth=1,
        figsize=figsize,
        vmin=0,
        vmax=1 if one_per_day else max(series),
        dropzero=False,
        fig_kws=kwargs,
    )
    plt.show()


if __name__ == "__main__":
    main()
