from typing import List, Dict, Callable, TypeVar, Any
from itertools import groupby

T = TypeVar('T')
K = Any  # Should be `TypeVar('K')`, see issue: https://github.com/python/mypy/issues/5464


def igroupby(l: List[T], key: Callable[[T], K]=lambda x: x) -> Dict[K, List[T]]:
    return {k: list(v) for k, v in groupby(sorted(l, key=key), key=key)}


result1: Dict[int, List[float]] = igroupby([1.2, 1.5, 2], key=lambda x: round(x))
result2: Dict[int, List[int]] = igroupby([1, 1, 2], key=lambda x: round(x))
