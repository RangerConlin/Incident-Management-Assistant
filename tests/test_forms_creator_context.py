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

