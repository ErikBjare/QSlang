#!/bin/env python3

import logging
import pint
from typing import Union


log = logging.getLogger(__name__)


ureg = pint.UnitRegistry()
ureg.define('micro- = 10**-6 = mc- = μ-')
ureg.define('micro- = 10**-6 = mc- = μ-')
Q_ = ureg.Quantity


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
        return self.substance == other.substance and round((self.quantity - other.quantity).magnitude, 18) == 0


def test_add_dose():
    assert Dose("caffeine", "100mg") + Dose("caffeine", "100mg")

    assert Dose("", "0g") + Dose("", "1g") == Dose("", "1.0g")
    assert Dose("", "1mg") + Dose("", "10mg") == Dose("", "11.0mg")
    assert Dose("", "500mcg") + Dose("", "1mg") == Dose("", "1.5mg")
    assert Dose("", "100mcg") + Dose("", "100ug") == Dose("", "200.0ug")
    assert Dose("", "100mcg") + Dose("", "100μg") == Dose("", "200.0ug")

    assert Dose("", "1ml") + Dose("", "2ml") == Dose("", "3.0ml")
    assert Dose("", "1dl") + Dose("", "4dl") == Dose("", "500.0ml")
    assert Dose("", "1.0dl") + Dose("", "0l") == Dose("", "100.0ml")

    assert Dose("", "33cl") + Dose("", "1l") == Dose("", "1.33l")


def test_dose_format():
    d = Dose("Caffeine", "0.1g")
    assert str(d) == "100mg Caffeine"

    d = Dose("Potent stuff", "100mcg")
    assert str(d) == "100mcg Potent stuff"
