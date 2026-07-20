"""Unit tests for the Liaison Reporting Board and customer-request conversion
repository helpers, mocking the API client (no live server required).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_api_client(monkeypatch):
    import utils.api_client as api_client_mod

    client = MagicMock()
    monkeypatch.setattr(api_client_mod, "api_client", client)
    return client


def test_fetch_reporting_digests_hits_expected_endpoint(mock_api_client):
    import modules.liaison.repository as repository

    mock_api_client.get.return_value = [{"int_id": 1, "source_type": "task"}]
    result = repository.fetch_reporting_digests(incident_id="INC-1")

    mock_api_client.get.assert_called_once_with("/api/incidents/INC-1/liaison/reporting-digests")
    assert result == [{"int_id": 1, "source_type": "task"}]


def test_create_reporting_digest_posts_note(mock_api_client):
    import modules.liaison.repository as repository

    mock_api_client.post.return_value = {"int_id": 2}
    repository.create_reporting_digest(
        "Task closed out, all clear.",
        source_type="objective",
        source_id="obj-9",
        submitted_by="ops1",
        incident_id="INC-1",
    )

    mock_api_client.post.assert_called_once_with(
        "/api/incidents/INC-1/liaison/reporting-digests",
        json={
            "raw_note": "Task closed out, all clear.",
            "source_type": "objective",
            "source_id": "obj-9",
            "submitted_by": "ops1",
        },
    )


def test_update_reporting_digest_patches_lofr_summary(mock_api_client):
    import modules.liaison.repository as repository

    mock_api_client.patch.return_value = {"int_id": 3, "ready_to_report": True}
    repository.update_reporting_digest(3, {"ready_to_report": True}, incident_id="INC-1")

    mock_api_client.patch.assert_called_once_with(
        "/api/incidents/INC-1/liaison/reporting-digests/3",
        json={"ready_to_report": True},
    )


def test_convert_agency_request_to_objective_marks_request_converted(mock_api_client, monkeypatch):
    import modules.liaison.repository as repository

    def fake_post(path, json=None, params=None):
        assert json["origin_module"] == "liaison"
        assert json["origin_id"] == "5"
        return {"_id": "obj-1"}

    def fake_get(path, params=None):
        if path.endswith("/tasks") or path.endswith("/audit"):
            return []
        return {
            "_id": "obj-1", "code": "OBJ-1", "text": "Need support", "priority": "high",
            "status": "draft", "owner_section": None, "tags": [], "op_period_id": None,
            "updated_at": None, "updated_by": None, "display_order": 0, "strategies": 0,
            "open_tasks": 0, "total_tasks": 0, "task_links": [], "narrative": None,
        }

    mock_api_client.post.side_effect = fake_post
    mock_api_client.get.side_effect = fake_get
    mock_api_client.patch.return_value = {}

    result = repository.convert_agency_request_to_objective(
        "Need support", 5, priority="high", incident_id="INC-1"
    )

    assert result == {"objective_id": "obj-1"}
    mock_api_client.patch.assert_called_once_with(
        "/api/incidents/INC-1/liaison/agency-requests/5/converted",
        json={"converted_to_type": "objective", "converted_to_id": "obj-1"},
    )


def test_convert_agency_request_to_task_marks_request_converted(mock_api_client, monkeypatch):
    import modules.liaison.repository as repository
    from utils import incident_context

    incident_context.set_active_incident("INC-1")
    mock_api_client.get.return_value = []
    mock_api_client.post.return_value = {"int_id": 77}
    mock_api_client.patch.return_value = {}

    result = repository.convert_agency_request_to_task(
        "Set up a perimeter check", 6, priority="High", incident_id="INC-1"
    )

    assert result == {"task_id": 77}
    post_call = mock_api_client.post.call_args
    assert post_call.args[0] == "/api/incidents/INC-1/operations/tasks"
    assert post_call.kwargs["json"]["origin_module"] == "liaison"
    assert post_call.kwargs["json"]["origin_id"] == "6"
    mock_api_client.patch.assert_called_once_with(
        "/api/incidents/INC-1/liaison/agency-requests/6/converted",
        json={"converted_to_type": "task", "converted_to_id": "77"},
    )
