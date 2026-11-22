"""`/api/auth/lookup` catalog prefill fields (see auth_sessions.py).

The mobile client pre-populates a brand-new local profile from this
response (ProfileScreen._lookupPersonId) instead of making the operator
retype a record that already exists, so `found` must carry the full set of
fields `LocalProfile.fromJson` reads.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db


PERSON_RECORD = 9101
PERSON_ID = "test-auth-lookup-9101"


def _personnel_col():
    return get_master_db()[MasterCollections.PERSONNEL]


def _clear():
    _personnel_col().delete_many({"person_record": PERSON_RECORD})


def test_lookup_found_includes_catalog_prefill_fields():
    _clear()
    _personnel_col().insert_one(
        {
            "person_record": PERSON_RECORD,
            "person_id": PERSON_ID,
            "first_name": "Prefill",
            "last_name": "Test",
            "organization": "Test Org",
            "home_unit": "Unit 7",
            "primary_role": "Ground Team Member",
            "rank": "Captain",
            "callsign": "Test-1",
            "title": "Member",
            "phone": "555-0100",
            "email": "prefill@example.com",
            "radio_id": "R-100",
            "status": "available",
            "is_medic": True,
            "certifications": [{"cert_type_id": 3, "level": 2}],
        }
    )
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/api/auth/lookup", params={"person_id": PERSON_ID})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "found"
    person = body["person"]
    assert person["home_unit"] == "Unit 7"
    assert person["primary_role"] == "Ground Team Member"
    assert person["rank"] == "Captain"
    assert person["callsign"] == "Test-1"
    assert person["status"] == "available"
    assert person["is_medic"] is True
    assert person["certifications"] == [{"cert_type_id": 3, "level": 2}]
    _clear()


def test_lookup_not_found_has_no_prefill_fields():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/api/auth/lookup", params={"person_id": PERSON_ID})
    assert res.status_code == 200
    assert res.json() == {"status": "not_found", "person": None}


def test_lookup_ambiguous_lists_every_matching_record_so_caller_can_pick():
    """A duplicated person_id must not dead-end sign-in: the response lists
    every candidate record (with its person_record) so the client can let
    the operator pick which one is theirs instead of being told to find an
    administrator."""

    _clear()
    _personnel_col().insert_one(
        {"person_record": PERSON_RECORD, "person_id": PERSON_ID, "first_name": "First", "last_name": "Dup"}
    )
    _personnel_col().insert_one(
        {"person_record": PERSON_RECORD + 1, "person_id": PERSON_ID, "first_name": "Second", "last_name": "Dup"}
    )
    app = create_app()
    try:
        with TestClient(app) as client:
            res = client.get("/api/auth/lookup", params={"person_id": PERSON_ID})
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ambiguous"
        assert body["person"] is None
        records = {c["person_record"] for c in body["candidates"]}
        assert records == {PERSON_RECORD, PERSON_RECORD + 1}
    finally:
        _personnel_col().delete_many({"person_record": PERSON_RECORD + 1})
        _clear()


def test_lookup_ignores_a_soft_deleted_duplicate():
    """A soft-deleted record (`deleted: true`) must not be offered as a pick
    for an ambiguous ID -- `mobile_context._require_master_person` already
    treats it as gone, so letting the operator choose it just moves the
    dead end from sign-in to the incident-entry step. With only one live
    record left, the ID should resolve as `found`, not `ambiguous`."""

    _clear()
    _personnel_col().insert_one(
        {"person_record": PERSON_RECORD, "person_id": PERSON_ID, "first_name": "Live", "last_name": "Dup"}
    )
    _personnel_col().insert_one(
        {
            "person_record": PERSON_RECORD + 1,
            "person_id": PERSON_ID,
            "first_name": "Deleted",
            "last_name": "Dup",
            "deleted": True,
        }
    )
    app = create_app()
    try:
        with TestClient(app) as client:
            res = client.get("/api/auth/lookup", params={"person_id": PERSON_ID})
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "found"
        assert body["person"]["person_record"] == PERSON_RECORD
    finally:
        _personnel_col().delete_many({"person_record": PERSON_RECORD + 1})
        _clear()
