from datetime import datetime, timedelta, timezone
from collections import defaultdict
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from aw_core import Event
from . import Dose


logger = logging.getLogger(__name__)


def compute_plasma(doses: list[tuple[datetime, Dose]]):
    # https://pharmacy.ufl.edu/files/2013/01/5127-28-equations.pdf
    absorbtion_halflife = timedelta(minutes=30)
    halflife = timedelta(minutes=4 * 60)
    idx = pd.date_range(
        start=doses[0][0],
        end=doses[-1][0] + timedelta(hours=12),
        freq=timedelta(minutes=30),
    )
    df = pd.DataFrame(index=idx)
    df["administered"] = 0.0

    for dt, dose in doses:
        print(dose.quantity)
        df.at[dt, "administered"] = dose.quantity.magnitude

    df["C"] = 0.0
    df["unabsorbed"] = df["administered"]
    for i in df.index[1:]:
        stepsize = i.freq / pd.Timedelta(halflife)
        stepsize_abs = i.freq / pd.Timedelta(absorbtion_halflife)
        df.loc[i, "unabsorbed"] += df.loc[i - i.freq, "unabsorbed"] * np.exp2(
            -1 * stepsize_abs
        )
        df.loc[i, "C"] += df.loc[i - i.freq, "C"] * np.exp2(-stepsize) + df.loc[
            i - i.freq, "unabsorbed"
        ] * (1 - np.exp2(-stepsize_abs))

    df["C"].plot(label="plasma")
    df["unabsorbed"].plot(label="unabsorbed")
    plt.legend()
    plt.show()

    print(df)


# Durations for different substances
# TODO: Read from file instead of hardcode (crawl psychonautwiki?)
# TODO: Combine substance with several names (weed/cannabis/hash, beer/wine/whiskey, etc.)
subst_durations = {
    # NOTE: these are synonyms, and should be converted
    "caffeine": timedelta(hours=5),
    "coffee": timedelta(hours=5),
    #
    # NOTE: these are synonyms, and should be converted
    "cannabis": timedelta(hours=3),
    "weed": timedelta(hours=3),
    "hash": timedelta(hours=3),
    #
    # NOTE: Alcohol clearance is badly modeled by a halflife or fixed duration, as clearance is ~constant.
    #       From a search: "Alcohol leaves the body at an average rate of 0.015 g/100mL/hour"
    # NOTE: This also has synonyms (Drink, Beer, Wine, Whiskey, etc.)
    "alcohol": timedelta(hours=4),
}


def effectspan_substance(doses: list[tuple[datetime, Dose]]) -> list[Event]:
    """
    Given a list of doses for a particular substance, return a list of events
    spanning the time during which the substance was active (according to durations specified in a dictionary).
    """
    subst = doses[0][1].substance.lower()

    # TODO: Incorporate time-until-effect into the calculation
    # assert all doses of same substance
    assert all(dose.substance.lower() == subst for (_, dose) in doses)

    # assert we have duration data for the substance
    if subst not in subst_durations:
        raise ValueError(f"Unknown effect duration for substance: {subst}")

    # sort
    doses = sorted(doses, key=lambda x: x[0])

    # compute effectspan for each dose, merge overlaps
    events: list[Event] = []
    for dt, dose in doses:
        end = dt + subst_durations[subst]

        # checks if last event overlaps with dose, if so, extend it
        if len(events) > 0:
            last_event = events[-1]
            # if last event ends before dose starts
            if (last_event.timestamp + last_event.duration) > dt:
                # events overlap
                last_event.duration = end - last_event.timestamp
                last_event.data["doses"].append(dose)
                continue

        e = Event(
            timestamp=dt,
            duration=subst_durations[subst],
            data={"substance": subst, "doses": [dose]},
        )
        events.append(e)

    return events


def effectspan(doses: list[tuple[datetime, Dose]]) -> list[Event]:
    """
    Given a list of doses, computes all spans of time during which the substance is active.
    """
    doses = sorted(doses, key=lambda x: x[0])

    # Group by substance
    groups = defaultdict(list)
    for dt, dose in doses:
        groups[dose.substance].append((dt, dose))

    # Compute effectspan for each substance
    events = []
    for substance, doses in groups.items():
        try:
            events.extend(effectspan_substance(doses))
        except ValueError as e:
            logger.warning(f"Failed to compute effectspan for {substance}: {e}")

    return events


def example():
    doses = [
        (datetime(2018, 9, 10, 8, tzinfo=timezone.utc), Dose("Caffeine", "50mg")),
        (datetime(2018, 9, 10, 12, tzinfo=timezone.utc), Dose("Caffeine", "50mg")),
    ]
    compute_plasma(doses)


def test_effectspan():
    doses = [
        (datetime(2018, 9, 10, 8, tzinfo=timezone.utc), Dose("Caffeine", "75mg")),
        (datetime(2018, 9, 10, 12, tzinfo=timezone.utc), Dose("Caffeine", "50mg")),
        (datetime(2018, 9, 10, 16, 20, tzinfo=timezone.utc), Dose("Cannabis", "0.03g")),
        (datetime(2018, 9, 10, 19, tzinfo=timezone.utc), Dose("Cannabis", "0.05g")),
    ]
    events = effectspan(doses)
    for e in events:
        print(e)


if __name__ == "__main__":
    test_effectspan()
    example()
