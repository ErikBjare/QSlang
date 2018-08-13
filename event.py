#!/bin/env python3

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from dataclasses import dataclass, field

from dose import Dose


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
        if isinstance(self.data, dict):
            return self.data["substance"].strip() if "substance" in self.data else None
        else:
            return "unknown/journal"

    @property
    def dose(self) -> Optional[Dose]:
        if self.substance and "amount" in self.data:
            try:
                return Dose(self.substance, self.data["amount"])
            except Exception as e:
                log.warning(f"Unable to build Dose object: {e}")
                return None
        else:
            return None

    @property
    def unit(self):
        return self.dose.unit if self.dose else None

    @property
    def roa(self):
        return self.data["roa"] if "roa" in self.data else "unknown"

    @property
    def json_dict(self) -> Dict[str, Any]:
        return {"timestamp": self.timestamp, "type": self.type, "data": self.data}

    @property
    def json_str(self) -> str:
        return json.dumps(self.json_dict)
