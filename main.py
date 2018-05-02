import re
from typing import List, Dict, Any, Tuple
from copy import copy
from collections import namedtuple
from datetime import date, time, datetime
from pathlib import Path
import json


re_date = re.compile(r"[0-9]+-[0-9]+-[0-9]+")
re_time = re.compile(r"[~+]*[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(r"[~]?[?0-9\.]+(k|c|d|mc|m|u|n)?(l|g|IU|x)?")
re_extra= re.compile(r"\(.*\)")
re_roa = re.compile(r"(oral|buccal|subcut|smoked|vaporized|insuff)")

Event = namedtuple("Event", ["timestamp", "type", "data"])


def load_standard_notes():
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
                    print("Unknown note type")
                    # print(entry["content"])
                    title = None

    return notes


def parse_data(data: str) -> List[Dict[str, Any]]:
    datas = []
    if re_amount.match(data):
        for entry in (e.strip() for e in data.split("+") if e.strip()):
            data = {"raw": entry}

            m_amount = re_amount.match(entry)
            if m_amount:
                data["amount"] = m_amount[0]
                entry = entry.replace(data["amount"], "").strip()

            m_roa = re_roa.findall(entry)
            if m_roa:
                data["roa"] = m_roa[0]
                entry = entry.replace(data["roa"], "").strip()

            m_extra = re_extra.findall(entry)
            if m_extra:
                data["extra"] = m_extra[0].strip("()")
                entry = entry.replace("(" + data["extra"] + ")", "").strip()

            data["substance"] = entry
            datas.append(data)
    return datas


def parse_time(s: str) -> Tuple[time, List[str]]:
    tags = []
    if "+" in s:
        tags.append("time-tomorrow")
    if "~" in s:
        tags.append("time-approximate")
    s = s.strip("+~").strip("+").strip("~")
    t = datetime.strptime(s, "%H:%M").time()
    return t, tags


def parse(text: str) -> None:
    events = []  # type: List[Event]

    current_date = None
    for line in text.split("\n"):
        line = line.strip()
        if line:
            if line[0] == "#":
                try:
                    current_date = datetime.strptime(line[1:].strip().split(" - ")[0], "%Y-%m-%d")
                except Exception as e:
                    print(e)
            elif re_time.match(line):
                t, tags = parse_time(line.split("-")[0].strip())
                timestamp = datetime.combine(current_date, t)
                data = "-".join(line.split("-")[1:]).strip()
                if re_amount.match(data):
                    # Data entry
                    for entry in parse_data(data):
                        events.append(Event(timestamp, "data", entry))
                else:
                    # Journal entry
                    events.append(Event(timestamp, "journal", data))
            elif line:
                print(f"Couldn't identify line-type: \n> {line}")

    return events


def print_event(e: Dict[str, str]):
    d = e.data
    if e.type == "data":
        e_str = f"{d['amount'] if 'amount' in d else '?'} {d['substance']}"
    else:
        e_str = e.data
    print(f"{e.timestamp.isoformat()} | {e.type.ljust(7)} | " + e_str)


def print_events(events):
    for e in events:
        print(f"{e.timestamp.isoformat()} [{e.type}]   \t{e.data}")


def test_parse():
    test1 = """
    # 2018-04-14

    16:30 - Started working on qslang

    ~17:12 - Made progress

    18:12 - ~1dl Green tea + 5g Cocoa
    """

    parse(test1)


if __name__ == "__main__":
    notes = load_standard_notes()

    for note in notes:
        for e in parse(note):
            print_event(e)
