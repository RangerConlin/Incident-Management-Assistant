"""Coverage for the "lockdown" collections:
organizations/ranks, resource types/capabilities, and the form catalog are
admin-controlled taxonomies, writable only on the central catalog
(sarapp_central_master). A local catalog (sarapp_master) must get a 403 on
any create/update/delete against these, while reads and central-catalog
writes keep working exactly as before.
"""
from __future__ import annotations

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

import pytest
from fastapi import HTTPException

from sarapp_db.api.routers import (
    certification_types,
    forms,
    lookup_types,
    organizations,
    qualification_types,
    resource_types,
)
from sarapp_db.mongo.database_manager import DB_CENTRAL_MASTER, DB_MASTER
from sarapp_db.mongo.mongo_client import get_client

_LOCAL_DB = "TEST_LOCKDOWN_LOCAL_MASTER"
_CENTRAL_DB = "TEST_LOCKDOWN_CENTRAL_MASTER"


@pytest.fixture
def lockdown_env(monkeypatch):
    monkeypatch.setattr("sarapp_db.mongo.database_manager.DB_MASTER", _LOCAL_DB, raising=False)
    monkeypatch.setattr("sarapp_db.mongo.database_manager.DB_CENTRAL_MASTER", _CENTRAL_DB, raising=False)
    get_client().drop_database(_LOCAL_DB)
    get_client().drop_database(_CENTRAL_DB)
    yield
    get_client().drop_database(_LOCAL_DB)
    get_client().drop_database(_CENTRAL_DB)


def _as_local(monkeypatch) -> None:
    monkeypatch.delenv("SARAPP_MASTER_DB_NAME", raising=False)
    monkeypatch.setattr(organizations, "get_master_db", lambda: get_client()[_LOCAL_DB])
    monkeypatch.setattr(resource_types, "get_master_db", lambda: get_client()[_LOCAL_DB])
    monkeypatch.setattr(forms, "get_master_db", lambda: get_client()[_LOCAL_DB])
    monkeypatch.setattr(lookup_types, "get_master_db", lambda: get_client()[_LOCAL_DB])
    monkeypatch.setattr(certification_types, "get_master_db", lambda: get_client()[_LOCAL_DB])
    monkeypatch.setattr(qualification_types, "get_master_db", lambda: get_client()[_LOCAL_DB])


def _as_central(monkeypatch) -> None:
    monkeypatch.setattr(organizations, "get_master_db", lambda: get_client()[_CENTRAL_DB])
    monkeypatch.setattr(resource_types, "get_master_db", lambda: get_client()[_CENTRAL_DB])
    monkeypatch.setattr(forms, "get_master_db", lambda: get_client()[_CENTRAL_DB])
    monkeypatch.setattr(lookup_types, "get_master_db", lambda: get_client()[_CENTRAL_DB])
    monkeypatch.setattr(certification_types, "get_master_db", lambda: get_client()[_CENTRAL_DB])
    monkeypatch.setattr(qualification_types, "get_master_db", lambda: get_client()[_CENTRAL_DB])


def test_organizations_write_rejected_locally_allowed_centrally(lockdown_env, monkeypatch):
    _as_local(monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        organizations.create_org_type({"name": "Local Attempt"})
    assert exc_info.value.status_code == 403

    _as_central(monkeypatch)
    created = organizations.create_org_type({"name": "Central Create"})
    assert created["name"] == "Central Create"


def test_resource_types_write_rejected_locally_allowed_centrally(lockdown_env, monkeypatch):
    _as_local(monkeypatch)
    body = resource_types.SaveResourceTypeRequest(name="Local Attempt")
    with pytest.raises(HTTPException) as exc_info:
        resource_types.create_resource_type(body)
    assert exc_info.value.status_code == 403

    _as_central(monkeypatch)
    created = resource_types.create_resource_type(resource_types.SaveResourceTypeRequest(name="Central Create"))
    assert created["name"] == "Central Create"


def test_form_family_write_rejected_locally_allowed_centrally(lockdown_env, monkeypatch):
    _as_local(monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        forms.create_family({"code": "LOCAL", "title": "Local Attempt"})
    assert exc_info.value.status_code == 403

    _as_central(monkeypatch)
    created = forms.create_family({"code": "CENTRAL", "title": "Central Create"})
    assert created["title"] == "Central Create"


def test_task_type_write_rejected_locally_allowed_centrally(lockdown_env, monkeypatch):
    _as_local(monkeypatch)
    body = lookup_types.UpsertLookupRequest(name="Local Attempt")
    with pytest.raises(HTTPException) as exc_info:
        lookup_types.create_task_type(body)
    assert exc_info.value.status_code == 403

    _as_central(monkeypatch)
    created = lookup_types.create_task_type(lookup_types.UpsertLookupRequest(name="Central Create"))
    assert created["id"] == 1


def test_team_type_write_rejected_locally_allowed_centrally(lockdown_env, monkeypatch):
    _as_local(monkeypatch)
    body = lookup_types.UpsertLookupRequest(name="Local Attempt")
    with pytest.raises(HTTPException) as exc_info:
        lookup_types.create_team_type(body)
    assert exc_info.value.status_code == 403

    _as_central(monkeypatch)
    created = lookup_types.create_team_type(lookup_types.UpsertLookupRequest(name="Central Create"))
    assert created["id"] == 1


def test_certification_type_write_rejected_locally_allowed_centrally(lockdown_env, monkeypatch):
    _as_local(monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        certification_types.create_certification_type({"code": "LOCAL", "name": "Local Attempt"})
    assert exc_info.value.status_code == 403

    _as_central(monkeypatch)
    created = certification_types.create_certification_type({"code": "GTL2", "name": "Central Create"})
    assert created["name"] == "Central Create"
    assert created["id"] == 1


def test_certification_type_list_reads_work_locally_and_centrally(lockdown_env, monkeypatch):
    _as_central(monkeypatch)
    certification_types.create_certification_type({"code": "GTL2", "name": "Central Create", "category": "SAR"})

    _as_local(monkeypatch)
    # Reads are unrestricted everywhere — only writes are lockdown-guarded.
    assert certification_types.list_certification_types(search="", category="", include_inactive=True) == []

    _as_central(monkeypatch)
    rows = certification_types.list_certification_types(search="", category="", include_inactive=True)
    assert len(rows) == 1
    assert rows[0]["code"] == "GTL2"
    assert rows[0]["tags"] == []


def test_qualification_type_write_rejected_locally_allowed_centrally(lockdown_env, monkeypatch):
    _as_local(monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        qualification_types.create_qualification_type({"code": "LOCAL", "name": "Local Attempt"})
    assert exc_info.value.status_code == 403

    _as_central(monkeypatch)
    created = qualification_types.create_qualification_type(
        {"code": "MEDIC", "name": "Medic", "any_tags": ["MEDIC"], "min_level": 2}
    )
    assert created["name"] == "Medic"
    assert created["id"] == 1
    assert created["any_tags"] == ["MEDIC"]


def test_qualification_type_list_reads_work_locally_and_centrally(lockdown_env, monkeypatch):
    _as_central(monkeypatch)
    qualification_types.create_qualification_type(
        {"code": "MEDIC", "name": "Medic", "any_tags": ["MEDIC"], "min_level": 2}
    )

    _as_local(monkeypatch)
    # Reads are unrestricted everywhere — only writes are lockdown-guarded.
    assert qualification_types.list_qualification_types(search="", include_inactive=True) == []

    _as_central(monkeypatch)
    rows = qualification_types.list_qualification_types(search="", include_inactive=True)
    assert len(rows) == 1
    assert rows[0]["code"] == "MEDIC"
    assert rows[0]["all_tags"] == []
