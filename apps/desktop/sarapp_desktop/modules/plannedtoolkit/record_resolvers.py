"""Phase 1D: read-only lookups into the systems an Event Schedule activity
can link to (Meeting Planner, Personnel, Teams, GIS).

The Event Schedule never owns or duplicates this data -- every function
here is a thin, failure-tolerant read through the existing API/service each
system already exposes. Every function returns ``None`` (not an exception)
for a missing/deleted/unreachable record, so callers can display "not
found" instead of crashing -- the brief's "handle deleted or unavailable
records gracefully" requirement.
"""
from __future__ import annotations

from typing import Any

from utils.api_client import api_client


def resolve_personnel_name(person_id: str) -> str | None:
    if not person_id:
        return None
    try:
        record_id = int(person_id)
    except (TypeError, ValueError):
        return None
    try:
        doc = api_client.get(f"/api/master/personnel/{record_id}")
    except Exception:
        return None
    if not doc:
        return None
    return str(doc.get("name") or "") or None


def resolve_team(incident_id: str, team_id: str) -> dict[str, Any] | None:
    if not incident_id or not team_id:
        return None
    try:
        team_record_id = int(team_id)
    except (TypeError, ValueError):
        return None
    try:
        doc = api_client.get(f"/api/incidents/{incident_id}/operations/teams/{team_record_id}")
    except Exception:
        return None
    return doc or None


def list_teams(incident_id: str) -> list[dict[str, Any]]:
    if not incident_id:
        return []
    try:
        return api_client.get(f"/api/incidents/{incident_id}/operations/teams") or []
    except Exception:
        return []


def resolve_meeting(incident_id: str, meeting_id: str) -> dict[str, Any] | None:
    if not incident_id or not meeting_id:
        return None
    try:
        meeting_record_id = int(meeting_id)
    except (TypeError, ValueError):
        return None
    try:
        doc = api_client.get(f"/api/incidents/{incident_id}/planning/meetings/{meeting_record_id}")
    except Exception:
        return None
    return doc or None


def list_meetings(incident_id: str) -> list[dict[str, Any]]:
    if not incident_id:
        return []
    try:
        return api_client.get(f"/api/incidents/{incident_id}/planning/meetings") or []
    except Exception:
        return []


def resolve_gis_feature(incident_id: str, feature_id: str) -> dict[str, Any] | None:
    if not incident_id or not feature_id:
        return None
    try:
        feature_record_id = int(feature_id)
    except (TypeError, ValueError):
        return None
    try:
        doc = api_client.get(f"/api/incidents/{incident_id}/gis/features/{feature_record_id}")
    except Exception:
        return None
    return doc or None


def list_gis_features(incident_id: str) -> list[dict[str, Any]]:
    if not incident_id:
        return []
    try:
        return api_client.get(f"/api/incidents/{incident_id}/gis/features") or []
    except Exception:
        return []
