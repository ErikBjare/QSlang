"""
Nicotine-vape events from an OpenElfbar app database.

OpenElfbar syncs ELFBAR vapes over BLE into SQLite. Devices like the ELFX Ultra
only expose hourly aggregates: each sync reports a rolling 3-day window
(``today``/``yesterday``/``two_days_ago`` × 24 hours, relative to the device
clock, which the app sets to phone local time). Hours no sync covered are
unknown.

Device hours become ``N puffs Nicotine vaped`` dose events at the start of
each hour. In hours the device covered, it replaces manually logged
``Nicotine vaped`` entries (other nicotine routes, like snus, are kept).

Configure in ``config.toml``::

    [data]
    openelfbar = "~/annex/Logs/OpenElfbar/openelfbar-latest.db"
    # openelfbar_timezone = "Europe/Stockholm"  # phone timezone (default)
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .event import Event

logger = logging.getLogger(__name__)

DAY_OFFSETS = {"today": 0, "yesterday": 1, "two_days_ago": 2}
DEFAULT_TIMEZONE = "Europe/Stockholm"
SUBSTANCE = "Nicotine"
ROA = "vaped"
# every spelling the parser accepts for vaping (see `roa` in parsimonious.py)
VAPING_ROAS = {"vap", "vaped", "vaporized"}


@dataclass
class DeviceHour:
    device: str
    hour: datetime  # naive local, start of hour
    puffs: float
    duration: float | None


def load_device_hours(path: Path, tz: str = DEFAULT_TIMEZONE) -> list[DeviceHour]:
    """Anchor hourly aggregates to local hours, keeping the latest sync per hour.

    The hour a sync happened in was still in progress, so it (and later hours)
    are skipped.
    """
    zone = ZoneInfo(tz)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            """
            SELECT h.device_identifier_hex, h.metric, h.day_label, h.hour_index,
                   h.value, s.started_at
            FROM hourly_aggregates h
            JOIN sync_runs s USING (sync_run_id)
            WHERE s.status = 'completed'
              AND h.metric IN ('puff_count', 'duration_summary')
            """
        ).fetchall()

    # (device, hour) -> (synced_utc, {metric: value}); latest sync wins
    latest: dict[tuple[str, datetime], tuple[datetime, dict[str, float]]] = {}
    for device, metric, day_label, hour_index, value, started_at in rows:
        if day_label not in DAY_OFFSETS or not 0 <= hour_index <= 23:
            continue
        synced = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        synced = synced.astimezone(timezone.utc)
        synced_local = synced.astimezone(zone).replace(tzinfo=None)
        day = synced_local.replace(hour=0, minute=0, second=0, microsecond=0)
        hour = (
            day - timedelta(days=DAY_OFFSETS[day_label]) + timedelta(hours=hour_index)
        )
        if hour >= synced_local.replace(minute=0, second=0, microsecond=0):
            continue
        key = (device, hour)
        prev = latest.get(key)
        if prev is None or synced > prev[0]:
            latest[key] = (synced, {metric: value})
        elif synced == prev[0]:
            prev[1][metric] = value

    return sorted(
        (
            DeviceHour(
                device=device,
                hour=hour,
                puffs=values.get("puff_count", 0.0),
                duration=values.get("duration_summary"),
            )
            for (device, hour), (_, values) in latest.items()
        ),
        key=lambda h: (h.hour, h.device),
    )


def _is_manual_vaped_nicotine(e: Event, substance: str) -> bool:
    return (
        e.type == "dose"
        and (e.substance or "").lower() == substance.lower()
        and ((e.data.get("dose") or {}).get("roa") or "").lower() in VAPING_ROAS
        and e.data.get("source") != "openelfbar"
        # doses logged for someone else ({name} prefix) aren't the device owner's
        and "patient" not in e.data
    )


def merge_device_events(
    events: list[Event], hours: list[DeviceHour], substance: str = SUBSTANCE
) -> list[Event]:
    """Replace manual vaped-nicotine entries in device-covered hours with device events.

    ``substance`` is the name nicotine has after alias resolution, so device
    events and the entries they replace share it.
    """
    covered = {h.hour for h in hours}

    def in_covered_hour(e: Event) -> bool:
        return e.timestamp.replace(minute=0, second=0, microsecond=0) in covered

    kept = [
        e
        for e in events
        if not (_is_manual_vaped_nicotine(e, substance) and in_covered_hour(e))
    ]
    n_replaced = len(events) - len(kept)

    device_events = []
    for h in hours:
        if h.puffs <= 0:
            continue
        data: dict[str, object] = {
            "substance": substance,
            "dose": {"amount": h.puffs, "unit": "puffs", "roa": ROA},
            "source": "openelfbar",
            "device": h.device,
        }
        if h.duration is not None:
            data["duration"] = h.duration
        device_events.append(Event(timestamp=h.hour, type="dose", data=data))

    logger.info(
        f"OpenElfbar: {len(device_events)} hourly events over {len(covered)} covered hours, "
        f"replaced {n_replaced} manual vaped '{substance}' entries"
    )
    return kept + device_events
