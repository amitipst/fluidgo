from app.services.company_backfill_service import (
    display_name, is_usable_company, is_usable_person, norm_company, norm_person, similar_pairs, split_person)


def test_norm_company_ignores_suffix_case_punctuation():
    assert norm_company("Team Aviation India Pvt. Ltd.") == norm_company("team aviation india")


def test_group_and_systems_stay_separate():
    assert norm_company("Sunpack Group") != norm_company("Sunpack Systems")


def test_placeholders_not_usable():
    for s in ("", " ", "NA", "n/a", "TBD", "-", "x"):
        assert not is_usable_company(s)
    assert is_usable_company("Acme")
    assert not is_usable_person("None") and is_usable_person("Ravi Kumar")


def test_display_name_prefers_most_used_then_longest():
    assert display_name(["Acme", "Acme", "Acme Pvt Ltd"]) == "Acme"
    assert display_name(["Acme", "Acme Pvt Ltd"]) == "Acme Pvt Ltd"


def test_split_person_strips_title():
    assert split_person("Mr. Ravi Kumar Singh") == ("Ravi", "Kumar Singh")
    assert split_person("Priya") == ("Priya", None)
    assert split_person("") == ("", None)


def test_norm_person():
    assert norm_person("Dr. Anil  Rao") == "anil rao"


def test_similar_pairs_flags_but_never_equal_names():
    pairs = similar_pairs(["Sunpack Group", "Sunpack Systems", "Sunpack Solutions", "Zenith Corp"])
    flat = {x for p in pairs for x in p}
    assert "Sunpack Group" in flat and "Zenith Corp" not in flat
    assert similar_pairs(["Acme Ltd", "ACME Limited"]) == []
