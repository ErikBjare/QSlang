#!/bin/env python3

import logging
from typing import Any

import pint

log = logging.getLogger(__name__)


ureg = pint.UnitRegistry(
    preprocessors=[
        lambda s: s.replace("%", "percent"),
        lambda s: s.replace("%%", "permille"),
    ]
)

ureg.define("micro- = 10**-6 = mc- = μ-")
ureg.define("percent = 0.01 = %")
ureg.define("permille = 0.001 = %%")


ureg.define("cup = 2*dl")

# NOTE: Not sure if this is correct? But gets rid of the warnings...
ureg.define("x = count")
ureg.define("IU = x")  # for now
ureg.define("CFU = x")  # for now
ureg.define("unknown = x")  # for now
ureg.define("serving = x")  # for now
ureg.define("puff = x")  # for now
ureg.define("puffs = x")  # for now

ureg.define("B = 10**9 * x")  # for noting billions of CFU, for example

# The type here is because mypy doesn't like this dynamically created type
Q_: Any = ureg.Quantity


class Dose:
    def __init__(self, substance: str, amount: str | Q_) -> None:
        self.substance: str = substance
        if not isinstance(amount, ureg.Quantity):
            self.quantity = Q_(amount)
        else:
            self.quantity = amount

    def __str__(self) -> str:
        return f"{self.amount_with_unit} {self.substance}"

    @property
    def amount(self) -> float:
        # return the amount as a float, in the base unit (kg for mass, L for volumes)
        return self.quantity.to_base_units().magnitude

    @property
    def amount_with_unit(self) -> str:
        if not self.quantity.units:
            return str(round(self.quantity))
        q = self.quantity.to_compact()
        # print(q)
        amount = q.magnitude
        amount = round(amount) if round(amount, 8) % 1.0 == 0 else amount
        return f"{amount}{q.units:~P}"

    def __repr__(self):
        return f"<Dose {self}>"

    def __add__(self, other: "Dose") -> "Dose":
        if self.quantity.units.dimensionality != other.quantity.units.dimensionality:
            # if quantity of either is 0, we skip it
            if self.quantity.magnitude == 0:
                return other
            if other.quantity.magnitude == 0:
                return self
            raise ValueError(
                f"Cannot add doses with different units: {self.quantity.units} and {other.quantity.units} (for {self} and {other})"
            )
        assert self.substance.lower() == other.substance.lower()
        return Dose(self.substance, self.quantity + other.quantity)

    def __truediv__(self, b):
        return Dose(self.substance, self.quantity / b)

    def __lt__(self, other):
        return self.quantity < other.quantity

    def __eq__(self, other):
        return (
            self.substance == other.substance
            and round((self.quantity - other.quantity).magnitude, 12) == 0
        )


def test_amount_with_unit():
    d = Dose("L", "100 mcg")
    assert d.amount_with_unit == "100mcg"


def test_amount_unitless():
    d = Dose("Candy", "10x")
    assert d.amount_with_unit == "10x"


def test_amount_iu():
    d = Dose("Vitamin D", "5000 IU")
    assert d.amount_with_unit == "5kIU"


def test_amount_cfu():
    d = Dose("CFU", "7B")
    assert d.amount_with_unit == "7B"
