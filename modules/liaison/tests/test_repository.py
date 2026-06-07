from __future__ import annotations

import importlib


def test_liaison_repository_creates_incident_scoped_feedback(monkeypatch, tmp_path):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    import utils.db as db
    import utils.incident_context as incident_context
    import modules.liaison.repository as repository

    importlib.reload(incident_context)
    importlib.reload(db)
    importlib.reload(repository)
    incident_context.set_active_incident("LIAISON-TEST")

    agency_id = repository.create_agency(
        {
            "name": "County Emergency Management",
            "agency_type": "Government",
            "jurisdiction": "County",
            "current_status": "Supporting",
            "priority": "High",
        }
    )
    interaction_id = repository.create_interaction(
        {
            "agency_id": agency_id,
            "interaction_type": "Meeting",
            "subject": "Coordination briefing",
            "summary": "Reviewed stakeholder concerns.",
            "followup_action": "Route concern to Planning",
            "followup_assigned_to": "Liaison Officer",
            "task_id": 42,
        }
    )
    feedback_id = repository.create_feedback(
        {
            "agency_id": agency_id,
            "interaction_id": interaction_id,
            "feedback_type": "Concern",
            "priority": "Critical",
            "summary": "Stakeholder requested revised access plan.",
            "requested_action": "Validate the planned route with the county.",
            "assigned_section": "Planning",
            "status": "Open",
            "task_id": 42,
            "resource_request_id": 7,
            "validation_status": "Requires Revision",
        }
    )

    agency_rows = repository.fetch_agency_rows()
    assert agency_rows[0]["id"] == agency_id
    assert agency_rows[0]["open_feedback_items"] == 1

    feedback_rows = repository.fetch_feedback_rows()
    assert feedback_rows[0]["id"] == feedback_id
    assert feedback_rows[0]["linked_item"] == "Task #42"
    assert feedback_rows[0]["resolution_status"] == "Requires Revision"

    task_feedback = repository.fetch_feedback_for_task(42)
    assert task_feedback[0]["summary"] == "Stakeholder requested revised access plan."

    con = db.get_incident_conn()
    try:
        audit_count = con.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
        followup_count = con.execute("SELECT COUNT(*) FROM liaison_followup_actions").fetchone()[0]
        assert audit_count >= 3
        assert followup_count == 1
    finally:
        con.close()
