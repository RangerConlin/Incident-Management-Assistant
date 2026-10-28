from __future__ import annotations

def test_liaison_repository_uses_incident_scoped_feedback_api(monkeypatch):
    import modules.liaison.repository as repository
    from utils.api_client import api_client

    calls: list[tuple[str, str, object]] = []
    feedback = {"id": 9, "summary": "Stakeholder requested revised access plan."}

    monkeypatch.setattr(
        api_client,
        "post",
        lambda path, json: calls.append(("POST", path, json)) or {"id": len(calls)},
    )
    monkeypatch.setattr(
        api_client,
        "get",
        lambda path, params=None: calls.append(("GET", path, params)) or [feedback],
    )

    agency = repository.create_agency({"name": "County Emergency Management"}, "LIAISON-TEST")
    interaction = repository.create_interaction({"agency_id": agency["id"]}, "LIAISON-TEST")
    created = repository.create_feedback(
        {"agency_id": agency["id"], "interaction_id": interaction["id"], "task_id": 42},
        "LIAISON-TEST",
    )
    task_feedback = repository.fetch_feedback_for_task(42, "LIAISON-TEST")

    assert created == {"id": 3}
    assert task_feedback == [feedback]
    assert calls == [
        ("POST", "/api/incidents/LIAISON-TEST/liaison/agencies", {"name": "County Emergency Management"}),
        ("POST", "/api/incidents/LIAISON-TEST/liaison/interactions", {"agency_id": 1}),
        (
            "POST",
            "/api/incidents/LIAISON-TEST/liaison/feedback",
            {"agency_id": 1, "interaction_id": 2, "task_id": 42},
        ),
        ("GET", "/api/incidents/LIAISON-TEST/liaison/feedback", {"task_id": 42}),
    ]
