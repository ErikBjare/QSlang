#!/bin/env python3

import logging
import itertools
from typing import List, Dict, Tuple
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


def monthrange(min_date: Tuple[int, int], max_date: Tuple[int, int]):
    (min_year, min_month) = min_date
    (max_year, max_month) = max_date
    g = itertools.product(range(min_year, max_year + 1), range(1, 13))
    g = itertools.dropwhile(lambda t: t < (min_year, min_month), g)
    return list(itertools.takewhile(lambda t: t <= (max_year, max_month), g))
