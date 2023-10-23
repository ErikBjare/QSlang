from datetime import datetime

import pytest
from qslang.parsimonious import (
    Event,
    ParseError,
    _parse_continue_on_err,
    parse,
    parse_entries,
    parse_to_node,
)

# Tests parsing with visitor


def test_parse_notes():
    parsed = parse("09:00 - One journal entry\n\n10:00 - Another journal entry")
    assert len(parsed) == 2
    assert parsed[0].type == "journal"
    assert parsed[0].data == {"note": "One journal entry"}
    assert parsed[1].type == "journal"
    assert parsed[1].data == {"note": "Another journal entry"}


def test_parse_multidose():
    s = "09:00 - 100mg Caffeine + 200mg L-Theanine"
    assert parse(s)


def test_parse_multivit():
    s = "09:00 - 1x Multivitamin (100mg Magnesium (from Citrate) + 10mg Zinc (from Picolinate))"
    assert parse(s)


def test_parse_nested():
    s = "09:30 - 1x Something (2x Something-Else (10mg Substance-A + 10mg Substance-B) + 10mg Substance-C) oral"
    assert parse(s)


def test_parse_simple():
    print("Simple example, no day header")
    s = """09:30 - 1 cup Coffee oral"""
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(1900, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"
    assert parsed[0].data["dose"] == {"amount": 1, "unit": "cup", "roa": "oral"}


def test_parse_header():
    print("\nHeader example")
    s = """
    # 2020-01-01

    09:30 - 1 cup Coffee
    """
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(2020, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"


def test_parse_subdoses():
    print("\nSubdoses example")
    s = """
    09:30 - 1 cup Coffee (100mg Caffeine + 50mg L-Theanine)
    """
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(1900, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"
    assert parsed[0].data.get("subdoses", []) == [
        {"substance": "Caffeine", "dose": {"amount": 100, "unit": "mg"}},
        {"substance": "L-Theanine", "dose": {"amount": 50, "unit": "mg"}},
    ]


def test_parse_complex():
    print("\nComplex example")
    # Complex example
    s = """
    09:30 - 1 cup Coffee (strong, milk, ~100mg Caffeine + 50mg L-Theanine + 1mg LOL)
    """
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].timestamp == datetime(1900, 1, 1, 9, 30)
    assert parsed[0].data["substance"] == "Coffee"
    assert parsed[0].data.get("notes", []) == [
        {"note": "strong"},
        {"note": "milk"},
    ]
    assert parsed[0].data.get("subdoses", []) == [
        {
            "substance": "Caffeine",
            "dose": {"amount": 100, "unit": "mg", "approx": True},
        },
        {"substance": "L-Theanine", "dose": {"amount": 50, "unit": "mg"}},
        {"substance": "LOL", "dose": {"amount": 1, "unit": "mg"}},
    ]


def test_parse_event():
    s = "# 2020-01-01\n09:30 - 1x Something (50mg Caffeine + 100mg L-Theanine)"
    print(parse(s))


def test_parse_alcohol():
    s = "# 2020-01-01\n18:30 - 4cl Gin (Tanqueray, 47%)"
    parsed = parse(s)
    assert len(parsed) == 1
    assert parsed[0].data["notes"] == [{"note": "Tanqueray"}, {"note": "47%"}]


def test_parse_patient():
    parsed = parse("# 2020-01-01\n09:30 - 100mcg LSD\n09:30 - {F} 100mcg LSD")
    assert "patient" not in parsed[0].data
    assert parsed[1].data["patient"] == "F"


def test_parse_ratio():
    s = """
    19:00 - 1g Some kind of extract (10:1)
    """
    entries = parse(s)
    assert len(entries) == 1
    assert entries[0].data["substance"] == "Some kind of extract"
    assert entries[0].data["notes"][0] == {"note": "10:1"}


def test_parse_umlaut():
    # Umlaut in substance name
    s = """20:00 - 4cl Jägermeister"""
    entries = parse(s)
    assert len(entries) == 1
    assert entries[0].data["substance"] == "Jägermeister"


def test_parse_half_serving():
    # Half serving
    s = """20:00 - 1/2 serving Elevate Pre-workout Formula (5g Vitargo + 1.6g Beta-Alanine + 1.5g Citrulline Malate + 1.5g Arginine Alpha Ketoglutarate + 1.25g Trimethylglycine + 1g Taurine + 250mg Glucuronolactone + 200mg L-Tyrosine + 150mg Grape Seed Extract + 125mg Caffeine + 90mg ACTINOS + 12.5mg Vitamin B6 + 2.5mg Bioperine) + 5g Creatine"""
    entries = parse(s)
    assert len(entries) == 2
    assert entries[0].data["substance"] == "Elevate Pre-workout Formula"
    assert entries[0].data["dose"]["unit"] == "serving"
    # assert entries[0].data["dose"]["amount"] == 0.5


def test_parse_dayheader_title():
    # Half serving
    s = """# 2022-08-03 - Just some example title"""
    parse(s)


def test_parse_probiotic_cfu():
    # Half serving
    s = """10:00 - 1x Probiotic (30B CFU)"""
    entries = parse(s)
    assert len(entries) == 1
    assert entries[0].data["substance"] == "Probiotic"
    assert entries[0].data["dose"]["amount"] == 1
    assert entries[0].data["dose"]["unit"] == "x"
    assert entries[0].data["subdoses"] == [
        {"substance": "CFU", "dose": {"amount": 30, "unit": "B"}}
    ]
    # assert entries[0].data["notes"] == [{"note": "30B CFU"}]


# Parse to node tests


@pytest.mark.run(order=0)
def test_parse_node_dayheader():
    assert parse_to_node("# 2020-1-1", rule="day_header")
    assert parse_to_node("# 2020-01-01", rule="day_header")


@pytest.mark.run(order=0)
def test_parse_node_entry():
    assert parse_to_node("10:00 - 100mg Caffeine", rule="entry")
    assert parse_to_node("10:00 - 1 cup Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_full():
    assert parse_to_node("10:00 - 100mg Caffeine", rule="entries")
    assert parse_to_node("10:00 - 1 cup Coffee\n11:00 - 50mg Caffeine", rule="entries")


@pytest.mark.run(order=0)
def test_parse_node_unknown():
    assert parse_to_node("10:00 - ?dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_approx_time():
    assert parse_to_node("~10:00 - 1dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_approx_amount():
    assert parse_to_node("10:00 - ~1dl Coffee", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_next_day():
    assert parse_to_node("+01:00 - 0.5mg Melatonin", rule="entry")


@pytest.mark.run(order=0)
def test_parse_node_extra():
    assert parse_to_node("(100mg Caffeine + 200mg L-Theanine)", rule="extra")


# Test parse entries


@pytest.mark.run(order=0)
def test_parse_entries():
    entries = list(parse_entries("10:00 - 100mg Caffeine"))
    assert len(entries) == 1

    entries = list(parse_entries("10:00 - 1 cup Coffee\n\n11:00 - 50mg Caffeine"))
    assert len(entries) == 2


def test_parse_decimal():
    s = """
    19:00 - 3.5g Creatine monohydrate
    """
    assert list(parse_entries(s))


def test_parse_percent():
    s = """
    19:00 - 4cl Drink (8%)
    """
    assert list(parse_entries(s))


def test_parse_entries_notes():
    s = """
    09:30 - Just a plain note

    09:40 - 1x Something (with a note)
    """
    assert list(parse_entries(s))


def test_parse_entries_day_example():
    s = """
    # 2020-01-01

    09:30 - 1 cup Coffee (100mg Caffeine + 50mg L-Theanine)

    21:30 - 0.5mg Melatonin subl
    """
    assert list(parse_entries(s))


def test_parse_next_day():
    s = """
    # 2017-06-08

    10:00 - 100mg Caffeine

    +00:30 - 0.5mg Melatonin subl
    """
    entries = parse(s)
    print(entries)
    assert len(entries) == 2
    assert entries[0].timestamp == datetime(2017, 6, 8, 10, 0)
    assert entries[1].timestamp == datetime(2017, 6, 9, 0, 30)


def test_parse_continue_on_err():
    s = """
    # 2020-01-01

    08:00 - 1x This will lead to an error ((+)

    09:00 - But this should still parse to a note.
    """
    entries = _parse_continue_on_err(s)
    assert len(entries) == 2

    # first entry is a parse error
    assert isinstance(entries[0], ParseError)

    # ensure that the day header is being tracked
    assert isinstance(entries[1], Event)
    assert entries[1].timestamp == datetime(2020, 1, 1, 9, 0)
