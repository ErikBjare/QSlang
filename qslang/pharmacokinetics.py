from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from dose import Dose


def compute_plasma(doses):
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
        df.at[dt, "administered"] = dose.amount

    df["C"] = 0.0
    df["unabsorbed"] = df["administered"]
    for i in df.index[1:]:
        stepsize = i.freq / pd.Timedelta(halflife)
        stepsize_abs = i.freq / pd.Timedelta(absorbtion_halflife)
        df.loc[i, "unabsorbed"] += df.loc[i - 1, "unabsorbed"] * np.exp2(
            -1 * stepsize_abs
        )
        df.loc[i, "C"] += df.loc[i - 1, "C"] * np.exp2(-stepsize) + df.loc[
            i - 1, "unabsorbed"
        ] * (1 - np.exp2(-stepsize_abs))

    df["C"].plot(label="plasma")
    df["unabsorbed"].plot(label="unabsorbed")
    plt.legend()
    plt.show()

    print(df)


doses = [
    [datetime(2018, 9, 10, 8), Dose("Caffeine", "50mg")],
    [datetime(2018, 9, 10, 12), Dose("Caffeine", "50mg")],
]


if __name__ == "__main__":
    compute_plasma(doses)
