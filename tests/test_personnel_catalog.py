from models.master_catalog import make_service


def test_personnel_service_lists_records():
    svc = make_service("data/master.db", "personnel")
    rows = svc.list()
    assert len(rows) == 2
    assert {
        "id",
        "name",
        "callsign",
        "role",
        "phone",
        "email",
    }.issubset(rows[0].keys())
