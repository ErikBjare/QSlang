#!/bin/env python3

import logging
import itertools
import calendar
from typing import Dict, Tuple, List
from collections import defaultdict


log = logging.getLogger(__name__)


class MsgCounterHandler(logging.Handler):
    """https://stackoverflow.com/a/31142078/965332"""

    level2count: Dict[str, int]

    def __init__(self, *args, **kwargs) -> None:
        super(MsgCounterHandler, self).__init__(*args, **kwargs)
        self.level2count = defaultdict(int)

    def emit(self, record) -> None:
        self.level2count[record.levelname] += 1


def days_in_month(year, month):
    return max(list(calendar.Calendar().itermonthdays(year, month)))


def monthrange(
    min_date: Tuple[int, int], max_date: Tuple[int, int]
) -> List[Tuple[int, int]]:
    (min_year, min_month) = min_date
    (max_year, max_month) = max_date
    g = itertools.product(range(min_year, max_year + 1), range(1, 13))
    g = itertools.dropwhile(lambda t: t < (min_year, min_month), g)
    return list(itertools.takewhile(lambda t: t <= (max_year, max_month), g))


def dayrange(
    min_date: Tuple[int, int, int], max_date: Tuple[int, int, int]
) -> List[Tuple[int, int, int]]:
    months = monthrange(min_date[:2], max_date[:2])
    return [
        (y, m, d)
        for y, m in months
        for d in range(1, days_in_month(y, m) + 1)
        if min_date <= (y, m, d) <= max_date
    ]
