#!/bin/env python3

import os
import re
import logging
import json
from typing import List, Dict
from pathlib import Path
from collections import defaultdict

from .event import Event
from .parse import parse, re_date
from .config import load_config


log = logging.getLogger(__name__)

re_evernote_author = re.compile(r'>author:(.+)$')
re_evernote_source = re.compile(r'>source:(.+)$')


base_dir = os.path.dirname(__file__)


def _load_standard_notes() -> List[str]:
    notes = []
    p = Path(os.path.dirname(base_dir) + "/data/private")
    for path in p.glob("Standard Notes Decrypted Backup*.txt"):
        print(f"Loading standardnotes from {path}")
        with open(path) as f:
            data = json.load(f)
            for entry in sorted(data["items"], key=lambda e: e["content"]["title"] if "title" in e["content"] else ""):
                if "title" in entry["content"] and "text" in entry["content"]:
                    title = entry["content"]["title"]
                    text = entry["content"]["text"]
                    if re_date.match(title):
                        # print(title)
                        # print(text)
                        notes.append(f"# {title}\n\n{text}")
                else:
                    log.debug("Unknown note type")
                    # print(entry["content"])
                    title = None

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
                print(f" - Skipping note without author or source")
                continue

            if source and "android" not in source[0]:
                print(f" - Source was something else than android: {source}")

        dates = re_date.findall(str(p))
        if dates:
            dateset.add(dates[0])

            # Remove metadata lines
            data = "\n".join(line for line in data.split("\n") if not (line.startswith(">") or line.startswith("---") or line.startswith("##")))

            notes.append(data)
    # pprint(sorted(dates))
    return notes


def load_events() -> List[Event]:
    events: List[Event] = []
    for note in _load_standard_notes():
        events += parse(note)
    for note in _load_evernote():
        events += parse(note)
    events = _extend_substance_abbrs(events)
    events = _tag_substances(events)
    return sorted(events)


def _load_categories() -> Dict[str, List[str]]:
    "Returns a dict {category: [substances...]}"
    config = load_config()
    categories = config.get('categories', {})
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
    return config.get('aliases', {})


substance_aliases = _load_substance_aliases()


def _tag_substances(events: List[Event]) -> List[Event]:
    for e in events:
        if e.substance and e.substance.lower() in substance_categories:
            cats = substance_categories[e.substance.lower()]
            e.data["tags"] = cats
    n_categorized = len([e for e in events if e.tags])
    print(f"Categorized {n_categorized} out {len(events)} of events ({round(n_categorized/len(events)*100, 1)}%)")
    return events


def _extend_substance_abbrs(events) -> List[Event]:
    for e in events:
        if e.substance and e.substance.lower() in substance_aliases:
            e.data["substance"] = substance_aliases[e.substance.lower()]
    return events


def test_load():
    load_events()
