from modules.personnel.services.cert_formatter import level_to_label, label_to_level, render_badge


def test_level_label_roundtrip():
    assert level_to_label(0) == "None"
    assert level_to_label(1) == "Trainee"
    assert level_to_label(2) == "Qualified"
    assert level_to_label(3) == "Evaluator"
    assert label_to_level("none") == 0
    assert label_to_level("Trainee") == 1
    assert label_to_level("qualified") == 2
    assert label_to_level("EVALUATOR") == 3


def test_render_badge_rules():
    assert render_badge("ICS-100", 0) == ""
    assert render_badge("ICS-100", 1) == "ICS-100-T"
    assert render_badge("ICS-100", 2) == "ICS-100"
    assert render_badge("ICS-100", 3) == "ICS-100-SET"

