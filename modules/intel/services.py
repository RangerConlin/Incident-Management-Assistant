"""Intel service functions — CRUD via SARApp API (MongoDB-backed)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from utils import incident_context

from .models import Clue, Subject, EnvSnapshot, IntelReport, FormEntry


def _client():
    from utils.api_client import api_client
    return api_client


def _incident_id() -> str:
    iid = incident_context.get_active_incident_id()
    if not iid:
        raise RuntimeError("Active incident is not set")
    return iid


def _base(iid: str) -> str:
    return f"/api/incidents/{iid}/intel"


def _dt_str(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat(timespec="seconds")
    return str(dt)


def _parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Clues
# ---------------------------------------------------------------------------

def _clue_from_dict(d: dict) -> Clue:
    return Clue(
        id=d.get("id"),
        type=d.get("type", ""),
        score=d.get("score", 0),
        at_time=_parse_dt(d.get("at_time")) or datetime.utcnow(),
        location_text=d.get("location_text", ""),
        entered_by=d.get("entered_by", ""),
        geom=d.get("geom"),
        team_text=d.get("team_text"),
        description=d.get("description"),
        attachments_json=d.get("attachments_json"),
        linked_subject_id=d.get("linked_subject_id"),
        linked_task_id=d.get("linked_task_id"),
        created_at=_parse_dt(d.get("created_at")),
        updated_at=_parse_dt(d.get("updated_at")),
    )


def _clue_payload(c: Clue) -> dict:
    return {
        "type": c.type,
        "score": c.score,
        "at_time": _dt_str(c.at_time),
        "location_text": c.location_text,
        "entered_by": c.entered_by,
        "geom": c.geom,
        "team_text": c.team_text,
        "description": c.description,
        "attachments_json": c.attachments_json,
        "linked_subject_id": c.linked_subject_id,
        "linked_task_id": c.linked_task_id,
    }


def list_clues(incident_id: str | None = None) -> List[Clue]:
    iid = incident_id or _incident_id()
    rows = _client().get(f"{_base(iid)}/clues")
    return [_clue_from_dict(r) for r in rows]


def add_clue(clue: Clue, incident_id: str | None = None) -> Clue:
    iid = incident_id or _incident_id()
    result = _client().post(f"{_base(iid)}/clues", json=_clue_payload(clue))
    return _clue_from_dict(result)


def get_clue(clue_id: int, incident_id: str | None = None) -> Optional[Clue]:
    iid = incident_id or _incident_id()
    try:
        return _clue_from_dict(_client().get(f"{_base(iid)}/clues/{clue_id}"))
    except Exception:
        return None


def update_clue(clue: Clue, incident_id: str | None = None) -> Clue:
    iid = incident_id or _incident_id()
    result = _client().put(f"{_base(iid)}/clues/{clue.id}", json=_clue_payload(clue))
    return _clue_from_dict(result)


def save_clue(clue: Clue, incident_id: str | None = None) -> Clue:
    if clue.id is not None:
        return update_clue(clue, incident_id)
    return add_clue(clue, incident_id)


def delete_clue(clue_id: int, incident_id: str | None = None) -> None:
    iid = incident_id or _incident_id()
    _client().delete(f"{_base(iid)}/clues/{clue_id}")


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------

def _subject_from_dict(d: dict) -> Subject:
    return Subject(
        id=d.get("id"),
        name=d.get("name", ""),
        sex=d.get("sex"),
        dob=d.get("dob"),
        race=d.get("race"),
        photo=d.get("photo"),
        lkp_time=_parse_dt(d.get("lkp_time")),
        lkp_place=d.get("lkp_place"),
    )


def _subject_payload(s: Subject) -> dict:
    return {
        "name": s.name,
        "sex": s.sex,
        "dob": s.dob,
        "race": s.race,
        "photo": s.photo,
        "lkp_time": _dt_str(s.lkp_time) if s.lkp_time else None,
        "lkp_place": s.lkp_place,
    }


def list_subjects(incident_id: str | None = None) -> List[Subject]:
    iid = incident_id or _incident_id()
    rows = _client().get(f"{_base(iid)}/subjects")
    return [_subject_from_dict(r) for r in rows]


def add_subject(subject: Subject, incident_id: str | None = None) -> Subject:
    iid = incident_id or _incident_id()
    result = _client().post(f"{_base(iid)}/subjects", json=_subject_payload(subject))
    return _subject_from_dict(result)


def get_subject(subject_id: int, incident_id: str | None = None) -> Optional[Subject]:
    iid = incident_id or _incident_id()
    try:
        return _subject_from_dict(_client().get(f"{_base(iid)}/subjects/{subject_id}"))
    except Exception:
        return None


def update_subject(subject: Subject, incident_id: str | None = None) -> Subject:
    iid = incident_id or _incident_id()
    result = _client().put(f"{_base(iid)}/subjects/{subject.id}", json=_subject_payload(subject))
    return _subject_from_dict(result)


def save_subject(subject: Subject, incident_id: str | None = None) -> Subject:
    if subject.id is not None:
        return update_subject(subject, incident_id)
    return add_subject(subject, incident_id)


def delete_subject(subject_id: int, incident_id: str | None = None) -> None:
    iid = incident_id or _incident_id()
    _client().delete(f"{_base(iid)}/subjects/{subject_id}")


# ---------------------------------------------------------------------------
# Env Snapshots
# ---------------------------------------------------------------------------

def _env_from_dict(d: dict) -> EnvSnapshot:
    return EnvSnapshot(
        id=d.get("id"),
        op_period=d.get("op_period", 0),
        weather_json=d.get("weather_json"),
        hazards_json=d.get("hazards_json"),
        terrain_json=d.get("terrain_json"),
        notes=d.get("notes"),
    )


def _env_payload(s: EnvSnapshot) -> dict:
    return {
        "op_period": s.op_period,
        "weather_json": s.weather_json,
        "hazards_json": s.hazards_json,
        "terrain_json": s.terrain_json,
        "notes": s.notes,
    }


def list_env_snapshots(incident_id: str | None = None) -> List[EnvSnapshot]:
    iid = incident_id or _incident_id()
    rows = _client().get(f"{_base(iid)}/env-snapshots")
    return [_env_from_dict(r) for r in rows]


def add_env_snapshot(snap: EnvSnapshot, incident_id: str | None = None) -> EnvSnapshot:
    iid = incident_id or _incident_id()
    result = _client().post(f"{_base(iid)}/env-snapshots", json=_env_payload(snap))
    return _env_from_dict(result)


def get_env_snapshot(snap_id: int, incident_id: str | None = None) -> Optional[EnvSnapshot]:
    iid = incident_id or _incident_id()
    try:
        return _env_from_dict(_client().get(f"{_base(iid)}/env-snapshots/{snap_id}"))
    except Exception:
        return None


def update_env_snapshot(snap: EnvSnapshot, incident_id: str | None = None) -> EnvSnapshot:
    iid = incident_id or _incident_id()
    result = _client().put(f"{_base(iid)}/env-snapshots/{snap.id}", json=_env_payload(snap))
    return _env_from_dict(result)


def save_env_snapshot(snap: EnvSnapshot, incident_id: str | None = None) -> EnvSnapshot:
    if snap.id is not None:
        return update_env_snapshot(snap, incident_id)
    return add_env_snapshot(snap, incident_id)


def delete_env_snapshot(snap_id: int, incident_id: str | None = None) -> None:
    iid = incident_id or _incident_id()
    _client().delete(f"{_base(iid)}/env-snapshots/{snap_id}")


# ---------------------------------------------------------------------------
# Intel Reports
# ---------------------------------------------------------------------------

def _report_from_dict(d: dict) -> IntelReport:
    return IntelReport(
        id=d.get("id"),
        title=d.get("title", ""),
        body_md=d.get("body_md", ""),
        linked_subject_id=d.get("linked_subject_id"),
        linked_task_id=d.get("linked_task_id"),
        created_at=_parse_dt(d.get("created_at")),
    )


def _report_payload(r: IntelReport) -> dict:
    return {
        "title": r.title,
        "body_md": r.body_md,
        "linked_subject_id": r.linked_subject_id,
        "linked_task_id": r.linked_task_id,
    }


def list_reports(incident_id: str | None = None) -> List[IntelReport]:
    iid = incident_id or _incident_id()
    rows = _client().get(f"{_base(iid)}/reports")
    return [_report_from_dict(r) for r in rows]


def add_report(report: IntelReport, incident_id: str | None = None) -> IntelReport:
    iid = incident_id or _incident_id()
    result = _client().post(f"{_base(iid)}/reports", json=_report_payload(report))
    return _report_from_dict(result)


def get_report(report_id: int, incident_id: str | None = None) -> Optional[IntelReport]:
    iid = incident_id or _incident_id()
    try:
        return _report_from_dict(_client().get(f"{_base(iid)}/reports/{report_id}"))
    except Exception:
        return None


def update_report(report: IntelReport, incident_id: str | None = None) -> IntelReport:
    iid = incident_id or _incident_id()
    result = _client().put(f"{_base(iid)}/reports/{report.id}", json=_report_payload(report))
    return _report_from_dict(result)


def save_report(report: IntelReport, incident_id: str | None = None) -> IntelReport:
    if report.id is not None:
        return update_report(report, incident_id)
    return add_report(report, incident_id)


# ---------------------------------------------------------------------------
# Form Entries
# ---------------------------------------------------------------------------

def _form_entry_from_dict(d: dict) -> FormEntry:
    return FormEntry(
        id=d.get("id"),
        form_name=d.get("form_name", ""),
        data_json=d.get("data_json", ""),
    )


def list_form_entries(incident_id: str | None = None) -> List[FormEntry]:
    iid = incident_id or _incident_id()
    rows = _client().get(f"{_base(iid)}/form-entries")
    return [_form_entry_from_dict(r) for r in rows]


def add_form_entry(entry: FormEntry, incident_id: str | None = None) -> FormEntry:
    iid = incident_id or _incident_id()
    result = _client().post(f"{_base(iid)}/form-entries", json={"form_name": entry.form_name, "data_json": entry.data_json})
    return _form_entry_from_dict(result)


def get_form_entry(entry_id: int, incident_id: str | None = None) -> Optional[FormEntry]:
    iid = incident_id or _incident_id()
    try:
        return _form_entry_from_dict(_client().get(f"{_base(iid)}/form-entries/{entry_id}"))
    except Exception:
        return None
