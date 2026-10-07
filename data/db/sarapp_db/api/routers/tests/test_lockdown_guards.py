"""Coverage for the "lockdown" collections (see Design Documents/Instructions/
mongodb_schema_decisions.md and backlog.md's dual-key/lockdown split):
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

from sarapp_db.api.routers import forms, lookup_types, organizations, resource_types
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


def _as_central(monkeypatch) -> None:
    monkeypatch.setattr(organizations, "get_master_db", lambda: get_client()[_CENTRAL_DB])
    monkeypatch.setattr(resource_types, "get_master_db", lambda: get_client()[_CENTRAL_DB])
    monkeypatch.setattr(forms, "get_master_db", lambda: get_client()[_CENTRAL_DB])
    monkeypatch.setattr(lookup_types, "get_master_db", lambda: get_client()[_CENTRAL_DB])


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
