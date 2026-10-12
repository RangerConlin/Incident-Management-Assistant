"""Coverage for cert_api.qualifications_met() — the pure tag/level matching
logic backing the personnel editor's live "Qualifications Met" display.
"""
from __future__ import annotations

from modules.personnel.api import cert_api

_CATALOG_BY_ID = {
    2003: {"code": "EMT", "name": "Emergency Medical Technician", "tags": ["MEDIC", "MEDICAL"]},
    6004: {"code": "GTL", "name": "Ground Team Leader", "tags": ["LSAR_TL"]},
}

_MEDIC_QUALIFICATION = {
    "code": "MEDICAL_PROVIDER",
    "name": "Medical Provider (Field)",
    "any_tags": ["MEDIC"],
    "all_tags": [],
    "min_level": 2,
}


def test_qualifications_met_matches_on_any_tag_and_min_level(monkeypatch):
    monkeypatch.setattr(cert_api, "list_qualifications", lambda: [_MEDIC_QUALIFICATION])

    met = cert_api.qualifications_met([{"cert_type_id": 2003, "level": 2}], _CATALOG_BY_ID)

    assert [q["code"] for q in met] == ["MEDICAL_PROVIDER"]


def test_qualifications_met_rejects_below_min_level(monkeypatch):
    monkeypatch.setattr(cert_api, "list_qualifications", lambda: [_MEDIC_QUALIFICATION])

    met = cert_api.qualifications_met([{"cert_type_id": 2003, "level": 1}], _CATALOG_BY_ID)

    assert met == []


def test_qualifications_met_rejects_wrong_tag(monkeypatch):
    monkeypatch.setattr(cert_api, "list_qualifications", lambda: [_MEDIC_QUALIFICATION])

    met = cert_api.qualifications_met([{"cert_type_id": 6004, "level": 3}], _CATALOG_BY_ID)

    assert met == []


def test_qualifications_met_uses_highest_level_per_cert(monkeypatch):
    monkeypatch.setattr(cert_api, "list_qualifications", lambda: [_MEDIC_QUALIFICATION])

    met = cert_api.qualifications_met(
        [{"cert_type_id": 2003, "level": 1}, {"cert_type_id": 2003, "level": 2}],
        _CATALOG_BY_ID,
    )

    assert [q["code"] for q in met] == ["MEDICAL_PROVIDER"]


def test_qualifications_met_requires_all_tags_when_present(monkeypatch):
    qualification = dict(_MEDIC_QUALIFICATION, any_tags=[], all_tags=["MEDIC", "MEDICAL"])
    monkeypatch.setattr(cert_api, "list_qualifications", lambda: [qualification])

    met = cert_api.qualifications_met([{"cert_type_id": 2003, "level": 2}], _CATALOG_BY_ID)

    assert [q["code"] for q in met] == ["MEDICAL_PROVIDER"]

    qualification_missing_tag = dict(_MEDIC_QUALIFICATION, any_tags=[], all_tags=["MEDIC", "EMT_ADVANCED"])
    monkeypatch.setattr(cert_api, "list_qualifications", lambda: [qualification_missing_tag])

    assert cert_api.qualifications_met([{"cert_type_id": 2003, "level": 2}], _CATALOG_BY_ID) == []
