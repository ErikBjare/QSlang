import re
from datetime import datetime


re_time = re.compile(r"[0-9]{1,2}:[0-9]{1,2}")
re_amount = re.compile(r"~?[0-9\.]+(k|d|m|mcg|u|n)?(l|g|IU)?")


def parse(text: str):
    current_date = None
    for line in text.split("\n"):
        line = line.strip()
        if line:
            if line[0] == "#":
                current_date = datetime.strptime(line[1:].strip(), "%Y-%m-%d")
                print(current_date)
            elif re_time.match(line):
                time = line.split("-")[0].strip()
                data = "-".join(line.split("-")[1:]).strip()
                if re_amount.match(data):
                    # Data entry
                    print(f"[data@{time}]   \t{data}")
                    for entry in (e.strip() for e in data.split("+")):
                        # print(f"  - {entry}")
                        pass
                else:
                    # Journal entry
                    print(f"[journal@{time}]\t{data}")

            elif line:
                print(f"Couldn't identify line-type: \n> {line}")


test1 = """
# 2018-04-14

16:30 - Started working on qslang

18:12 - ~1dl Green tea + 5g Cocoa
"""

parse(test1)
