from modules.forms_creator.context import FormDataContext


def test_build_agency_contacts_flattens_liaison_contacts(monkeypatch):
    responses = {
        "/api/incidents/INC-42/liaison/agencies": [
            {"int_id": 7, "name": "County EOC"},
            {"int_id": 8, "name": "Sheriff Office"},
        ],
        "/api/incidents/INC-42/liaison/agencies/7/contacts": [
            {
                "title": "Coordinator",
                "name": "Alex Rivera",
                "phone": "555-0100",
                "email": "alex@example.org",
                "notes": "Primary liaison",
            },
            {
                "title": "Deputy",
                "name": "Sam Lee",
                "agency": "County EOC",
                "contact_info": "555-0101",
                "notes": "",
            },
        ],
        "/api/incidents/INC-42/liaison/agencies/8/contacts": [
            {
                "title": "Captain",
                "name": "Jamie Chen",
                "phone": "555-0102",
                "email": "jamie@example.org",
                "notes": "Night shift",
            }
        ],
    }

    def fake_get(path, params=None):
        return responses[path]

    monkeypatch.setattr("modules.forms_creator.context._get", fake_get)

    context = FormDataContext().build("INC-42")

    assert context["agency_contacts"] == [
        {
            "title": "Coordinator",
            "name": "Alex Rivera",
            "agency": "County EOC",
            "phone": "555-0100",
            "email": "alex@example.org",
            "notes": "Primary liaison",
        },
        {
            "title": "Deputy",
            "name": "Sam Lee",
            "agency": "County EOC",
            "phone": "555-0101",
            "email": "",
            "notes": "",
        },
        {
            "title": "Captain",
            "name": "Jamie Chen",
            "agency": "Sheriff Office",
            "phone": "555-0102",
            "email": "jamie@example.org",
            "notes": "Night shift",
        },
    ]


def test_build_liaison_data_wires_all_liaison_collections(monkeypatch):
    responses = {
        "/api/incidents/INC-99": {},
        "/api/incidents/INC-99/operational-periods": [],
        "/api/incidents/INC-99/org/assignments": [],
        "/api/incidents/INC-99/comms/channels": [],
        "/api/incidents/INC-99/teams": [],
        "/api/incidents/INC-99/tasks": [],
        "/api/objectives": [],
        "/api/incidents/INC-99/resources": [],
        "/api/incidents/INC-99/meetings": [],
        "/api/master/aircraft": [],
        "/api/master/personnel": [],
        "/api/master/vehicles": [],
        "/api/master/equipment": [],
        "/api/comms/channels": [],
        "/api/resource-types": [],
        "/api/incidents/INC-99/comms-log": [],
        "/api/incidents/INC-99/liaison/agencies": [
            {
                "int_id": 7,
                "name": "County EOC",
                "agency_type": "Government",
                "jurisdiction": "County",
                "current_status": "Supporting",
                "assigned_liaison": "Pat Morgan",
                "last_contact": "2026-06-23T09:00:00",
                "next_contact_due": "2026-06-24T09:00:00",
                "priority": "High",
                "notes": "Primary partner",
                "created_at": "2026-06-22T10:00:00",
                "updated_at": "2026-06-23T08:00:00",
            }
        ],
        "/api/incidents/INC-99/liaison/interactions": [
            {
                "int_id": 21,
                "agency_id": 7,
                "interaction_type": "Meeting",
                "occurred_at": "2026-06-23T09:00:00",
                "subject": "Coordination briefing",
                "summary": "Reviewed stakeholder concerns.",
                "followup_action": "Route concern to Planning",
                "followup_assigned_to": "Liaison Officer",
                "followup_due": "2026-06-24",
                "task_id": 42,
                "created_at": "2026-06-23T09:01:00",
            }
        ],
        "/api/incidents/INC-99/liaison/feedback": [
            {
                "int_id": 31,
                "agency_id": 7,
                "interaction_id": 21,
                "feedback_type": "Concern",
                "priority": "Critical",
                "summary": "Stakeholder requested revised access plan.",
                "requested_action": "Validate the planned route with the county.",
                "assigned_section": "Planning",
                "assigned_to": "Jamie",
                "status": "Open",
                "task_id": 42,
                "resource_request_id": 7,
                "validation_status": "Requires Revision",
                "followup_due": "2026-06-24",
                "entered_ts": "2026-06-23T09:05:00",
            }
        ],
        "/api/incidents/INC-99/liaison/agency-requests": [
            {
                "int_id": 41,
                "agency_id": 7,
                "description": "Portable radios",
                "requested_by": "County EOC",
                "priority": "High",
                "status": "Open",
                "due_date": "2026-06-24",
                "notes": "Need before night shift",
            }
        ],
        "/api/incidents/INC-99/liaison/resource-offers": [
            {
                "int_id": 51,
                "agency_id": 7,
                "description": "Barricades",
                "offered_by": "Supply Lead",
                "quantity": "12",
                "available_from": "2026-06-23T12:00:00",
                "status": "Accepted",
                "notes": "Deliver to staging",
            }
        ],
        "/api/incidents/INC-99/liaison/agencies/7/detail": {
            "contacts": [
                {
                    "int_id": 61,
                    "agency_id": 7,
                    "name": "Alex Rivera",
                    "role": "Coordinator",
                    "phone": "555-0100",
                    "email": "alex@example.org",
                    "radio_channel": "LIAISON-1",
                    "preferred_contact": "Radio",
                    "notes": "Primary liaison",
                }
            ],
            "followups": [
                {
                    "int_id": 71,
                    "agency_id": 7,
                    "feedback_id": 31,
                    "action_summary": "Call back with route update",
                    "assigned_to": "Pat Morgan",
                    "due_at": "2026-06-24",
                    "status": "Open",
                }
            ],
            "restrictions": [
                {
                    "int_id": 81,
                    "agency_id": 7,
                    "restriction_type": "Access",
                    "description": "Gate access requires escort",
                    "effective_at": "2026-06-23T00:00:00",
                    "expires_at": "2026-06-25T00:00:00",
                    "status": "Active",
                }
            ],
            "agreements": [
                {
                    "int_id": 91,
                    "agency_id": 7,
                    "agreement_type": "MOU",
                    "description": "Temporary shelter support",
                    "effective_at": "2026-06-23T00:00:00",
                    "expires_at": "2026-06-30T00:00:00",
                    "status": "Signed",
                }
            ],
        },
    }

    def fake_get(path, params=None):
        if path == "/api/objectives":
            return responses[path]
        return responses[path]

    monkeypatch.setattr("modules.forms_creator.context._get", fake_get)

    context = FormDataContext().build("INC-99")

    assert context["liaison_agencies"][0]["name"] == "County EOC"
    assert context["liaison_contacts"][0]["title"] == "Coordinator"
    assert context["liaison_contacts"][0]["radio_channel"] == "LIAISON-1"
    assert context["agency_contacts"][0]["agency"] == "County EOC"
    assert context["liaison_interactions"][0]["followup_action"] == "Route concern to Planning"
    assert context["liaison_feedback"][0]["validation_status"] == "Requires Revision"
    assert context["liaison_agency_requests"][0]["description"] == "Portable radios"
    assert context["liaison_resource_offers"][0]["available_from"] == "2026-06-23T12:00:00"
    assert context["liaison_followup_actions"][0]["action_summary"] == "Call back with route update"
    assert context["liaison_restrictions"][0]["restriction_type"] == "Access"
    assert context["liaison_agreements"][0]["agreement_type"] == "MOU"
