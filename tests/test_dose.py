from qslang.dose import Dose


def test_add_dose():
    assert Dose("caffeine", "100mg") + Dose("caffeine", "100mg")

    assert Dose("", "0g") + Dose("", "1g") == Dose("", "1.0g")
    assert Dose("", "1mg") + Dose("", "10mg") == Dose("", "11.0mg")
    assert Dose("", "500mcg") + Dose("", "1mg") == Dose("", "1.5mg")
    assert Dose("", "100mcg") + Dose("", "100ug") == Dose("", "200.0ug")
    assert Dose("", "100mcg") + Dose("", "100μg") == Dose("", "200.0ug")

    assert Dose("", "1ml") + Dose("", "2ml") == Dose("", "3.0ml")
    assert Dose("", "1dl") + Dose("", "4dl") == Dose("", "500.0ml")
    assert Dose("", "1.0dl") + Dose("", "0l") == Dose("", "100.0ml")

    assert Dose("", "33cl") + Dose("", "1l") == Dose("", "1.33l")


def test_dose_format():
    d = Dose("Caffeine", "0.1g")
    assert str(d) == "100mg Caffeine"

    d = Dose("Potent stuff", "100mcg")
    assert str(d) == "100mcg Potent stuff"
