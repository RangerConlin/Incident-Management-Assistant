from __future__ import annotations

from modules.plannedtoolkit.repository import PlannedToolkitRepository


class FakeApiClient:
    def __init__(self):
        self.records = []
        self.calls = []

    def get(self, path, *, params=None):
        self.calls.append(("get", path, params))
        return list(self.records)

    def post(self, path, *, json=None):
        self.calls.append(("post", path, json))
        row = dict(json or {})
        row.update(
            {
                "id": len(self.records) + 1,
                "record_id": f"DEV-PLAN-TASK-{len(self.records) + 1}",
                "incident_id": "DEV",
                "tool": path.rsplit("/", 1)[-1],
                "created_at": "now",
                "updated_at": "now",
            }
        )
        self.records.append(row)
        return row

    def patch(self, path, *, json=None, params=None):
        self.calls.append(("patch", path, json))
        row = self.records[0]
        row.update(json or {})
        return row

    def delete(self, path, *, params=None):
        self.calls.append(("delete", path, params))
        return None


def test_repository_uses_incident_scoped_planned_api(monkeypatch):
    fake = FakeApiClient()
    monkeypatch.setattr("modules.plannedtoolkit.repository._client", lambda: fake)

    repo = PlannedToolkitRepository("DEV")
    created = repo.create_record(
        "tasks",
        title="Stage barricades",
        summary="North gate setup",
        priority="High",
        assigned_to="Logistics",
        location="North Gate",
    )

    assert created.id == 1
    assert created.title == "Stage barricades"
    assert fake.calls[0][0] == "post"
    assert fake.calls[0][1] == "/api/incidents/DEV/planned/tasks"
    assert fake.calls[0][2]["priority"] == "High"

    rows = repo.list_records("tasks", search="gate")
    assert rows[0].location == "North Gate"
    assert fake.calls[1] == ("get", "/api/incidents/DEV/planned/tasks", {"search": "gate"})

    updated = repo.update_record("tasks", 1, {"status": "Completed"})
    assert updated.status == "Completed"
    assert fake.calls[2][1] == "/api/incidents/DEV/planned/tasks/1"

    repo.delete_record("tasks", 1)
    assert fake.calls[3][0] == "delete"
