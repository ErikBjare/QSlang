#!/bin/env python3

import logging
import pint
from typing import Union, Any


log = logging.getLogger(__name__)


ureg = pint.UnitRegistry()
ureg.define("micro- = 10**-6 = mc- = μ-")
ureg.define("micro- = 10**-6 = mc- = μ-")

# The type here is because mypy doesn't like this dynamically created type
Q_ = ureg.Quantity  # type: Any


class Dose:
    def __init__(self, substance: str, amount: Union[str, Q_]) -> None:
        self.substance: str = substance
        if isinstance(amount, ureg.Quantity):
            self.quantity = amount
        else:
            self.quantity = Q_(amount)

    def __str__(self) -> str:
        return f"{self.amount_with_unit} {self.substance}"

    @property
    def amount_with_unit(self) -> str:
        q = self.quantity.to_compact()
        # print(q)
        amount = q.magnitude
        amount = round(amount) if round(amount, 8) % 1.0 == 0 else amount
        return f"{amount}{q.units:~P}"

    def __repr__(self):
        return f"<Dose {self}>"

    def __add__(self, other: "Dose") -> "Dose":
        assert self.substance.lower() == other.substance.lower()
        return Dose(self.substance, self.quantity + other.quantity)

    def __truediv__(self, b):
        return Dose(self.substance, self.quantity / b)

    def __lt__(self, other):
        return self.quantity < other.quantity

    def __eq__(self, other):
        return (
            self.substance == other.substance
            and round((self.quantity - other.quantity).magnitude, 18) == 0
        )
