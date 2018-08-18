#!/bin/env python3

import re
import logging
from typing import Tuple


log = logging.getLogger(__name__)

_r = re.compile(r"([0-9]+\.?[0-9]*e?-?[0-9]*)(μ|u|mc|d|c|m)?(l|g)?")


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
    elif p in ["mc", "u", "μ"]:
        n *= 0.000001
    return n


def _best_prefix(n: float) -> Tuple[str, float]:
    if 1e-6 <= n < 1e-3:
        return "u", 0.000001
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
        assert self.substance.lower() == other.substance.lower()
        try:
            assert self.unit == other.unit
        except AssertionError as e:
            log.warning(f"Units were not equal: '{self.unit}' != '{other.unit}'")
            raise e
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
    assert _sum_amount("100mcg", "100ug") == "200.0ug"
    assert _sum_amount("100mcg", "100μg") == "200.0ug"

    assert _sum_amount("1ml", "2ml") == "3.0ml"
    assert _sum_amount("1dl", "4dl") == "500.0ml"
    assert _sum_amount("1.0dl", "0l") == "100.0ml"

    assert _sum_amount("33cl", "1l") == "1.33l"
