from modules.forms_creator.context import FormDataContext


def test_build_agency_contacts_flattens_liaison_contacts(monkeypatch):
    responses = {
        "/api/incidents/INC-42": {},
        "/api/incidents/INC-42/operational-periods": [],
        "/api/incidents/INC-42/org/assignments": [],
        "/api/incidents/INC-42/comms/channels": [],
        "/api/incidents/INC-42/teams": [],
        "/api/incidents/INC-42/tasks": [],
        "/api/objectives": [],
        "/api/incidents/INC-42/resources": [],
        "/api/incidents/INC-42/ics214/streams": [],
        "/api/incidents/INC-42/meetings": [],
        "/api/incidents/INC-42/snapshot": {"collections": {"hazards": [], "cap_orm_summaries": [], "cap_orm_audit": []}},
        "/api/incidents/INC-42/safety/reports": [],
        "/api/incidents/INC-42/safety/zones": [],
        "/api/incidents/INC-42/safety/iwi": [],
        "/api/hazard-types": [],
        "/api/master/safety-templates": [],
        "/api/master/aircraft": [],
        "/api/master/personnel": [],
        "/api/master/vehicles": [],
        "/api/master/equipment": [],
        "/api/comms/channels": [],
        "/api/resource-types": [],
        "/api/incidents/INC-42/comms-log": [],
        "/api/incidents/INC-42/liaison/agencies": [
            {"int_id": 7, "name": "County EOC"},
            {"int_id": 8, "name": "Sheriff Office"},
        ],
        "/api/incidents/INC-42/liaison/interactions": [],
        "/api/incidents/INC-42/liaison/feedback": [],
        "/api/incidents/INC-42/liaison/agency-requests": [],
        "/api/incidents/INC-42/liaison/resource-offers": [],
        "/api/incidents/INC-42/liaison/agencies/7/detail": {
            "contacts": [
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
            "followups": [],
            "restrictions": [],
            "agreements": [],
        },
        "/api/incidents/INC-42/liaison/agencies/8/detail": {
            "contacts": [
                {
                    "title": "Captain",
                    "name": "Jamie Chen",
                    "phone": "555-0102",
                    "email": "jamie@example.org",
                    "notes": "Night shift",
                }
            ],
            "followups": [],
            "restrictions": [],
            "agreements": [],
        },
    }

    def fake_get(path, params=None, **kwargs):
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
        "/api/incidents/INC-99/ics214/streams": [],
        "/api/incidents/INC-99/meetings": [],
        "/api/incidents/INC-99/snapshot": {"collections": {"hazards": [], "cap_orm_summaries": [], "cap_orm_audit": []}},
        "/api/incidents/INC-99/safety/reports": [],
        "/api/incidents/INC-99/safety/zones": [],
        "/api/incidents/INC-99/safety/iwi": [],
        "/api/hazard-types": [],
        "/api/master/safety-templates": [],
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

    def fake_get(path, params=None, **kwargs):
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


def test_build_communications_context_wires_channels_comm_log_and_narrative(monkeypatch):
    responses = {
        "/api/incidents/INC-77": {},
        "/api/incidents/INC-77/operational-periods": [],
        "/api/incidents/INC-77/org/assignments": [],
        "/api/incidents/INC-77/comms/channels": [
            {
                "id": 12,
                "channel_id": "INC-77-CH-12",
                "master_id": "9",
                "channel": "CMD-1",
                "function": "Command",
                "band": "VHF",
                "system": "Repeater",
                "mode": "FM",
                "rx_freq": "155.160",
                "tx_freq": "159.210",
                "rx_tone": "136.5",
                "tx_tone": "136.5",
                "squelch_type": "CTCSS",
                "squelch_value": "136.5",
                "repeater": 1,
                "offset": "+5.0",
                "encryption": "None",
                "assignment_division": "Division A",
                "assignment_team": "Team 3",
                "priority": "High",
                "include_on_205": 1,
                "remarks": "Primary net",
                "sort_index": 10,
                "line_a": 1,
                "line_c": 0,
                "created_at": "2026-06-25T08:00:00",
                "updated_at": "2026-06-25T09:00:00",
            }
        ],
        "/api/incidents/INC-77/teams": [],
        "/api/incidents/INC-77/tasks": [],
        "/api/objectives": [],
        "/api/incidents/INC-77/resources": [],
        "/api/incidents/INC-77/liaison/agencies": [],
        "/api/incidents/INC-77/liaison/interactions": [],
        "/api/incidents/INC-77/liaison/feedback": [],
        "/api/incidents/INC-77/liaison/agency-requests": [],
        "/api/incidents/INC-77/liaison/resource-offers": [],
        "/api/incidents/INC-77/ics214/streams": [
            {"id": "stream-1", "name": "Team-3 Field Log"},
            {"id": "stream-2", "name": "Planning Log"},
        ],
        "/api/incidents/INC-77/ics214/streams/stream-1": {
            "id": "stream-1",
            "name": "Team-3 Field Log",
            "entries": [
                {
                    "id": "entry-2",
                    "stream_id": "stream-1",
                    "timestamp_utc": "2026-06-25T11:00:00",
                    "text": "Located trail junction.",
                    "source": "manual",
                    "actor_user_id": "alex",
                    "critical_flag": True,
                    "tags": ["field"],
                }
            ],
        },
        "/api/incidents/INC-77/ics214/streams/stream-2": {
            "id": "stream-2",
            "name": "Planning Log",
            "entries": [
                {
                    "id": "entry-1",
                    "stream_id": "stream-2",
                    "timestamp_utc": "2026-06-25T10:00:00",
                    "text": "Updated IAP cover sheet.",
                    "source": "manual",
                    "actor_user_id": "jamie",
                    "critical_flag": False,
                    "tags": [],
                }
            ],
        },
        "/api/incidents/INC-77/meetings": [],
        "/api/incidents/INC-77/snapshot": {"collections": {"hazards": [], "cap_orm_summaries": [], "cap_orm_audit": []}},
        "/api/incidents/INC-77/safety/reports": [],
        "/api/incidents/INC-77/safety/zones": [],
        "/api/incidents/INC-77/safety/iwi": [],
        "/api/hazard-types": [],
        "/api/master/safety-templates": [],
        "/api/master/aircraft": [],
        "/api/master/personnel": [],
        "/api/master/vehicles": [],
        "/api/master/equipment": [],
        "/api/comms/channels": [],
        "/api/resource-types": [],
        "/api/incidents/INC-77/comms-log": [
            {
                "id": 5,
                "comms_id": "INC-77-COMMS-5",
                "ts_utc": "2026-06-25T11:05:00",
                "ts_local": "2026-06-25T07:05:00",
                "direction": "Outbound",
                "priority": "Urgent",
                "resource_id": "radio-4",
                "resource_label": "Handheld 4",
                "frequency": "155.160",
                "band": "VHF",
                "mode": "FM",
                "from_unit": "ICP",
                "to_unit": "Team 3",
                "message": "Return to staging.",
                "action_taken": "Acknowledged",
                "follow_up_required": True,
                "disposition": "Closed",
                "operator_user_id": "operator-1",
                "operator_display_name": "Pat Morgan",
                "team_id": 3,
                "task_id": 42,
                "vehicle_id": "veh-2",
                "personnel_id": "pers-4",
                "attachments": ["clip.wav"],
                "geotag_lat": 44.1,
                "geotag_lon": -72.5,
                "notification_level": "All",
                "is_status_update": True,
                "created_at": "2026-06-25T11:05:00",
                "updated_at": "2026-06-25T11:06:00",
            }
        ],
    }

    def fake_get(path, params=None, **kwargs):
        return responses[path]

    monkeypatch.setattr("modules.forms_creator.context._get", fake_get)

    context = FormDataContext().build("INC-77")

    assert context["channels"][0]["channel_id"] == "INC-77-CH-12"
    assert context["channels"][0]["system_type"] == "Repeater"
    assert context["channels"][0]["assignment"] == "Team 3"
    assert context["comm_log"][0]["comms_id"] == "INC-77-COMMS-5"
    assert context["comm_log"][0]["notification_level"] == "All"
    assert context["comm_log"][0]["attachments"] == ["clip.wav"]
    assert [entry["id"] for entry in context["narrative"]] == ["entry-1", "entry-2"]
    assert context["narrative"][1]["team_num"] == "3"
    assert context["narrative"][1]["critical"] is True


def test_build_safety_context_wires_incident_and_master_safety_collections(monkeypatch):
    responses = {
        "/api/incidents/SAFE-1": {},
        "/api/incidents/SAFE-1/operational-periods": [
            {
                "op_number": 3,
                "start_time": "2026-06-26T08:00:00",
                "end_time": "2026-06-26T20:00:00",
            }
        ],
        "/api/incidents/SAFE-1/org/assignments": [],
        "/api/incidents/SAFE-1/comms/channels": [],
        "/api/incidents/SAFE-1/teams": [],
        "/api/incidents/SAFE-1/tasks": [],
        "/api/objectives": [],
        "/api/incidents/SAFE-1/resources": [],
        "/api/incidents/SAFE-1/planning/work-assignments": [
            {
                "id": 99,
                "assignment_number": "WA-3",
                "assignment_name": "West Slope Search",
                "branch": "Operations",
                "division_group": "Division A",
                "location": "West Slope",
                "hazards": [
                    {
                        "id": 11,
                        "hazard_type_text": "Loose rock",
                        "category": "Terrain",
                        "risk_level": "H",
                        "likelihood": "Likely",
                        "severity": "Serious",
                        "control_measure": "Belay team",
                        "mitigation_text": "Use spotters",
                        "ppe_text": "Helmet",
                        "is_resolved": False,
                        "notes": "Slope on west edge",
                    }
                ],
            }
        ],
        "/api/incidents/SAFE-1/ics214/streams": [],
        "/api/incidents/SAFE-1/meetings": [],
        "/api/incidents/SAFE-1/snapshot": {
            "collections": {
                "hazards": [
                    {
                        "id": 11,
                        "incident_id": "SAFE-1",
                        "work_assignment_id": 99,
                        "hazard_type_id": 5,
                        "hazard_type_text": "Loose rock",
                        "risk_level": "H",
                        "likelihood": "Likely",
                        "severity": "Serious",
                        "control_measure": "Belay team",
                        "mitigation_text": "Use spotters",
                        "ppe_text": "Helmet",
                        "safety_message": "Watch footing",
                        "is_resolved": False,
                        "notes": "Slope on west edge",
                        "created_at": "2026-06-26T07:00:00",
                        "updated_at": "2026-06-26T07:05:00",
                    }
                ],
                "cap_orm_summaries": [
                    {
                        "id": 21,
                        "incident_id": "SAFE-1",
                        "form_type": "CAPF 160",
                        "activity": "Ground search",
                        "participants_json": "[\"Team 1\"]",
                        "hazards_json": "[\"Loose rock\"]",
                        "mitigations_json": "[\"Use spotters\"]",
                        "residual_risk": "M",
                        "created_by": "safety",
                        "created_at": "2026-06-26T07:10:00",
                        "updated_at": "2026-06-26T07:15:00",
                    }
                ],
                "cap_orm_audit": [
                    {
                        "incident_id": "SAFE-1",
                        "entity": "orm_form",
                        "entity_id": 31,
                        "action": "update",
                        "field": "activity",
                        "old_value": "Old",
                        "new_value": "Ground search",
                        "ts_iso": "2026-06-26T07:25:00",
                    }
                ],
            }
        },
        "/api/incidents/SAFE-1/safety/reports": [
            {
                "id": 1,
                "incident_id": "SAFE-1",
                "time": "2026-06-26T09:00:00",
                "location": "Division A",
                "severity": "Moderate",
                "notes": "Minor slip",
                "flagged": True,
                "reported_by": "Alex",
                "team_id": 4,
                "created_at": "2026-06-26T09:01:00",
                "updated_at": "2026-06-26T09:02:00",
            }
        ],
        "/api/incidents/SAFE-1/safety/zones": [
            {
                "id": 2,
                "incident_id": "SAFE-1",
                "name": "Cliff band",
                "coordinates_json": "[[1,2],[3,4]]",
                "severity": "High",
                "description": "Rockfall area",
                "created_at": "2026-06-26T06:00:00",
                "updated_at": "2026-06-26T06:05:00",
            }
        ],
        "/api/incidents/SAFE-1/safety/orm/form": {
            "id": 31,
            "incident_id": "SAFE-1",
            "op_period": 3,
            "activity": "Ground search",
            "prepared_by_id": 17,
            "date_iso": "2026-06-26",
            "highest_residual_risk": "M",
            "status": "draft",
            "approval_blocked": False,
            "created_at": "2026-06-26T07:00:00",
            "updated_at": "2026-06-26T07:30:00",
        },
        "/api/incidents/SAFE-1/safety/orm/hazards": [
            {
                "id": 41,
                "form_id": 31,
                "sub_activity": "Approach",
                "hazard_outcome": "Slip/fall",
                "initial_risk": "H",
                "control_text": "Use trekking poles",
                "residual_risk": "M",
                "implement_how": "Brief team",
                "implement_who": "Team lead",
                "created_at": "2026-06-26T07:31:00",
                "updated_at": "2026-06-26T07:32:00",
            }
        ],
        "/api/incidents/SAFE-1/safety/ics208": {
            "incident_id": "SAFE-1",
            "op_period": 3,
            "op_period_from": "06/26/2026 0800",
            "op_period_to": "06/26/2026 2000",
            "safety_message": "Hydrate and use helmets near the cliff band.",
            "site_safety_plan_required": True,
            "site_safety_plan_location": "Plans trailer",
            "weather_summary": "Current: KCVG VFR\nForecast: Hot with afternoon storms",
            "prepared_by_name": "Pat Morgan",
            "prepared_by_position": "SOFR",
            "prepared_by_datetime": "2026-06-26 07:40",
            "created_at": "2026-06-26T07:35:00",
            "updated_at": "2026-06-26T07:40:00",
        },
        "/api/incidents/SAFE-1/weather": {
            "incident_id": "SAFE-1",
            "icao_codes": ["KCVG", "KDAY"],
            "weather_payload": {
                "metar": {
                    "KCVG": {
                        "station": "KCVG",
                        "raw_text": "KCVG 261651Z 21012KT 10SM SCT040 29/21 A2992",
                    }
                },
                "forecast": {
                    "39.1031,-84.5120": {
                        "label": "ICP",
                        "periods": [
                            {"name": "Today", "temperature": 84, "detailed_text": "Hot and humid"},
                            {"name": "Tonight", "temperature": 68, "detailed_text": "Chance of storms"},
                        ],
                    }
                },
                "advisories": [
                    {"event": "Heat Advisory"}
                ],
            },
        },
        "/api/incidents/SAFE-1/safety/iwi": [
            {
                "id": 51,
                "form_number": 1,
                "incident_id": "SAFE-1",
                "status": "submitted",
                "op_period": 3,
                "date_of_occurrence": "2026-06-26",
                "time_of_occurrence": "1015",
                "time_reported": "1030",
                "reported_by": "Jamie",
                "location_general": "Division A",
                "location_specific": "Trail 4 switchback",
                "incident_types": ["Injury"],
                "actual_outcome": "Sprain",
                "actual_severity": "MODERATE",
                "narrative": "Responder slipped on wet rock.",
                "prepared_by": "Jamie",
                "signoffs": {"reporter": {"name": "Jamie", "signed_at": "2026-06-26T10:40:00"}},
                "created_at": "2026-06-26T10:35:00",
                "updated_at": "2026-06-26T10:40:00",
            }
        ],
        "/api/hazard-types": [
            {
                "id": 5,
                "hazard_type_id": "5",
                "name": "Loose rock",
                "display_name": "Loose Rock / Scree",
                "category": "Terrain",
                "source": "AHJ",
                "owner_agency": "County SAR",
                "description": "Unstable rocky footing",
                "default_risk_level": "H",
                "default_likelihood": "Likely",
                "default_severity": "Serious",
                "default_control_measure": "Use spotters",
                "default_ppe": "Helmet",
                "default_safety_message": "Watch footing",
                "is_active": True,
                "notes": "Review seasonally",
                "created_by": "safety",
                "updated_by": "safety",
                "aliases": ["scree"],
                "mitigations": [{"mitigation_text": "Use spotters"}],
                "ppe_items": [{"ppe_text": "Helmet"}],
                "references": [{"title": "Field guide"}],
                "resource_defaults": [{"resource_type_id": 9}],
                "mitigation_count": 1,
                "ppe_preview": "Helmet",
                "created_at": "2026-06-20T08:00:00",
                "updated_at": "2026-06-21T08:00:00",
            }
        ],
        "/api/master/safety-templates": [
            {
                "template_id": 8,
                "name": "Mountain Search",
                "description": "Common hazards for alpine incidents",
                "scenario_type": "Mountain",
                "target_forms": ["ics_208", "ics_215a"],
                "hazard_entries": [{"hazard_type_id": 5}],
                "is_active": True,
                "notes": "Use during winter storms too",
                "created_by": "planner",
                "updated_by": "planner",
                "created_at": "2026-06-01T08:00:00",
                "updated_at": "2026-06-15T08:00:00",
            }
        ],
        "/api/master/aircraft": [],
        "/api/master/personnel": [],
        "/api/master/vehicles": [],
        "/api/master/equipment": [],
        "/api/comms/channels": [],
        "/api/resource-types": [],
        "/api/incidents/SAFE-1/comms-log": [],
        "/api/incidents/SAFE-1/liaison/agencies": [],
        "/api/incidents/SAFE-1/liaison/interactions": [],
        "/api/incidents/SAFE-1/liaison/feedback": [],
        "/api/incidents/SAFE-1/liaison/agency-requests": [],
        "/api/incidents/SAFE-1/liaison/resource-offers": [],
    }

    def fake_get(path, params=None, **kwargs):
        return responses[path]

    monkeypatch.setattr("modules.forms_creator.context._get", fake_get)

    context = FormDataContext().build("SAFE-1")

    assert context["hazards"][0]["hazard_type_text"] == "Loose rock"
    assert context["safety_reports"][0]["flagged"] is True
    assert context["hazard_zones"][0]["name"] == "Cliff band"
    assert context["cap_orm_summaries"][0]["form_type"] == "CAPF 160"
    assert context["cap_orm_form"]["highest_residual_risk"] == "M"
    assert context["cap_orm_hazards"][0]["implement_who"] == "Team lead"
    assert context["cap_orm_audit"][0]["field"] == "activity"
    assert context["ics_208"]["site_safety_plan_required"] is True
    assert context["ics_208"]["weather_summary"].startswith("Current:")
    assert context["ics_215a_rows"][0]["branch_div_group"] == "Operations / Division A"
    assert context["ics_215a_rows"][0]["work_assignment"] == "WA-3 - West Slope Search"
    assert context["iwi_reports"][0]["actual_severity"] == "MODERATE"
    assert context["hazard_types"][0]["default_safety_message"] == "Watch footing"
    assert context["safety_analysis_templates"][0]["scenario_type"] == "Mountain"
    assert context["weather"]["current"]["local"].startswith("KCVG:")
    assert "Heat Advisory" in context["weather"]["conditions"]


def test_build_medical_context_wires_master_and_ics206_collections(monkeypatch):
    responses = {
        "/api/incidents/MED-1": {},
        "/api/incidents/MED-1/operational-periods": [
            {
                "op_number": 2,
                "start_time": "2026-06-26T08:00:00",
                "end_time": "2026-06-26T20:00:00",
            }
        ],
        "/api/incidents/MED-1/org/positions": [],
        "/api/incidents/MED-1/org/assignments": [],
        "/api/incidents/MED-1/comms/channels": [],
        "/api/incidents/MED-1/teams": [],
        "/api/incidents/MED-1/tasks": [],
        "/api/objectives": [],
        "/api/incidents/MED-1/resources": [],
        "/api/incidents/MED-1/liaison/agencies": [],
        "/api/incidents/MED-1/liaison/interactions": [],
        "/api/incidents/MED-1/liaison/feedback": [],
        "/api/incidents/MED-1/liaison/agency-requests": [],
        "/api/incidents/MED-1/liaison/resource-offers": [],
        "/api/incidents/MED-1/ics214/streams": [],
        "/api/incidents/MED-1/meetings": [],
        "/api/incidents/MED-1/snapshot": {"collections": {"hazards": [], "cap_orm_summaries": [], "cap_orm_audit": []}},
        "/api/incidents/MED-1/safety/reports": [],
        "/api/incidents/MED-1/safety/zones": [],
        "/api/incidents/MED-1/safety/iwi": [],
        "/api/incidents/MED-1/safety/orm/form": {},
        "/api/incidents/MED-1/safety/orm/hazards": [],
        "/api/incidents/MED-1/safety/ics208": {},
        "/api/incidents/MED-1/planning/work-assignments": [],
        "/api/hazard-types": [],
        "/api/master/safety-templates": [],
        "/api/master/aircraft": [],
        "/api/master/personnel": [],
        "/api/master/vehicles": [],
        "/api/master/equipment": [],
        "/api/master/hospitals": [
            {
                "id": 10,
                "hospital_id": "10",
                "name": "Regional Medical Center",
                "type": "Hospital",
                "phone": "555-2000",
                "phone_er": "555-2001",
                "address": "1 Main St",
                "city": "Albany",
                "state": "NY",
                "zip": "12207",
                "contact_name": "Charge Nurse",
                "helipad": True,
                "burn_center": True,
                "adult_trauma_level": 2,
                "pediatric_trauma_level": 1,
                "notes": "Primary destination",
            }
        ],
        "/api/master/ems-agencies": [
            {
                "id": 20,
                "name": "County EMS",
                "type": "Ground Ambulance",
                "service_level": 2,
                "phone": "555-3000",
                "radio_channel": "MED-1",
                "address": "2 Station Rd",
                "city": "Albany",
                "state": "NY",
                "zip": "12207",
                "default_on_206": True,
                "is_active": True,
            }
        ],
        "/api/comms/channels": [],
        "/api/resource-types": [],
        "/api/incidents/MED-1/comms-log": [],
        "/api/incidents/MED-1/medical/ics206/aid-stations": [
            {
                "id": 1,
                "op_period": 2,
                "name": "Base Aid",
                "type": "Medical Aid",
                "level": "ALS",
                "is_24_7": True,
                "notes": "Main camp",
            }
        ],
        "/api/incidents/MED-1/medical/ics206/ambulance-services": [
            {
                "id": 2,
                "op_period": 2,
                "name": "County EMS",
                "type": "Ground ALS",
                "service_level": 2,
                "phone": "555-3000",
                "location": "Staging",
                "notes": "Closest transport",
            }
        ],
        "/api/incidents/MED-1/medical/ics206/hospitals": [
            {
                "id": 3,
                "op_period": 2,
                "name": "Children's Hospital",
                "address": "3 Care Ave",
                "phone": "555-4000",
                "helipad": False,
                "burn_center": False,
                "adult_trauma_level": 0,
                "pediatric_trauma_level": 2,
                "notes": "Pediatric specialty",
            }
        ],
        "/api/incidents/MED-1/medical/ics206/air-ambulance": [
            {
                "id": 4,
                "op_period": 2,
                "name": "Medevac 1",
                "phone": "555-5000",
                "base": "Airport",
                "contact": "Dispatch",
                "notes": "Day ops",
            }
        ],
        "/api/incidents/MED-1/medical/ics206/comms": [
            {
                "id": 5,
                "op_period": 2,
                "channel": "MED TAC",
                "function": "Hospital coordination",
                "frequency": "155.340",
                "mode": "Analog",
                "notes": "Backup route",
            }
        ],
        "/api/incidents/MED-1/medical/ics206/procedures": {
            "id": 6,
            "op_period": 2,
            "content": "Call dispatch before transport.",
        },
        "/api/incidents/MED-1/medical/ics206/signatures": {
            "id": 7,
            "op_period": 2,
            "prepared_by": "Pat Morgan",
            "position": "MEDL",
            "approved_by": "Alex Rivera",
            "date": "2026-06-26 07:50",
        },
    }

    def fake_get(path, params=None, **kwargs):
        return responses[path]

    monkeypatch.setattr("modules.forms_creator.context._get", fake_get)

    context = FormDataContext().build("MED-1")

    assert context["hospitals"][0]["trauma_level_display"] == "A-II / P-I"
    assert context["ems_agencies"][0]["service_level"] == 2
    assert context["ems_agencies"][0]["service_level_label"] == "ALS"
    assert context["ics_206_aid_stations"][0]["is_24_7"] is True
    assert context["ics_206_ambulance_services"][0]["service_level_label"] == "ALS"
    assert context["ics_206_hospitals"][0]["trauma_level_display"] == "P-II"
    assert context["ics_206_air_ambulance"][0]["base"] == "Airport"
    assert context["ics_206_medical_comms"][0]["channel"] == "MED TAC"
    assert context["ics_206_procedures"]["content"] == "Call dispatch before transport."
    assert context["ics_206_signatures"]["position"] == "MEDL"


def test_build_context_exposes_facility_bindings_for_incident_tasks_and_ics215a(monkeypatch):
    responses = {
        "/api/incidents/FAC-1": {
            "id": "FAC-1",
            "name": "River Search",
            "number": "INC-500",
            "type": "Search",
            "description": "River corridor incident",
            "icp_location": "County fairgrounds",
            "icp_facility_id": "fac-icp",
            "start_time": "2026-06-27T08:00:00",
        },
        "/api/incidents/FAC-1/facilities/fac-icp": {
            "id": "fac-icp",
            "name": "County Fairgrounds ICP",
        },
        "/api/incidents/FAC-1/operational-periods": [],
        "/api/incidents/FAC-1/org/assignments": [],
        "/api/incidents/FAC-1/comms/channels": [],
        "/api/incidents/FAC-1/teams": [],
        "/api/incidents/FAC-1/tasks": [
            {
                "id": "task-1",
                "task_id": "T-1",
                "title": "Set up staging",
                "location": "North lot",
                "location_facility_id": "fac-staging",
                "created_at": "2026-06-27T09:15:00",
            }
        ],
        "/api/objectives": [],
        "/api/incidents/FAC-1/resources": [],
        "/api/incidents/FAC-1/ics214/streams": [],
        "/api/incidents/FAC-1/meetings": [],
        "/api/incidents/FAC-1/snapshot": {"collections": {"hazards": [], "cap_orm_summaries": [], "cap_orm_audit": []}},
        "/api/incidents/FAC-1/safety/reports": [],
        "/api/incidents/FAC-1/safety/zones": [],
        "/api/incidents/FAC-1/safety/iwi": [],
        "/api/hazard-types": [],
        "/api/master/safety-templates": [],
        "/api/master/aircraft": [],
        "/api/master/personnel": [],
        "/api/master/vehicles": [],
        "/api/master/equipment": [],
        "/api/comms/channels": [],
        "/api/resource-types": [],
        "/api/incidents/FAC-1/comms-log": [],
        "/api/incidents/FAC-1/planning/work-assignments": [
            {
                "id": "wa-1",
                "assignment_number": "WA-1",
                "assignment_name": "North Perimeter",
                "branch": "Operations",
                "division_group": "Division N",
                "location": "North lot",
                "location_facility_id": "fac-staging",
                "hazards": [
                    {
                        "id": "hz-1",
                        "hazard_type_text": "Traffic",
                    }
                ],
            }
        ],
        "/api/incidents/FAC-1/weather": {},
        "/api/incidents/FAC-1/liaison/agencies": [],
        "/api/incidents/FAC-1/liaison/interactions": [],
        "/api/incidents/FAC-1/liaison/feedback": [],
        "/api/incidents/FAC-1/liaison/agency-requests": [],
        "/api/incidents/FAC-1/liaison/resource-offers": [],
        "/api/incidents/FAC-1/facilities": [
            {
                "id": "fac-icp",
                "incident_id": "FAC-1",
                "name": "County Fairgrounds ICP",
                "facility_type": "command_post",
                "status": "active",
                "address": "123 Main St",
                "geocoded_address": "123 Main St, Albany, NY",
                "latitude": 42.6526,
                "longitude": -73.7562,
                "is_primary": True,
            },
            {
                "id": "fac-staging",
                "incident_id": "FAC-1",
                "name": "North Lot Staging",
                "facility_type": "staging",
                "status": "active",
                "address": "456 North Rd",
                "geocoded_address": "456 North Rd, Albany, NY",
                "latitude": 42.66,
                "longitude": -73.75,
                "manager_name": "Taylor",
                "is_primary": False,
            },
        ],
    }

    def fake_get(path, params=None, **kwargs):
        return responses[path]

    monkeypatch.setattr("modules.forms_creator.context._get", fake_get)

    context = FormDataContext().build("FAC-1")

    assert context["incident"]["icp_facility_id"] == "fac-icp"
    assert context["incident"]["icp_facility_name"] == "County Fairgrounds ICP"
    assert context["tasks"][0]["location_facility_id"] == "fac-staging"
    assert context["ics_215a_rows"][0]["location_facility_id"] == "fac-staging"
    assert context["facilities"][0]["facility_type"] == "command_post"
    assert context["facilities"][1]["manager_name"] == "Taylor"


def test_build_medical_context_exposes_aid_station_facility_fields(monkeypatch):
    responses = {
        "/api/incidents/MED-FAC-1": {},
        "/api/incidents/MED-FAC-1/operational-periods": [
            {
                "op_number": 1,
                "start_time": "2026-06-27T08:00:00",
                "end_time": "2026-06-27T20:00:00",
            }
        ],
        "/api/incidents/MED-FAC-1/org/positions": [],
        "/api/incidents/MED-FAC-1/org/assignments": [],
        "/api/incidents/MED-FAC-1/comms/channels": [],
        "/api/incidents/MED-FAC-1/teams": [],
        "/api/incidents/MED-FAC-1/tasks": [],
        "/api/objectives": [],
        "/api/incidents/MED-FAC-1/resources": [],
        "/api/incidents/MED-FAC-1/ics214/streams": [],
        "/api/incidents/MED-FAC-1/meetings": [],
        "/api/incidents/MED-FAC-1/snapshot": {"collections": {"hazards": [], "cap_orm_summaries": [], "cap_orm_audit": []}},
        "/api/incidents/MED-FAC-1/safety/reports": [],
        "/api/incidents/MED-FAC-1/safety/zones": [],
        "/api/incidents/MED-FAC-1/safety/iwi": [],
        "/api/hazard-types": [],
        "/api/master/safety-templates": [],
        "/api/master/aircraft": [],
        "/api/master/personnel": [],
        "/api/master/vehicles": [],
        "/api/master/equipment": [],
        "/api/master/hospitals": [],
        "/api/master/ems-agencies": [],
        "/api/comms/channels": [],
        "/api/resource-types": [],
        "/api/incidents/MED-FAC-1/comms-log": [],
        "/api/incidents/MED-FAC-1/medical/ics206/aid-stations": [
            {
                "id": 1,
                "op_period": 1,
                "name": "Base Aid",
                "type": "Medical Aid",
                "level": "ALS",
                "facility_id": "fac-aid",
                "location_text": "Base camp, east side",
                "latitude": 39.123,
                "longitude": -84.456,
                "is_24_7": True,
                "notes": "Main camp",
            }
        ],
        "/api/incidents/MED-FAC-1/medical/ics206/ambulance-services": [],
        "/api/incidents/MED-FAC-1/medical/ics206/hospitals": [],
        "/api/incidents/MED-FAC-1/medical/ics206/air-ambulance": [],
        "/api/incidents/MED-FAC-1/weather": {},
        "/api/incidents/MED-FAC-1/liaison/agencies": [],
        "/api/incidents/MED-FAC-1/liaison/interactions": [],
        "/api/incidents/MED-FAC-1/liaison/feedback": [],
        "/api/incidents/MED-FAC-1/liaison/agency-requests": [],
        "/api/incidents/MED-FAC-1/liaison/resource-offers": [],
    }

    def fake_get(path, params=None, **kwargs):
        return responses[path]

    monkeypatch.setattr("modules.forms_creator.context._get", fake_get)

    context = FormDataContext().build("MED-FAC-1")

    assert context["ics_206_aid_stations"][0]["facility_id"] == "fac-aid"
    assert context["ics_206_aid_stations"][0]["location_text"] == "Base camp, east side"
    assert context["ics_206_aid_stations"][0]["latitude"] == 39.123
    assert context["ics_206_aid_stations"][0]["longitude"] == -84.456
