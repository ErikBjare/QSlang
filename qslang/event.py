#!/bin/env python3

import logging
import json
from copy import copy
from typing import List, Dict, Any, Optional, Hashable
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
    type: str
    data: dict = field(compare=False)

    def __hash__(self):
        return hash((self.timestamp, self.type, _freeze(self.data)))

    @property
    def tags(self) -> List[str]:
        return self.data["tags"] if "tags" in self.data else []

    @property
    def substance(self) -> Optional[str]:
        return self.data["substance"] if "substance" in self.data else None

    @property
    def dose(self) -> Optional[Dose]:
        if self.substance and self.amount:
            try:
                return Dose(self.substance, self.amount)
            except Exception as e:
                log.warning(f"Unable to build Dose object: {e}")
                return None
        else:
            return None

    @property
    def amount(self):
        # TODO: Move stripping of '~' etc into parsing and annotate meaning using tags?
        return (
            self.data["amount"].strip("~")
            if "amount" in self.data and "?" not in self.data["amount"]
            else None
        )

    @property
    def roa(self):
        return self.data["roa"] if "roa" in self.data else "unknown"

    def prettyprint(self, show_misc=False) -> None:
        if self.type == "data" and "amount" in self.data and "substance" in self.data:
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
    def json_dict(self) -> Dict[str, Any]:
        return {"timestamp": self.timestamp, "type": self.type, "data": self.data}

    @property
    def json_str(self) -> str:
        return json.dumps(self.json_dict)


def print_events(events: List[Event]) -> None:
    last_date: Optional[datetime] = None
    for e in events:
        if last_date and last_date.date() != e.timestamp.date():
            print(
                f"{str(last_date.date()).ljust(8)} =========|=========|====== New day ====="
            )
        e.prettyprint()
        last_date = e.timestamp
