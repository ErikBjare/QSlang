#!/bin/env python3

from qslang.util import dayrange, monthrange


def test_monthrange():
    months = monthrange((2017, 1), (2018, 4))
    assert len(months) == 12 + 4


def test_dayrange():
    days = dayrange((2017, 12, 20), (2017, 12, 31))
    assert len(days) == 12

    days = dayrange((2017, 12, 20), (2018, 2, 4))
    assert len(days) == 12 + 31 + 4
