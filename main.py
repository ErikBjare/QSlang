import re
from typing import List, Dict, Any
from copy import copy
from collections import namedtuple
from datetime import date, time, datetime


re_time = re.compile(r"[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(r"~?[0-9\.]+(k|d|m|mcg|u|n)?(l|g|IU)?")

Event = namedtuple("Event", ["timestamp", "type", "data"])


def parse_data(data: str) -> List[Dict[str, Any]]:
    datas = []
    if re_amount.match(data):
        for entry in (e.strip() for e in data.split("+")):
            amount = re_amount.match(entry)[0]
            # print(m)
            datas.append({"raw": entry, "amount": amount})
            # print(f"  - {entry}")
    return datas


def parse(text: str) -> None:
    events = []  # type: List[Event]

    current_date = None
    for line in text.split("\n"):
        line = line.strip()
        if line:
            if line[0] == "#":
                current_date = datetime.strptime(line[1:].strip(), "%Y-%m-%d")
            elif re_time.match(line):
                t = datetime.strptime(line.split("-")[0].strip(), "%H:%M").time()
                timestamp = copy(current_date).replace(hour=t.hour, minute=t.minute, second=t.second)
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

    for e in events:
        print(f"{e.timestamp.isoformat()} [{e.type}]   \t{e.data}")


if __name__ == "__main__":
    test1 = """
    # 2018-04-14

    16:30 - Started working on qslang

    18:12 - ~1dl Green tea + 5g Cocoa
    """

    parse(test1)
