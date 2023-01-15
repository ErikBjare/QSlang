#!/bin/env python3

import os
import re
import logging
import json
from typing import List, Dict, Optional, Union, Literal
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from .event import Event
from .parsimonious import parse_defer_errors
from .config import load_config
from .filter import filter_events
from .preprocess import _alcohol_preprocess


logger = logging.getLogger(__name__)

re_date = re.compile(r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}")
re_evernote_author = re.compile(r">author:(.+)$")
re_evernote_source = re.compile(r">source:(.+)$")


base_dir = os.path.dirname(__file__)


def load_events(
    start: datetime = None,
    end: datetime = None,
    substances: list[str] = [],
    sources: None | (
        list[Literal["standardnotes"] | Literal["evernote"] | Literal["example"]]
    ) = None,
) -> list[Event]:
    """
    Load events from various sources.

    Sources can be:
    - standardnotes
    - evernote
    - example

    If set to None, all sources will be attempted.
    """
    events: list[Event] = []

    # NOTE: Many notes are duplicated (due to conflicts),
    # so we will end up with duplcate events that we have to deal with.

    if sources is None or "standardnotes" in sources:
        logger.info("Loading standardnotes...")
        new_events = notes_to_events(_load_standardnotes_export())
        logger.info(f"Loaded {len(new_events)} from standardnotes")
        events += new_events

    if sources is None or "evernote" in sources:
        logger.info("Loading evernote...")
        new_events = notes_to_events(_load_evernotes())
        logger.info(f"Loaded {len(new_events)} from evernote")
        events += new_events

    if not events:
        logger.warning("No events found, falling back to example data")
    if not events or (sources and "example" in sources):
        new_events = notes_to_events(_load_example_notes())
        logger.info(f"Loaded {len(new_events)} from example data")
        events += new_events

    events = _extend_substance_abbrs(events)
    events = _tag_substances(events)
    events = sorted(events)
    events = filter_events(events, start, end, substances)
    events = _alcohol_preprocess(events)

    # sanity checks
    illegal_chars = ["(", ")", "/"]
    for e in events:
        for char in illegal_chars:
            if e.substance and char in e.substance:
                logger.warning(
                    f"Substance '{e.substance}' contained illegal char '{char}' (entry time: {e.timestamp})"
                )

    return events


def notes_to_events(notes: list[str]) -> list[Event]:
    """
    Turns raw notes into events

    - Collects errors
    - Deals with duplicates
    """
    logger.debug("Converting to events...")
    events = []
    errors = []
    for note in notes:
        note_events, note_errors = parse_defer_errors(note)
        events += note_events
        errors += note_errors
    if errors:
        total = len(events) + len(errors)
        logger.warning(
            f"Found {len(errors)} ({len(errors) / total * 100:.2f}%) errors when parsing {total} notes"
        )
        # logger.warning("First 3 errors")
        # for e in errors[:3]:
        #     logger.exception(e)

    # remove duplicate events
    events_pre = len(events)
    events = list(set(events))
    if len(events) != events_pre:
        logger.warning("Removed duplicate events: %d -> %d", events_pre, len(events))

    return events


def _get_export_file() -> Path | None:
    config = load_config()
    p = config.get("data", {}).get("standardnotes_export", None)
    if p is None:
        return None
    return Path(p)


def _load_standardnotes_export() -> list[str]:
    # NOTE: Used to be deprecated, but not any longer as standardnotes-fs isn't working as well as it used to (after the standardnotes 004 upgrade)
    path = _get_export_file()
    if path is None:
        logger.warning("no standardnotes export in config")
        return []

    logger.info(f"Loading standardnotes from {path}")
    notes = []
    with open(path) as f:
        data = json.load(f)
        for entry in sorted(
            data["items"],
            key=lambda e: e["content"]["title"] if "title" in e["content"] else "",
        ):
            if "title" in entry["content"] and "text" in entry["content"]:
                title = entry["content"]["title"]
                text = entry["content"]["text"]
                if re_date.match(title):
                    # print(title)
                    # print(text)
                    notes.append(f"# {title}\n\n{text}")
            else:
                logger.debug("Unknown note type")
                # print(entry["content"])
                title = None

    assert notes, "no notes were read, is the file available and decrypted?"
    return notes


def _load_dir_notes(path: Path) -> list[str]:
    """
    This used to be called _load_standardnotes_fs,
    as it was used when standardnotes-fs was still functional.

    However, it was repurposed as it generalizes well.
    """
    notes = []
    for p in path.glob("*.md"):
        title = p.name.split(".")[0]
        if re_date.match(title):
            with open(p) as f:
                text = f.read()
                # print(title)
                # print(text)
                if text.startswith("#"):
                    notes.append(text)
                else:
                    notes.append(f"# {title}\n\n{text}")
        else:
            logger.debug("Unknown note type")
            # print(entry["content"])

    return notes


def _load_example_notes() -> list[str]:
    notes = _load_dir_notes(Path(base_dir) / ".." / "data" / "test" / "notes")
    assert notes
    return notes


def _load_evernotes() -> list[str]:
    notes = []
    # TODO: read from config
    d = Path("./data/private/Evernote")
    dateset = set()
    for p in d.glob("*.md"):
        data = p.read_text()

        # A bad idea for filtering away notes that were not mine, but might still be useful for tagging with metadata
        if False:
            authors = re_evernote_author.findall(data)
            if authors and "erik" not in authors[0]:
                print(f" - Skipped note from other author: {authors}")
                continue

            source = re_evernote_source.findall(data)
            if not authors and not source:
                print(" - Skipping note without author or source")
                continue

            if source and "android" not in source[0]:
                print(f" - Source was something else than android: {source}")

        dates = re_date.findall(str(p))
        if dates:
            dateset.add(dates[0])

            # Remove metadata lines
            data = "\n".join(
                line
                for line in data.split("\n")
                if not (
                    line.startswith(">")
                    or line.startswith("---")
                    or line.startswith("##")
                )
            )

            notes.append(data)
    # pprint(sorted(dates))
    return notes


def _load_categories() -> dict[str, list[str]]:
    "Returns a dict {category: [substances...]}"
    config = load_config()
    categories = config.get("categories", {})
    for cat in categories:
        categories[cat] = [sub.lower() for sub in categories[cat]]
    return categories


def _substance2categories():
    "returns the inverted dict of _load_categories"
    sub2cat = defaultdict(set)
    for cat, subs in _load_categories().items():
        for sub in subs:
            sub2cat[sub].add(cat)
    return sub2cat


def _load_substance_aliases() -> dict[str, list[str]]:
    """Loads a mapping from target values to a list of substance aliases that should be renamed to target"""
    config = load_config()
    aliases = config.get("aliases", {})
    return aliases


def _tag_substances(events: list[Event]) -> list[Event]:
    substance_categories = _substance2categories()
    for e in events:
        if e.substance and e.substance.lower() in substance_categories:
            cats = substance_categories[e.substance.lower()]
            e.data["tags"] = cats
    n_doses = len([e for e in events if e.substance])
    n_categorized = len([e for e in events if e.tags])
    frac_categorized = n_categorized / n_doses if events else 0.0
    logger.info(
        f"Categorized {n_categorized} out of {n_doses} doses ({round(frac_categorized*100, 1)}%)"
    )
    return events


def _extend_substance_abbrs(events) -> list[Event]:
    substance_aliases = _load_substance_aliases()
    # invert mapping and lowercase for easier lookup
    substance_aliases_inv = {
        v.lower(): k for k, vs in substance_aliases.items() for v in vs
    }
    for e in events:
        if e.substance and e.substance.lower() in substance_aliases_inv:
            e.data["substance"] = substance_aliases_inv[e.substance.lower()]
    return events


def test_load_events():
    events = load_events(sources=["example"])
    print(f"Loaded {len(events)} events")
    assert events
