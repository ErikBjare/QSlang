from qslang.event import Event

_alcohol_conc_assumptions = {
    "gin": 0.4,
    "vodka": 0.4,
    "whiskey": 0.4,
    "beer": 0.05,
    "wine": 0.12,
}


def _alcohol_preprocess(events: list[Event]) -> list[Event]:
    for e in events:
        if not e.substance or not e.dose:
            continue
        if "Alcohol" in e.tags:
            conc_str = e.data.get("concentration", None)
            if conc_str:
                if "?" not in conc_str:
                    conc = 0.01 * float(conc_str.strip("%"))
            elif e.substance.lower() in _alcohol_conc_assumptions:
                conc = _alcohol_conc_assumptions[e.substance.lower()]
            else:
                print(f"Concentration unknown for event: {e}")
                continue
            e.data["substance"] = "Alcohol"
            e.data["amount"] = str(e.dose.quantity * conc)
    return events
