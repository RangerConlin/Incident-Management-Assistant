"""Read-only export snapshots. No UI state, SQLite, or runtime ID repair."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from sarapp_db.mongo.collection_names import IncidentCollections as C
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

from .models import ExportError, ExportRequest, ExportSnapshot, FormDefinition

class ExportReadRepository(BaseRepository):
    soft_deletes = False
    def __init__(self, db: Any, collection: str):
        self.collection_name = collection
        super().__init__(db)

def load_snapshot(request: ExportRequest, definition: FormDefinition) -> ExportSnapshot:
    incident_id, form_id = request.incident_id, request.form_id
    source_id, period_id = request.source_id, request.operational_period_id
    selected_set = definition.template(request.form_set_id).form_set_id
    db = get_incident_db(incident_id)
    def repo(collection: str) -> ExportReadRepository:
        return ExportReadRepository(db, collection)
    incident = repo(C.INCIDENT_PROFILE).find_one({"incident_id": incident_id, "deleted": {"$ne": True}})
    if not incident:
        raise ExportError(404, "Incident profile not found")
    source = definition.source
    if source == "organization":
        if period_id is None:
            raise ExportError(422, "Select an operational period for ICS 203")
        if source_id is not None:
            raise ExportError(422, "ICS 203 exports the current incident organization, not a source record")
    records: list[dict[str, Any]]
    query: dict[str, Any] = {"deleted": {"$ne": True}}
    if source in {"work_assignment", "resource_request", "sitrep"} and not source_id:
        raise ExportError(422, "Select a saved source record to export this form")
    if source == "organization":
        records = repo(C.INCIDENT_ORG).find_many(query, sort=[("sort_order", 1), ("position_id", 1)])
    elif source == "work_assignment":
        try:
            query["int_id"] = int(source_id or "")
        except ValueError as exc:
            raise ExportError(422, "Work assignment ID must be numeric") from exc
        document = repo(C.WORK_ASSIGNMENTS).find_one(query)
        records = [document] if document else []
    elif source in {"resource_request", "sitrep"}:
        query["id"] = source_id
        document = repo(C.RESOURCE_REQUESTS if source == "resource_request" else C.SITREPS).find_one(query)
        records = [document] if document else []
    elif source == "objectives":
        query["incident_id"] = incident_id
        if source_id:
            query["_id"] = source_id
        else:
            query["status"] = "active"
            if period_id is not None:
                query["op_period_id"] = str(period_id)
        records = repo(C.INCIDENT_OBJECTIVES).find_many(query, sort=[("display_order", 1), ("code", 1)])
    elif source == "meetings":
        if source_id:
            try:
                query["int_id"] = int(source_id)
            except ValueError as exc:
                raise ExportError(422, "Meeting ID must be numeric") from exc
        else:
            query["show_on_ics230"] = True
            if period_id is not None:
                query["operational_period_id"] = str(period_id)
        records = repo(C.MEETINGS).find_many(query, sort=[("meeting_date", 1), ("start_time", 1)])
    elif source == "checkin":
        query["status"] = {"$in": ["Checked In", "Assigned", "Available", "Out of Service", "Preparing for Demobilization"]}
        records = repo(C.RESOURCE_STATUS).find_many(query, sort=[("resource_name", 1)])
    else:
        raise ValueError("This source requires a registered domain builder")
    if source_id and not records:
        raise ExportError(404, "Export source not found in this incident")
    # Use the source's canonical period when one is attached. Never silently choose an active period.
    attached_period = records[0].get("operational_period_id") if len(records) == 1 else None
    if source == "objectives" and len(records) == 1:
        attached_period = records[0].get("op_period_id")
    if period_id is not None and attached_period not in (None, "") and str(period_id) != str(attached_period):
        raise ExportError(422, "The selected period does not match the saved source record")
    selected_period = period_id if period_id is not None else attached_period
    period: dict[str, Any] = {}
    if selected_period not in (None, ""):
        try:
            period_number = int(selected_period)
        except (TypeError, ValueError) as exc:
            raise ExportError(422, "Source operational period is invalid") from exc
        period = repo(C.OPERATIONAL_PERIODS).find_one({"int_id": period_number, "deleted": {"$ne": True}}) or {}
        if not period:
            raise ExportError(404, "Operational period not found in this incident")
    if source == "organization":
        from .organization import load_organization

        records = [load_organization(db, records)]
        if incident.get("icp_facility_id"):
            facility = repo(C.FACILITIES).find_one({
                "_id": incident["icp_facility_id"], "incident_id": incident_id,
                "deleted": {"$ne": True},
            })
            if not facility:
                raise ExportError(404, "Incident command post facility not found")
            incident = {**incident, "icp_location": facility.get("name", "")}
    return ExportSnapshot(
        form_id, incident, period, records, request.prepared_by, selected_set,
        request.prepared_by_position,
    )


def human_time(value: Any, part: str = "datetime") -> str:
    if not value:
        return ""
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    pattern = {
        "date": "%b %d, %Y", "time": "%H:%M:%S",
        "datetime": "%b %d, %Y %H:%M:%S %Z",
        "date_short": "%m/%d/%Y", "time_short": "%H%M %Z",
        "datetime_human": "%m/%d/%y %H:%M %Z",
        "datetime_short": "%m/%d/%Y %H:%M",
    }[part]
    return date.strftime(pattern).strip()
