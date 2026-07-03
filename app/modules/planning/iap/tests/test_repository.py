"""Integration tests for the IAP API router (replaces SQLite repository tests).

These tests require a running MongoDB instance at SARAPP_MONGO_URI
(default: mongodb://localhost:27017) and follow the same pattern as
data/db/sarapp_db/api/routers/tests/test_weather.py.
"""
from __future__ import annotations

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[5]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient
from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db

INCIDENT_ID = "TEST-IAP-REPO"


def _cleanup(db):
    db["iap_packages"].delete_many({"incident_id": INCIDENT_ID})


def test_iap_package_crud():
    db = get_incident_db(INCIDENT_ID)
    _cleanup(db)

    app = create_app()
    with TestClient(app) as client:
        base = f"/api/incidents/{INCIDENT_ID}/iap"

        # List — empty
        res = client.get(f"{base}/packages")
        assert res.status_code == 200
        assert res.json() == []

        # Create package via PUT (upsert)
        pkg_payload = {
            "incident_id": INCIDENT_ID,
            "op_start": "2025-09-23T07:00:00",
            "op_end": "2025-09-23T19:00:00",
            "status": "draft",
            "notes": "",
        }
        res = client.put(f"{base}/packages/1", json=pkg_payload)
        assert res.status_code == 200
        pkg = res.json()
        assert pkg["op_number"] == 1
        assert pkg["status"] == "draft"
        assert pkg["forms"] == []

        # Add a form
        form_payload = {
            "form_id": "ICS-202",
            "title": "Incident Objectives",
            "op_number": 1,
            "fields": {"incident_name": "Test Incident"},
        }
        res = client.put(f"{base}/packages/1/forms/ICS-202", json=form_payload)
        assert res.status_code == 200
        pkg = res.json()
        assert len(pkg["forms"]) == 1
        assert pkg["forms"][0]["form_id"] == "ICS-202"
        assert pkg["forms"][0]["fields"]["incident_name"] == "Test Incident"

        # Add a second form
        form2 = {
            "form_id": "ICS-205",
            "title": "Communications Plan",
            "op_number": 1,
            "fields": {"nets": ["TAC-1"]},
            "display_order": 1,
        }
        res = client.put(f"{base}/packages/1/forms/ICS-205", json=form2)
        assert res.status_code == 200
        pkg = res.json()
        assert len(pkg["forms"]) == 2

        # Get package — full detail
        res = client.get(f"{base}/packages/1")
        assert res.status_code == 200
        pkg = res.json()
        assert pkg["op_number"] == 1
        assert len(pkg["forms"]) == 2

        # Update form order
        res = client.put(f"{base}/packages/1/forms-order", json={"order": ["ICS-205", "ICS-202"]})
        assert res.status_code == 200
        pkg = res.json()
        assert [f["form_id"] for f in pkg["forms"]] == ["ICS-205", "ICS-202"]

        # Delete a form
        res = client.delete(f"{base}/packages/1/forms/ICS-205")
        assert res.status_code == 204

        res = client.get(f"{base}/packages/1")
        pkg = res.json()
        assert len(pkg["forms"]) == 1
        assert pkg["forms"][0]["form_id"] == "ICS-202"

        # Create second package
        pkg2 = {**pkg_payload, "op_start": "2025-09-23T19:00:00", "op_end": "2025-09-24T07:00:00"}
        client.put(f"{base}/packages/2", json=pkg2)

        # List — ordered by op_number
        res = client.get(f"{base}/packages")
        assert res.status_code == 200
        pkgs = res.json()
        assert [p["op_number"] for p in pkgs] == [1, 2]

        # Update package status
        updated = {**pkg_payload, "status": "published", "version_tag": "OP1-FINAL-v1"}
        res = client.put(f"{base}/packages/1", json=updated)
        assert res.status_code == 200
        assert res.json()["status"] == "published"

        # 404 for unknown package
        res = client.get(f"{base}/packages/99")
        assert res.status_code == 404

    _cleanup(db)
