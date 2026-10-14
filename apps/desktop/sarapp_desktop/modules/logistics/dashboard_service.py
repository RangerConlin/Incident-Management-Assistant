"""Data aggregation for the Logistics Dashboard."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules.logistics.resource_status.models import CLOSED_STATUSES, parse_datetime

OPEN_REQUEST_STATUSES = {"DRAFT", "SUBMITTED", "REVIEWED", "APPROVED", "ASSIGNED", "INTRANSIT", "PARTIAL"}
APPROVAL_REQUEST_STATUSES = {"SUBMITTED", "REVIEWED"}
READY_STATUSES = {"Available", "Checked In"}
VEHICLE_ACTIVE_STATUSES = {"Pending", "Enroute", "Staged", "Checked In", "Assigned", "Available", "Out of Service"}
DEMOB_STATUSES = {"Preparing for Demobilization"}


def _client():
    from utils.api_client import api_client

    return api_client


def _get(path: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        rows = _client().get(path, params=params or {}) or []
    except Exception:
        return []
    return rows if isinstance(rows, list) else []


def build_dashboard_payload(incident_id: str) -> dict[str, Any]:
    """Return the widget payload for the current incident's Logistics Dashboard."""

    requests = _get(f"/api/incidents/{incident_id}/logistics/resource-requests")
    resources = _get(f"/api/incidents/{incident_id}/resource-status")
    facilities = _get(f"/api/incidents/{incident_id}/facilities")

    open_requests = [row for row in requests if str(row.get("status") or "").upper() in OPEN_REQUEST_STATUSES]
    approvals_pending = [
        row for row in requests if str(row.get("status") or "").upper() in APPROVAL_REQUEST_STATUSES
    ]
    personnel = [row for row in resources if row.get("entity_type") == "personnel"]
    vehicles = [row for row in resources if row.get("entity_type") == "vehicle"]
    active_vehicles = [row for row in vehicles if row.get("status") in VEHICLE_ACTIVE_STATUSES]
    ready_vehicles = [row for row in vehicles if row.get("status") in READY_STATUSES]
    assigned_vehicles = [row for row in vehicles if row.get("status") == "Assigned"]
    oos_vehicles = [row for row in vehicles if row.get("status") == "Out of Service"]

    active_facilities = [row for row in facilities if str(row.get("status") or "").lower() == "active"]
    open_facilities = [
        row for row in facilities if str(row.get("status") or "").lower() in {"active", "open"}
    ]
    demob_items = [row for row in resources if row.get("status") in DEMOB_STATUSES]

    payload = {
        "kpis": {
            "open_requests": len(open_requests),
            "approvals_pending": len(approvals_pending),
            "low_stock_alerts": 0,
            "checkins_today": _count_checkins_today(personnel),
            "vehicles_ready": f"{len(ready_vehicles)}/{len(active_vehicles)}",
            "facilities_ok": f"{len(active_facilities)}/{len(facilities)}",
        },
        "alerts": _build_alerts(open_requests, resources),
        "actions": _build_actions(open_requests),
        "resource_snapshot": {
            "checkins_total": len([row for row in personnel if row.get("status") not in CLOSED_STATUSES]),
            "equip_218_missing_serials": 0,
            "vehicles_ready": len(ready_vehicles),
            "vehicles_assigned": len(assigned_vehicles),
            "vehicles_oos": len(oos_vehicles),
            "facilities_status": f"{len(open_facilities)}/{len(facilities)}",
        },
        "supply_comms": {
            "ppe": "No data",
            "medical": "No data",
            "water": "No data",
            "fuel": "No data",
            "comms_cache": "No data",
            "spare_radios": "No data",
        },
        "demob_queue": _build_demob_queue(demob_items),
    }
    return payload


def _count_checkins_today(personnel: list[dict[str, Any]]) -> int:
    today = datetime.now().astimezone().date()
    count = 0
    for row in personnel:
        value = row.get("checked_in_time") or row.get("created_at") or row.get("updated_at")
        parsed = parse_datetime(value)
        if parsed and parsed.astimezone().date() == today:
            count += 1
    return count


def _build_alerts(requests: list[dict[str, Any]], resources: list[dict[str, Any]]) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    now = datetime.now(timezone.utc)
    for row in resources:
        status = str(row.get("status") or "")
        eta = parse_datetime(row.get("eta_utc"))
        if status in {"Pending", "Enroute"} and eta and eta < now:
            alerts.append(
                {
                    "id": str(row.get("id") or row.get("_id") or row.get("record_id") or len(alerts)),
                    "severity": "low",
                    "ts": _short_time(row.get("updated_at") or row.get("eta_utc")),
                    "text": f"{row.get('resource_name') or 'Resource'} is overdue for arrival.",
                }
            )
    for row in requests[:4]:
        status = str(row.get("status") or "").upper()
        if status in APPROVAL_REQUEST_STATUSES:
            alerts.append(
                {
                    "id": str(row.get("id") or len(alerts)),
                    "severity": "info",
                    "ts": _short_time(row.get("last_updated_utc") or row.get("created_utc")),
                    "text": f"{row.get('title') or 'Resource request'} is waiting on review or approval.",
                }
            )
    return alerts[:8]


def _build_actions(requests: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for row in requests[:6]:
        status = str(row.get("status") or "").upper()
        priority = str(row.get("priority") or "Routine").title()
        kind = "approve" if status in APPROVAL_REQUEST_STATUSES else "assign"
        actions.append(
            {
                "id": str(row.get("id") or ""),
                "priority": priority,
                "title": str(row.get("title") or "Resource request"),
                "subtitle": f"{status.title()} | {row.get('requesting_section') or 'Unknown section'}",
                "kind": kind,
            }
        )
    return actions


def _build_demob_queue(resources: list[dict[str, Any]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for row in resources[:8]:
        items.append(
            {
                "id": str(row.get("id") or row.get("_id") or row.get("record_id") or ""),
                "title": str(row.get("resource_name") or row.get("resource_id") or "Resource"),
                "due": str(row.get("updated_at") or row.get("notes") or "Preparing for demobilization"),
            }
        )
    return items


def _short_time(value: Any) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        return ""
    return parsed.astimezone().strftime("%H:%M")


__all__ = ["build_dashboard_payload"]
