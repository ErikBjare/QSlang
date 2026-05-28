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
    # A clear winner per unit: "blip" -> Alpha, "blop" -> Beta.
    # Plurals collapse to the same key, so a bare "blip" matches "blips".
    events = (
        [_dose("Alpha", "blips", "oral") for _ in range(10)]
        + [_dose("Beta", "blops", "buccal") for _ in range(10)]
        + [_dose(None, "blip"), _dose(None, "blop")]
    )
    _infer_implicit_substances(events)

    bare_blip = next(e for e in events if e.data["dose"]["unit"] == "blip")
    bare_blop = next(e for e in events if e.data["dose"]["unit"] == "blop")
    assert bare_blip.substance == "Alpha"
    assert bare_blop.substance == "Beta"
    # marked as inferred and the dominant ROA is filled in
    assert bare_blip.data.get("implicit_substance") is True
    assert bare_blip.roa == "oral"
    assert bare_blop.roa == "buccal"


def test_no_inference_without_clear_winner():
    # Two substances equally common for the same unit -> ambiguous, leave unknown
    events = (
        [_dose("Alpha", "blob") for _ in range(5)]
        + [_dose("Beta", "blob") for _ in range(5)]
        + [_dose(None, "blob")]
    )
    _infer_implicit_substances(events)
    bare = next(e for e in events if e.substance is None)
    assert bare.substance is None
    assert "implicit_substance" not in bare.data


def test_no_inference_below_min_observations():
    # Only one observation of the unit -> not enough evidence to infer
    events = [_dose("Rare", "zzz"), _dose(None, "zzz")]
    _infer_implicit_substances(events)
    bare = next(e for e in events if e.substance is None)
    assert bare.substance is None


def test_explicit_substance_not_overwritten():
    events = [_dose("Alpha", "blips") for _ in range(5)] + [_dose("Gamma", "blip")]
    _infer_implicit_substances(events)
    assert all(e.substance for e in events)
    # the explicit entry is left untouched
    gamma = next(e for e in events if e.substance == "Gamma")
    assert "implicit_substance" not in gamma.data
