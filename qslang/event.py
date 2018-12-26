#!/bin/env python3

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from dataclasses import dataclass, field

from .dose import Dose


log = logging.getLogger(__name__)


@dataclass(order=True)
class Event:
    timestamp: datetime
    type: str
    data: dict = field(compare=False)

    @property
    def tags(self) -> List[str]:
        return self.data["tags"] if "tags" in self.data else []

    @property
    def substance(self) -> Optional[str]:
        return self.data["substance"].strip() if "substance" in self.data else None

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
        return self.data["amount"].strip("~") if "amount" in self.data and "?" not in self.data["amount"] else None

    @property
    def roa(self):
        return self.data["roa"] if "roa" in self.data else "unknown"

    @property
    def json_dict(self) -> Dict[str, Any]:
        return {"timestamp": self.timestamp, "type": self.type, "data": self.data}

    @property
    def json_str(self) -> str:
        return json.dumps(self.json_dict)
