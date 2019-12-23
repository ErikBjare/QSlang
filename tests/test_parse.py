#!/bin/env python3

import re
import logging
import typing
from typing import List, Dict, Any, Tuple, Optional
from datetime import time, datetime, timedelta

from qslang.event import Event
from qslang.parse import *
from qslang.parse import _pop_regex


def test_pop_regex():
    s, match = _pop_regex("100mg", re_amount)
    assert match
    assert not s


def test_parse():
    test1 = """
    # 2018-04-14
    16:30 - Started working on qslang
    ~17:12 - Made progress
    18:12 - ~1dl Green tea + 5g Cocoa
    """
    events = parse(test1)
    assert len(events) == 4
    assert events[0].timestamp == datetime(2018, 4, 14, 16, 30)
    assert events[0].data["raw"] == "Started working on qslang"

    assert events[1].timestamp == datetime(2018, 4, 14, 17, 12)
    assert events[1].data["raw"] == "Made progress"

    assert events[2].substance == "Green tea"
    assert events[2].amount == "1dl"

    assert events[3].substance == "Cocoa"
    assert events[3].amount == "5g"


def test_parse_amount():
    test_str = """
    # 2018-04-14
    12:00 - 30 situps
    12:01 - 30x situps
    12:02 - 2tbsp sugar
    """
    events = parse(test_str)
    assert len(events) == 3
    assert events[0].amount == "30"
    assert events[1].amount == "30x"
    assert events[2].amount == "2tbsp"


def test_parse_roa():
    test_str = """
    # 2018-04-14
    12:00 - 1x Otrivin intranasal
    12:01 - 1x Somethingwithoralinit subcutaneous
    """
    events = parse(test_str)
    assert len(events) == 2
    assert events[0].substance == "Otrivin"
    assert events[0].roa == "intranasal"
    assert events[1].substance == "Somethingwithoralinit"
    assert events[1].roa == "subcutaneous"


def test_parse_with_plus_in_extras():
    test_str = """
    # 2018-04-14
    12:00 - 1x Something (50mg Caffeine + 100mg L-Theanine)
    """
    events = parse(test_str)
    assert len(events) == 3

    assert events[0].substance == "Something"
    assert events[0].amount == "1x"

    assert events[1].substance == "Caffeine"
    assert events[1].amount == "50mg"

    assert events[2].substance == "L-Theanine"
    assert events[2].amount == "100mg"


def test_alcoholic_drink():
    test_str = """
    # 2018-08-18
    ~21:00 - 33cl Beer (Pistonhead Kustom Lager, 5.9%)
    """
    events = parse(test_str)
    assert events[0].data["concentration"] == "5.9%"
    assert len(events) == 1


def test_complex_extras():
    test_str = """
    # 2018-08-20
    08:00 - 1x Generic Multivitamin (Generic Brand, 1000IU Vitamin D3 + 25mg Zinc Picolinate)
    """
    events = parse(test_str)
    assert len(events) == 3
    assert len(events[0].data["subevents"]) == 2
    assert "Generic Brand" in events[0].data["attributes"]
