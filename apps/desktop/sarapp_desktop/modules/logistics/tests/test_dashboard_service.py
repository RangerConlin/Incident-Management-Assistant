from __future__ import annotations

from modules.logistics import dashboard_service


class _FakeClient:
    def get(self, path, params=None):
        if path.endswith("/logistics/resource-requests"):
            return [
                {
                    "id": "REQ-1",
                    "title": "Radios",
                    "status": "SUBMITTED",
                    "priority": "HIGH",
                    "requesting_section": "Operations",
                    "created_utc": "2026-10-13T12:00:00+00:00",
                }
            ]
        if path.endswith("/resource-status"):
            return [
                {
                    "id": "RS-1",
                    "entity_type": "personnel",
                    "resource_name": "Alex Rivera",
                    "status": "Available",
                    "checked_in_time": "2026-10-13T12:00:00+00:00",
                },
                {
                    "id": "RS-2",
                    "entity_type": "vehicle",
                    "resource_name": "Truck 4",
                    "status": "Available",
                },
                {
                    "id": "RS-3",
                    "entity_type": "personnel",
                    "resource_name": "Morgan Lee",
                    "status": "Preparing for Demobilization",
                },
            ]
        if path.endswith("/facilities"):
            return [{"id": "fac-1", "status": "active"}, {"id": "fac-2", "status": "closed"}]
        return []


def test_dashboard_payload_aggregates_existing_logistics_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(dashboard_service, "_client", lambda: _FakeClient())

    payload = dashboard_service.build_dashboard_payload("incident-1")

    assert payload["kpis"]["open_requests"] == 1
    assert payload["kpis"]["approvals_pending"] == 1
    assert payload["kpis"]["vehicles_ready"] == "1/1"
    assert payload["kpis"]["facilities_ok"] == "1/2"
    assert payload["actions"][0]["id"] == "REQ-1"
    assert payload["demob_queue"][0]["title"] == "Morgan Lee"
