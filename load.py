#!/bin/env python3

import re
import logging
import json
from typing import List
from pathlib import Path

from dose import Dose
from event import Event
from parse import parse


log = logging.getLogger(__name__)

re_date = re.compile(r"[0-9]+-[0-9]+-[0-9]+")
re_time = re.compile(r"[~+]*[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(r"[~]?[?0-9\.]+(k|c|d|mc|m|u|n)?(l|L|g|IU|x)?")
re_extra = re.compile(r"\(.*\)")
re_roa = re.compile(r"(orall?y?|buccal|subcut|smoked|vaporized|insuffl?a?t?e?d?|chewed|subli?n?g?u?a?l?|intranasal|spliff)")

re_evernote_author = re.compile(r'>author:(.+)$')
re_evernote_source = re.compile(r'>source:(.+)$')


def _load_standard_notes() -> List[str]:
    notes = []
    p = Path("./data/private")
    for path in p.glob("*Archive*.txt"):
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
            notes.append(data)
    # pprint(sorted(dates))
    return notes


def load_events():
    notes = []
    notes += _load_standard_notes()
    notes += _load_evernote()

    events = sorted([e for note in notes for e in parse(note)])
    events = _extend_substance_abbrs(events)
    events = _annotate_doses(events)
    events = _tag_substances(events)
    return events


def _load_substance_categories():
    # TODO: Support more than one category per substance
    p = Path("data/substance_categories.csv")
    if p.is_file():
        with p.open() as f:
            lines = f.readlines()
            return dict((line.split(",")[0].lower(), [line.split(",")[1].strip()]) for line in lines)
    else:
        return {}


substance_categories = _load_substance_categories()


def _load_substance_map():
    p = Path("data/substance_map.csv")
    if p.is_file():
        with p.open() as f:
            lines = f.readlines()
            return dict((line.split(",")[0].lower(), line.split(",")[1].strip()) for line in lines)
    else:
        return {}


substance_map = _load_substance_map()


def _tag_substances(events: List[Event]) -> List[Event]:
    for e in events:
        if e.substance.lower() in substance_categories:
            cats = substance_categories[e.substance.lower()]
            e.data["tags"] = cats
    n_categorized = len([e for e in events if e.tags])
    print(f"Categorized {n_categorized} out {len(events)} of events ({round(n_categorized/len(events)*100, 1)}%)")
    return events


def _annotate_doses(events: List[Event]) -> List[Event]:
    for e in events:
        try:
            e.data["dose"] = Dose(e.substance, e.data["amount"])
        except Exception as exc:
            log.warning(f"Unable to annotate dose: {exc}")
            events.remove(e)
    return events


def _extend_substance_abbrs(events) -> List[Event]:
    for e in events:
        if e.substance.lower() in substance_map:
            e.data["substance"] = substance_map[e.substance.lower()]
    return events


def test_load():
    load_events()
