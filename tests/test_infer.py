from datetime import datetime

from qslang.event import Event
from qslang.load import _infer_implicit_substances


def _dose(substance, unit, roa=None, amount=1.0):
    dose = {"amount": amount, "unit": unit}
    if roa:
        dose["roa"] = roa
    return Event(
        timestamp=datetime(2020, 1, 1, 12, 0),
        type="dose",
        data={"substance": substance, "dose": dose},
    )


def test_infer_substance_from_unit():
    # A clear winner per unit: "serving(s)" -> Alpha, "cup(s)" -> Beta.
    # Known plurals collapse to the singular, so a bare "serving" matches "servings".
    events = (
        [_dose("Alpha", "servings", "oral") for _ in range(10)]
        + [_dose("Beta", "cups", "buccal") for _ in range(10)]
        + [_dose(None, "serving"), _dose(None, "cup")]
    )
    result = _infer_implicit_substances(events)

    bare_serving = next(e for e in result if e.data["dose"]["unit"] == "serving")
    bare_cup = next(e for e in result if e.data["dose"]["unit"] == "cup")
    assert bare_serving.substance == "Alpha"
    assert bare_cup.substance == "Beta"
    # marked as inferred and the dominant ROA is filled in
    assert bare_serving.data.get("implicit_substance") is True
    assert bare_serving.roa == "oral"
    assert bare_cup.roa == "buccal"


def test_drop_when_no_clear_winner():
    # Two substances equally common for the same unit -> ambiguous, so the
    # substance-less entry is dropped rather than kept with substance=None.
    events = (
        [_dose("Alpha", "blob") for _ in range(5)]
        + [_dose("Beta", "blob") for _ in range(5)]
        + [_dose(None, "blob")]
    )
    result = _infer_implicit_substances(events)
    assert len(result) == 10
    assert all(e.substance for e in result)


def test_drop_below_min_observations():
    # Only one observation of the unit -> not enough evidence; entry dropped
    events = [_dose("Rare", "zzz"), _dose(None, "zzz")]
    result = _infer_implicit_substances(events)
    assert len(result) == 1
    assert result[0].substance == "Rare"


def test_explicit_substance_not_overwritten():
    events = [_dose("Alpha", "servings") for _ in range(5)] + [_dose("Gamma", "serving")]
    result = _infer_implicit_substances(events)
    assert len(result) == 6
    assert all(e.substance for e in result)
    # the explicit entry is left untouched
    gamma = next(e for e in result if e.substance == "Gamma")
    assert "implicit_substance" not in gamma.data
