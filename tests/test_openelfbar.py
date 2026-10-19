import sqlite3
from datetime import datetime
from pathlib import Path

from qslang.event import Event
from qslang.load import _infer_implicit_substances
from qslang.openelfbar import load_device_hours, merge_device_events


def _write_db(path: Path, syncs: dict[str, dict[tuple[str, int], float]]) -> None:
    """syncs: started_at (UTC ISO) -> {(day_label, hour): puffs}"""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sync_runs (sync_run_id TEXT, started_at TEXT, status TEXT);
        CREATE TABLE hourly_aggregates (device_identifier_hex TEXT, sync_run_id TEXT,
            metric TEXT, day_label TEXT, hour_index INTEGER, value REAL);
        """
    )
    for i, (started_at, values) in enumerate(syncs.items()):
        conn.execute(
            "INSERT INTO sync_runs VALUES (?, ?, 'completed')", (f"s{i}", started_at)
        )
        for label in ["two_days_ago", "yesterday", "today"]:
            for hour in range(24):
                puffs = values.get((label, hour), 0)
                for metric, value in [
                    ("puff_count", puffs),
                    ("duration_summary", puffs * 1.5),
                ]:
                    conn.execute(
                        "INSERT INTO hourly_aggregates VALUES ('dev', ?, ?, ?, ?, ?)",
                        (f"s{i}", metric, label, hour, value),
                    )
    conn.commit()
    conn.close()


def _dose(ts, substance, unit="puffs", roa=None, amount=2.0):
    dose = {"amount": amount, "unit": unit}
    if roa:
        dose["roa"] = roa
    return Event(timestamp=ts, type="dose", data={"substance": substance, "dose": dose})


def test_load_device_hours(tmp_path: Path):
    path = tmp_path / "openelfbar.db"
    _write_db(
        path,
        {
            # 2026-03-03 12:30 CET
            "2026-03-03T11:30:00.000Z": {("yesterday", 18): 37, ("today", 12): 9},
            # later sync re-reports 03-02 18:00 with the same count
            "2026-03-04T08:30:00.000Z": {("two_days_ago", 18): 37, ("today", 8): 4},
        },
    )
    hours = {h.hour: h for h in load_device_hours(path)}
    assert hours[datetime(2026, 3, 2, 18)].puffs == 37
    assert hours[datetime(2026, 3, 2, 18)].duration == 37 * 1.5
    # 12:00 was in progress during the first sync; the second sync (03-04)
    # covers 03-03 fully as "yesterday", where 12:00 has no puffs
    assert hours[datetime(2026, 3, 3, 12)].puffs == 0
    # the second sync's own hour (09:00 local) and later are not covered
    assert max(hours) == datetime(2026, 3, 4, 8)
    assert hours[datetime(2026, 3, 4, 8)].puffs == 4
    # 72h window of the first sync starts at 03-01 00:00
    assert min(hours) == datetime(2026, 3, 1, 0)


def test_merge_replaces_manual_vaped_nicotine_in_covered_hours(tmp_path: Path):
    path = tmp_path / "openelfbar.db"
    _write_db(path, {"2026-03-03T11:30:00.000Z": {("yesterday", 18): 37}})
    hours = load_device_hours(path)

    manual_covered = _dose(
        datetime(2026, 3, 2, 18, 40), "Nicotine", roa="vaped", amount=6
    )
    manual_uncovered = _dose(
        datetime(2026, 3, 5, 10, 0), "Nicotine", roa="vaped", amount=3
    )
    snus = _dose(
        datetime(2026, 3, 2, 18, 10), "Nicotine", unit="mg", roa="buccal", amount=8
    )
    cannabis = _dose(datetime(2026, 3, 2, 18, 20), "Cannabis oil", roa="vaped")

    result = merge_device_events(
        [manual_covered, manual_uncovered, snus, cannabis], hours
    )

    assert manual_covered not in result
    assert manual_uncovered in result
    assert snus in result
    assert cannabis in result
    device = [e for e in result if e.data.get("source") == "openelfbar"]
    # only hours with puffs become events
    assert len(device) == 1
    e = device[0]
    assert e.timestamp == datetime(2026, 3, 2, 18)
    assert e.substance == "Nicotine"
    assert e.roa == "vaped"
    assert e.data["dose"] == {"amount": 37, "unit": "puffs", "roa": "vaped"}


def test_device_events_dont_sway_bare_puff_inference(tmp_path: Path):
    # bare "puff" → Cannabis oil must still hold even if device events would
    # outnumber cannabis entries; that's why merging happens after inference
    path = tmp_path / "openelfbar.db"
    _write_db(
        path, {"2026-03-03T11:30:00.000Z": {("yesterday", h): 10 for h in range(24)}}
    )
    ts = datetime(2026, 2, 1, 12)
    events = [_dose(ts, "Cannabis oil", roa="vaped") for _ in range(5)] + [
        _dose(ts, None)
    ]
    events = _infer_implicit_substances(events)
    events = merge_device_events(events, load_device_hours(path))
    bare = [e for e in events if e.data.get("implicit_substance")]
    assert len(bare) == 1 and bare[0].substance == "Cannabis oil"
