from typing import List, Dict, Callable, TypeVar, Any
from itertools import groupby

T = TypeVar('T')
K = Any  # Should be `TypeVar('K')`, see issue: https://github.com/python/mypy/issues/5464


def igroupby(l: List[T], key: Callable[[T], K]=lambda x: x) -> Dict[K, List[T]]:
    return {k: list(v) for k, v in groupby(sorted(l, key=key), key=key)}


def test_igroupby() -> None:
    d0: Dict[int, List[int]] = igroupby([1, 1, 2])
    assert len(d0[1]) == 2
    assert len(d0[2]) == 1

    d1: Dict[int, List[float]] = igroupby([1.2, 1.5, 2], key=lambda x: round(x))
    assert len(d1[1]) == 1
    assert len(d1[2]) == 2

    d2: Dict[int, List[int]] = igroupby([1, 1, 2], key=lambda x: round(x))
    assert len(d2[1]) == 2
    assert len(d2[2]) == 1
