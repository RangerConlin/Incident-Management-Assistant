"""Desktop-side repository tests for Resource Associations (no Qt, no Mongo)."""
from __future__ import annotations

from modules.admin.resource_associations.data.repository import ApiResourceAssociationRepository
from modules.admin.resource_associations.models import ResourceAssociation, ResourceEndpoint
from utils.api_client import api_client


def test_list_for_resource_builds_expected_params(monkeypatch):
    seen = {}

    def fake_get(path, params=None):
        seen["path"] = path
        seen["params"] = params
        return [
            {
                "id": "assoc-1",
                "source": {"resource_type": "personnel", "resource_id": 5},
                "target": {"resource_type": "vehicle", "resource_id": 9},
                "source_label": "Jane Doe",
                "target_label": "Engine 1",
                "association_type": "Assigned",
                "active": True,
            }
        ]

    monkeypatch.setattr(api_client, "get", fake_get)
    repo = ApiResourceAssociationRepository()
    rows = repo.list_for_resource("personnel", 5)

    assert seen["path"] == "/api/resource-associations"
    assert seen["params"]["resource_type"] == "personnel"
    assert seen["params"]["resource_id"] == 5
    assert len(rows) == 1
    assert rows[0].source.resource_type == "personnel"
    assert rows[0].target.label == "Engine 1"
    assert rows[0].association_type == "Assigned"


def test_create_sends_endpoint_payload(monkeypatch):
    sent = {}

    def fake_post(path, json=None):
        sent["path"] = path
        sent["json"] = json
        return {
            "id": "assoc-2",
            "source": json["source"],
            "target": json["target"],
            "association_type": json["association_type"],
            "active": True,
        }

    monkeypatch.setattr(api_client, "post", fake_post)
    repo = ApiResourceAssociationRepository()
    association = ResourceAssociation(
        source=ResourceEndpoint(resource_type="vehicle", resource_id=1),
        target=ResourceEndpoint(resource_type="equipment", resource_id=2),
        association_type="Carried/Onboard",
    )
    result = repo.create(association)

    assert sent["path"] == "/api/resource-associations"
    assert sent["json"]["source"] == {"resource_type": "vehicle", "resource_id": 1}
    assert sent["json"]["target"] == {"resource_type": "equipment", "resource_id": 2}
    assert result.id == "assoc-2"


def test_delete_calls_expected_endpoint(monkeypatch):
    calls = []
    monkeypatch.setattr(api_client, "delete", lambda path, params=None: calls.append(path))
    ApiResourceAssociationRepository().delete("assoc-3")
    assert calls == ["/api/resource-associations/assoc-3"]
