#!/bin/env python3

import os
import re
import logging
import json
from typing import List, Dict, Optional
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from .event import Event
from .parse import re_date
from .parsimonious import parse
from .config import load_config
from .filter import filter_events
from .preprocess import _alcohol_preprocess


logger = logging.getLogger(__name__)

re_evernote_author = re.compile(r">author:(.+)$")
re_evernote_source = re.compile(r">source:(.+)$")


base_dir = os.path.dirname(__file__)


def load_events(
    start: datetime = None, end: datetime = None, substances: List[str] = []
) -> List[Event]:
    events: List[Event] = []

    # NOTE: Many notes are duplicated (due to conflicts),
    # so we will end up with duplcate events that we have to deal with.
    for note in _load_standardnotes_export():
        events += parse(note, continue_on_err=True)

    # remove duplicate events
    events_pre = len(events)
    events = list(set(events))
    logger.warning("Removed duplicate events: %d -> %d", events_pre, len(events))

    for note in _load_evernote():
        events += parse(note, continue_on_err=True)

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


def _get_export_file() -> Optional[Path]:
    config = load_config()
    p = config.get("data", {}).get("standardnotes_export", None)
    if p is None:
        return None
    return Path(p)


def _load_standardnotes_export() -> List[str]:
    # NOTE: Used to be deprecated, but not any longer as standardnotes-fs isn't working as well as it used to (after the standardnotes 004 upgrade)
    path = _get_export_file()
    if path is None:
        logger.warning("no standardnotes export in config")
        return []

    print(f"Loading standardnotes from {path}")
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


def _load_standardnotes_fs() -> List[str]:
    notes = []
    p = Path("/home/erb/notes-git/notes")
    for path in p.glob("*.md"):
        title = path.name.split(".")[0]
        if re_date.match(title):
            with open(path, "r") as f:
                text = f.read()
                # print(title)
                # print(text)
                notes.append(f"# {title}\n\n{text}")
        else:
            logger.debug("Unknown note type")
            # print(entry["content"])

    assert notes
    return notes


def _load_evernote() -> List[str]:
    notes = []
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


def _load_categories() -> Dict[str, List[str]]:
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


substance_categories = _substance2categories()


def _load_substance_aliases():
    config = load_config()
    return config.get("aliases", {})


substance_aliases = _load_substance_aliases()


def _tag_substances(events: List[Event]) -> List[Event]:
    for e in events:
        if e.substance and e.substance.lower() in substance_categories:
            cats = substance_categories[e.substance.lower()]
            e.data["tags"] = cats
    n_categorized = len([e for e in events if e.tags])
    logger.info(
        f"Categorized {n_categorized} out of {len(events)} events ({round(n_categorized/len(events)*100, 1)}%)"
    )
    return events


def _extend_substance_abbrs(events) -> List[Event]:
    for e in events:
        if e.substance and e.substance.lower() in substance_aliases:
            e.data["substance"] = substance_aliases[e.substance.lower()]
    return events


def test_load_events():
    events = load_events()
    assert events
    print(f"Loaded {len(events)} events")
