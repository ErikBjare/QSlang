from typing import TypeVar, overload, no_type_check
from collections.abc import Callable
from itertools import groupby

T = TypeVar("T")
K = TypeVar("K")


# Overload necessary here, see issue: https://github.com/python/mypy/issues/5464
@overload
def igroupby(l: list[T]) -> dict[K, list[K]]:
    ...


@overload  # noqa: F811
def igroupby(l: list[T], key: Callable[[T], K]) -> dict[K, list[T]]:
    ...


def igroupby(l, key=lambda x: x):  # noqa: F811
    return {k: list(v) for k, v in groupby(sorted(l, key=key), key=key)}


def test_igroupby() -> None:
    d0: dict[int, list[int]] = igroupby([1, 1, 2])
    assert len(d0[1]) == 2
    assert len(d0[2]) == 1

    d1: dict[int, list[float]] = igroupby([1.2, 1.5, 2], key=lambda x: round(x))
    assert len(d1[1]) == 1
    assert len(d1[2]) == 2

    d2: dict[int, list[int]] = igroupby([1, 1, 2], key=lambda x: round(x))
    assert len(d2[1]) == 2
    assert len(d2[2]) == 1

    t0: dict[int, list[int]] = igroupby([1, 2])  # noqa: F841
    t1: dict[str, list[int]] = igroupby([1, 2], key=lambda x: str(x))  # noqa: F841


@no_type_check
def invalid_used_types() -> None:
    # Just tests for making sure the overload works correctly,
    # comment the function decorator to get the errors.
    t0: dict[str, list[int]] = igroupby([1, 2])  # noqa: F841
    t1: dict[int, list[int]] = igroupby([1, 2], key=lambda x: str(x))  # noqa: F841
