#!/bin/env python3

import logging
import json
from copy import copy
from typing import Any, Literal
from collections.abc import Hashable
from datetime import datetime

from dataclasses import dataclass, field

from .dose import Dose


log = logging.getLogger(__name__)


def _freeze(obj: Any) -> Any:
    if isinstance(obj, Hashable):
        return obj
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, list):
        return tuple(_freeze(x) for x in obj)
    elif isinstance(obj, dict):
        return tuple((k, _freeze(v)) for k, v in obj.items())
    else:
        raise ValueError("Cannot freeze object of type %s" % type(obj))


@dataclass(order=True)
class Event:
    timestamp: datetime
    type: Literal["dose"] | Literal["journal"]
    data: dict = field(compare=False)

    def __hash__(self):
        return hash((self.timestamp, self.type, _freeze(self.data)))

    @property
    def tags(self) -> list[str]:
        return self.data["tags"] if "tags" in self.data else []

    @property
    def substance(self) -> str | None:
        return self.data["substance"] if "substance" in self.data else None

    @property
    def dose(self) -> Dose | None:
        if self.type == "dose":
            try:
                assert self.substance
                # NOTE: Amount could be None, if specified as unknown ("?") in entry
                return Dose(self.substance, self.amount or 0)
            except Exception as e:
                print(self.data)
                log.warning(f"Unable to build Dose object: {e}")
                return None
        else:
            return None

    @property
    def amount(self) -> float | None:
        """Returns the amount with unit, or None"""
        try:
            assert "dose" in self.data
            assert "amount" in self.data["dose"]
            amount = self.data["dose"]["amount"]
            assert amount != "unknown"
            return str(amount) + self.data["dose"]["unit"]
        except AssertionError:
            return None

    @property
    def roa(self) -> str:
        try:
            assert "dose" in self.data
            assert "roa" in self.data["dose"]
            return self.data["dose"]["roa"]
        except AssertionError:
            return "unknown"

    def prettyprint(self, show_misc=False) -> None:
        if self.type == "dose" and "amount" in self.data and "substance" in self.data:
            d = self.data
            misc = copy(self.data)
            misc.pop("amount")
            misc.pop("substance")
            if self.dose:
                base_str = str(self.dose)
            else:
                base_str = f"{d['amount'] if 'amount' in d else '?'} {d['substance']}"
            misc_str = f"  -  {misc}" if show_misc else ""
            e_str = base_str + misc_str
        else:
            e_str = str(self.data)
        print(f"{self.timestamp.isoformat()} | {self.type.ljust(7)} | " + e_str)

    @property
    def json_dict(self) -> dict[str, Any]:
        return {"timestamp": self.timestamp, "type": self.type, "data": self.data}

    @property
    def json_str(self) -> str:
        return json.dumps(self.json_dict)


def print_events(events: list[Event]) -> None:
    last_date: datetime | None = None
    for e in events:
        if last_date and last_date.date() != e.timestamp.date():
            print(
                f"{str(last_date.date()).ljust(8)} =========|=========|====== New day ====="
            )
        e.prettyprint()
        last_date = e.timestamp
