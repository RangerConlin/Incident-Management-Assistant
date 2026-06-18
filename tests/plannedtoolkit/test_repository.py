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
        if path.endswith("/promote"):
            row = self.records[0]
            row.update(
                {
                    "linked_tasking_id": "DEV-TASK-1",
                    "promoted_at": "now",
                    "promoted_by": (json or {}).get("promoted_by", ""),
                    "promoted_read_only": True,
                    "lifecycle_state": "Promoted",
                }
            )
            return row
        row = dict(json or {})
        row.update(
            {
                "id": len(self.records) + 1,
                "record_id": f"DEV-PLAN-TASK-{len(self.records) + 1}",
                "trigger_id": f"DEV-PLAN-TRIGGER-{len(self.records) + 1}",
                "notification_id": f"DEV-PLAN-NOTIFY-{len(self.records) + 1}",
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


def test_repository_supports_quick_assignment_contract(monkeypatch):
    fake = FakeApiClient()
    monkeypatch.setattr("modules.plannedtoolkit.repository._client", lambda: fake)

    repo = PlannedToolkitRepository("DEV")
    created = repo.create_record(
        "quick-assignments",
        title="Restroom check",
        zone="Zone B",
        recurring=True,
        recurrence_rule="every 30 minutes",
        source_type="schedule_trigger",
        source_id="trigger-1",
    )

    assert created.tool == "quick-assignments"
    assert created.zone == "Zone B"
    assert created.recurring is True
    assert created.recurrence_rule == "every 30 minutes"
    assert created.source_type == "schedule_trigger"
    assert fake.calls[0][1] == "/api/incidents/DEV/planned/quick-assignments"


def test_repository_supports_schedule_triggers_and_notifications(monkeypatch):
    fake = FakeApiClient()
    monkeypatch.setattr("modules.plannedtoolkit.repository._client", lambda: fake)

    repo = PlannedToolkitRepository("DEV")
    trigger = repo.create_schedule_trigger(
        schedule_item_id="DEV-PLAN-SCHEDULE-1",
        trigger_type="notification",
        label="Road closure reminder",
        message_template="Road closure starts in 15 minutes",
    )
    notification = repo.create_notification(
        title="Road closure",
        message="Road closure starts in 15 minutes",
        source_type="schedule_trigger",
        source_id=trigger.trigger_id,
    )
    repo.acknowledge_notification(1, acknowledged_by="ops")

    assert trigger.label == "Road closure reminder"
    assert notification.title == "Road closure"
    assert fake.calls[0][1] == "/api/incidents/DEV/planned-meta/schedule-triggers"
    assert fake.calls[1][1] == "/api/incidents/DEV/planned-meta/notifications"
    assert fake.calls[2][1] == "/api/incidents/DEV/planned-meta/notifications/1/acknowledge"


def test_repository_promotes_quick_assignment(monkeypatch):
    fake = FakeApiClient()
    monkeypatch.setattr("modules.plannedtoolkit.repository._client", lambda: fake)

    repo = PlannedToolkitRepository("DEV")
    repo.create_record("quick-assignments", title="Gate sweep")
    promoted = repo.promote_quick_assignment(1, promoted_by="lead")

    assert fake.calls[1][0] == "post"
    assert fake.calls[1][1] == "/api/incidents/DEV/planned/quick-assignments/1/promote"
    assert fake.calls[1][2] == {"promoted_by": "lead"}
    assert promoted.title == "Gate sweep"
