"""Persistence layer for the communications traffic log."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.communications.models.master_repo import MasterRepository
from utils.state import AppState

from .models import (
    CommsLogAuditEntry,
    CommsLogEntry,
    CommsLogFilterPreset,
    CommsLogQuery,
    DISPOSITION_OPEN,
    localnow_iso,
    utcnow_iso,
)

logger = logging.getLogger(__name__)

from utils import incident_storage

_DATA_DIR = incident_storage.data_root()


def _incident_db_path(incident_id: str) -> Path:
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        meta = incident_storage.infer_incident_metadata(incident_id)
        paths = incident_storage.get_incident_paths(incident_number=meta.get("incident_number") or incident_id, incident_name=meta.get("name") or incident_id, incident_id=meta.get("incident_id") or incident_id)
        incident_storage.ensure_incident_structure(paths, meta)
    return paths.incident_db


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 4000")
    except sqlite3.DatabaseError:
        pass
    return conn


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comms_log (
            id INTEGER PRIMARY KEY,
            ts_utc TEXT,
            ts_local TEXT,
            direction TEXT,
            priority TEXT,
            resource_id INTEGER,
            resource_label TEXT,
            frequency TEXT,
            band TEXT,
            mode TEXT,
            from_unit TEXT,
            to_unit TEXT,
            message TEXT,
            action_taken TEXT,
            follow_up_required INTEGER DEFAULT 0,
            disposition TEXT DEFAULT 'Open',
            operator_user_id TEXT,
            operator_display_name TEXT,
            team_id INTEGER,
            task_id INTEGER,
            vehicle_id INTEGER,
            personnel_id INTEGER,
            attachments TEXT,
            geotag_lat REAL,
            geotag_lon REAL,
            notification_level TEXT,
            is_status_update INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comms_log_audit (
            id INTEGER PRIMARY KEY,
            comms_log_id INTEGER NOT NULL,
            action TEXT,
            changed_by TEXT,
            changed_at TEXT,
            change_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comms_log_filters (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            user_id TEXT NOT NULL,
            filters_json TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    _ensure_columns(
        conn,
        "comms_log",
        {
            "operator_display_name": "TEXT",
            "notification_level": "TEXT",
            "geotag_lat": "REAL",
            "geotag_lon": "REAL",
        },
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_comms_log_ts ON comms_log(ts_utc DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_comms_log_priority ON comms_log(priority)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_comms_log_resource ON comms_log(resource_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_comms_log_task ON comms_log(task_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_comms_log_status ON comms_log(is_status_update)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_comms_log_follow_up ON comms_log(follow_up_required)"
    )
    conn.commit()


def _safe_row_value(row: sqlite3.Row, key: str) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


class CommsLogRepository:
    """Repository managing communications log persistence."""

    def __init__(self, incident_id: Optional[str] = None, master_repo: Optional[MasterRepository] = None):
        incident = incident_id or AppState.get_active_incident()
        if not incident:
            raise RuntimeError("No active incident configured")
        self.incident_id = str(incident)
        self._path = _incident_db_path(self.incident_id)
        self._master_repo = master_repo or MasterRepository()
        with _connect(self._path) as conn:
            _ensure_schema(conn)

    def _apply_resource_metadata(self, entry: CommsLogEntry) -> None:
        if entry.resource_id and not entry.resource_label:
            try:
                channel = self._master_repo.get_channel(int(entry.resource_id))
            except Exception as exc:
                logger.debug("Failed to load comms resource %s: %s", entry.resource_id, exc)
                channel = None
            if channel:
                entry.resource_label = channel.get("display_name") or channel.get("name") or ""
                if not entry.frequency:
                    rx = channel.get("rx_freq")
                    tx = channel.get("tx_freq")
                    if rx and tx and rx != tx:
                        entry.frequency = f"{rx}/{tx}"
                    elif rx:
                        entry.frequency = str(rx)
                    elif tx:
                        entry.frequency = str(tx)
                entry.band = entry.band or str(channel.get("band") or "")
                entry.mode = entry.mode or str(channel.get("mode") or "")
        if not entry.resource_label:
            entry.resource_label = ""

    def _apply_operator(self, entry: CommsLogEntry) -> None:
        if entry.operator_user_id is None:
            user = AppState.get_active_user_id()
            if user is not None:
                entry.operator_user_id = str(user)
        if entry.operator_display_name is None:
            user = AppState.get_active_user_id()
            if user is not None:
                entry.operator_display_name = str(user)

    def add_entry(self, entry: CommsLogEntry) -> CommsLogEntry:
        if not entry.message:
            raise ValueError("Message is required")
        self._apply_resource_metadata(entry)
        self._apply_operator(entry)
        entry.created_at = entry.created_at or utcnow_iso()
        entry.updated_at = entry.updated_at or entry.created_at
        entry.ts_utc = entry.ts_utc or utcnow_iso()
        entry.ts_local = entry.ts_local or localnow_iso()
        payload = entry.to_record()
        columns = ",".join(payload.keys())
        placeholders = ",".join(["?"] * len(payload))
        values = [payload[k] for k in payload.keys()]
        with _connect(self._path) as conn:
            cur = conn.execute(
                f"INSERT INTO comms_log ({columns}) VALUES ({placeholders})",
                values,
            )
            entry_id = cur.lastrowid
            conn.commit()
        entry.id = int(entry_id)
        self._write_audit(entry.id, "create", asdict(entry))
        return self.get_entry(entry.id)

    def get_entry(self, entry_id: int) -> CommsLogEntry:
        with _connect(self._path) as conn:
            row = conn.execute(
                "SELECT * FROM comms_log WHERE id=?",
                (int(entry_id),),
            ).fetchone()
            if not row:
                raise ValueError(f"comms_log entry {entry_id} not found")
            return CommsLogEntry.from_row(dict(row))

    def list_entries(self, query: Optional[CommsLogQuery] = None) -> List[CommsLogEntry]:
        query = query or CommsLogQuery()
        clauses: List[str] = []
        params: List[Any] = []
        if query.start_ts_utc:
            clauses.append("ts_utc >= ?")
            params.append(query.start_ts_utc)
        if query.end_ts_utc:
            clauses.append("ts_utc <= ?")
            params.append(query.end_ts_utc)
        if query.priorities:
            placeholders = ",".join(["?"] * len(query.priorities))
            clauses.append(f"priority IN ({placeholders})")
            params.extend(query.priorities)
        if query.resource_ids:
            placeholders = ",".join(["?"] * len(query.resource_ids))
            clauses.append(f"resource_id IN ({placeholders})")
            params.extend(query.resource_ids)
        if query.resource_labels:
            clauses.append(
                "(" + " OR ".join(["resource_label LIKE ?" for _ in query.resource_labels]) + ")"
            )
            params.extend([f"%{label}%" for label in query.resource_labels])
        if query.unit_like:
            clauses.append("(from_unit LIKE ? OR to_unit LIKE ?)")
            pattern = f"%{query.unit_like}%"
            params.extend([pattern, pattern])
        if query.operator_ids:
            placeholders = ",".join(["?"] * len(query.operator_ids))
            clauses.append(f"operator_user_id IN ({placeholders})")
            params.extend(query.operator_ids)
        if query.dispositions:
            placeholders = ",".join(["?"] * len(query.dispositions))
            clauses.append(f"disposition IN ({placeholders})")
            params.extend(query.dispositions)
        if query.notification_levels:
            placeholders = ",".join(["?"] * len(query.notification_levels))
            clauses.append(f"notification_level IN ({placeholders})")
            params.extend(query.notification_levels)
        if query.has_attachments is True:
            clauses.append("attachments NOT NULL AND attachments NOT LIKE '[]' AND attachments <> ''")
        elif query.has_attachments is False:
            clauses.append("(attachments IS NULL OR attachments = '' OR attachments = '[]')")
        if query.is_status_update is True:
            clauses.append("is_status_update = 1")
        elif query.is_status_update is False:
            clauses.append("is_status_update = 0")
        if query.follow_up_required is True:
            clauses.append("follow_up_required = 1")
        elif query.follow_up_required is False:
            clauses.append("follow_up_required = 0")
        if query.task_ids:
            placeholders = ",".join(["?"] * len(query.task_ids))
            clauses.append(f"task_id IN ({placeholders})")
            params.extend(query.task_ids)
        if query.team_ids:
            placeholders = ",".join(["?"] * len(query.team_ids))
            clauses.append(f"team_id IN ({placeholders})")
            params.extend(query.team_ids)
        if query.vehicle_ids:
            placeholders = ",".join(["?"] * len(query.vehicle_ids))
            clauses.append(f"vehicle_id IN ({placeholders})")
            params.extend(query.vehicle_ids)
        if query.personnel_ids:
            placeholders = ",".join(["?"] * len(query.personnel_ids))
            clauses.append(f"personnel_id IN ({placeholders})")
            params.extend(query.personnel_ids)
        if query.text_search:
            pattern = f"%{query.text_search.lower()}%"
            clauses.append(
                "(" +
                " OR ".join([
                    "LOWER(message) LIKE ?",
                    "LOWER(action_taken) LIKE ?",
                    "LOWER(from_unit) LIKE ?",
                    "LOWER(to_unit) LIKE ?",
                ]) +
                ")"
            )
            params.extend([pattern, pattern, pattern, pattern])

        where_clause = ""
        if clauses:
            where_clause = " WHERE " + " AND ".join(clauses)
        order_column = query.order_by if query.order_by in {
            "ts_utc",
            "ts_local",
            "priority",
            "resource_label",
            "created_at",
        } else "ts_utc"
        direction = "DESC" if query.order_desc else "ASC"
        limit_clause = ""
        if query.limit is not None:
            limit_clause = " LIMIT ?"
            params.append(int(query.limit))
            if query.offset:
                limit_clause += " OFFSET ?"
                params.append(int(query.offset))
        elif query.offset:
            # Offset without limit defaults to 1000 rows
            limit_clause = " LIMIT 1000 OFFSET ?"
            params.append(int(query.offset))
        sql = f"SELECT * FROM comms_log{where_clause} ORDER BY {order_column} {direction}{limit_clause}"
        with _connect(self._path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [CommsLogEntry.from_row(dict(row)) for row in rows]

    def _normalize_patch(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in patch.items():
            if key == "attachments":
                normalized[key] = json.dumps(value or [], ensure_ascii=False)
            elif key in {"follow_up_required", "is_status_update"}:
                normalized[key] = 1 if bool(value) else 0
            else:
                normalized[key] = value
        normalized["updated_at"] = utcnow_iso()
        return normalized

    def update_entry(self, entry_id: int, patch: Dict[str, Any]) -> CommsLogEntry:
        current = self.get_entry(entry_id)
        normalized = self._normalize_patch(patch)
        if not normalized:
            return current
        assignments = ",".join([f"{k}=?" for k in normalized.keys()])
        values = list(normalized.values()) + [int(entry_id)]
        with _connect(self._path) as conn:
            conn.execute(
                f"UPDATE comms_log SET {assignments} WHERE id=?",
                values,
            )
            conn.commit()
        updated = self.get_entry(entry_id)
        diff = self._diff_entries(current, updated)
        if diff:
            self._write_audit(entry_id, "update", diff)
        return updated

    def delete_entry(self, entry_id: int) -> None:
        current = self.get_entry(entry_id)
        with _connect(self._path) as conn:
            conn.execute("DELETE FROM comms_log WHERE id=?", (int(entry_id),))
            conn.commit()
        self._write_audit(entry_id, "delete", {"previous": asdict(current)})

    def _diff_entries(self, before: CommsLogEntry, after: CommsLogEntry) -> Dict[str, Any]:
        before_map = asdict(before)
        after_map = asdict(after)
        diff: Dict[str, Any] = {}
        for key in after_map.keys():
            if key in {"created_at", "updated_at"}:
                continue
            if before_map.get(key) != after_map.get(key):
                diff[key] = {"old": before_map.get(key), "new": after_map.get(key)}
        return diff

    def _write_audit(self, entry_id: int, action: str, payload: Dict[str, Any]) -> None:
        user = AppState.get_active_user_id()
        changed_by = str(user) if user is not None else None
        record = CommsLogAuditEntry(
            comms_log_id=entry_id,
            action=action,
            changed_by=changed_by,
            change_json=payload,
        )
        data = asdict(record)
        data["change_json"] = json.dumps(payload, ensure_ascii=False)
        columns = ",".join(k for k in data.keys() if k != "id")
        placeholders = ",".join(["?"] * (len(data) - 1))
        values = [data[k] for k in data.keys() if k != "id"]
        with _connect(self._path) as conn:
            conn.execute(
                f"INSERT INTO comms_log_audit ({columns}) VALUES ({placeholders})",
                values,
            )
            conn.commit()

    def list_audit_entries(self, entry_id: int) -> List[CommsLogAuditEntry]:
        with _connect(self._path) as conn:
            rows = conn.execute(
                "SELECT * FROM comms_log_audit WHERE comms_log_id=? ORDER BY changed_at DESC",
                (int(entry_id),),
            ).fetchall()
        result: List[CommsLogAuditEntry] = []
        for row in rows:
            try:
                payload = json.loads(row["change_json"])
            except Exception:
                payload = {}
            result.append(
                CommsLogAuditEntry(
                    id=row["id"],
                    comms_log_id=row["comms_log_id"],
                    action=row["action"],
                    changed_by=row["changed_by"],
                    changed_at=row["changed_at"],
                    change_json=payload,
                )
            )
        return result

    def list_contact_entities(self) -> List[Dict[str, Any]]:
        suggestions: List[Dict[str, Any]] = []
        with _connect(self._path) as conn:
            tables: set[str] = set()
            try:
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = {str(row[0]) for row in cur.fetchall()}
            except sqlite3.DatabaseError:
                return suggestions

            if "teams" in tables:
                try:
                    rows = conn.execute("SELECT * FROM teams").fetchall()
                except sqlite3.DatabaseError:
                    rows = []
                for row in rows:
                    team_id = _safe_row_value(row, "id")
                    if team_id is None:
                        continue
                    name = _safe_row_value(row, "name") or ""
                    callsign = _safe_row_value(row, "callsign") or ""
                    display = name or callsign or f"Team {team_id}"
                    alias_values = [value for value in (name, callsign) if value]
                    secondary_parts = [value for value in alias_values if value != display]
                    secondary = " / ".join(dict.fromkeys(secondary_parts))
                    entry = {
                        "type": "team",
                        "id": int(team_id),
                        "primary": display,
                        "secondary": secondary,
                        "aliases": alias_values,
                    }
                    suggestions.append(entry)

            if "personnel" in tables:
                try:
                    rows = conn.execute(
                        "SELECT id, name, role, callsign FROM personnel"
                    ).fetchall()
                except sqlite3.DatabaseError:
                    rows = []
                for row in rows:
                    person_id = _safe_row_value(row, "id")
                    if person_id is None:
                        continue
                    name = _safe_row_value(row, "name") or ""
                    role = _safe_row_value(row, "role") or ""
                    callsign = _safe_row_value(row, "callsign") or ""
                    primary = role or name or callsign or f"Personnel {person_id}"
                    secondary_parts = [value for value in (name, callsign) if value and value != primary]
                    secondary = " / ".join(secondary_parts)
                    entry = {
                        "type": "personnel",
                        "id": int(person_id),
                        "primary": primary,
                        "secondary": secondary,
                        "aliases": [value for value in (role, name, callsign) if value],
                    }
                    suggestions.append(entry)

        return suggestions

    def list_filter_presets(self, user_id: Optional[str] = None) -> List[CommsLogFilterPreset]:
        user = user_id or AppState.get_active_user_id()
        if user is None:
            return []
        with _connect(self._path) as conn:
            rows = conn.execute(
                "SELECT * FROM comms_log_filters WHERE user_id=? ORDER BY name",
                (str(user),),
            ).fetchall()
        presets: List[CommsLogFilterPreset] = []
        for row in rows:
            try:
                filters = json.loads(row["filters_json"])
            except Exception:
                filters = {}
            presets.append(
                CommsLogFilterPreset(
                    id=row["id"],
                    name=row["name"],
                    user_id=row["user_id"],
                    filters=filters,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return presets

    def save_filter_preset(
        self,
        name: str,
        filters: Dict[str, Any],
        *,
        preset_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> CommsLogFilterPreset:
        user = user_id or AppState.get_active_user_id()
        if user is None:
            raise RuntimeError("Active user is required to save presets")
        timestamp = utcnow_iso()
        payload = json.dumps(filters, ensure_ascii=False)
        if preset_id is None:
            with _connect(self._path) as conn:
                cur = conn.execute(
                    "INSERT INTO comms_log_filters (name, user_id, filters_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (name, str(user), payload, timestamp, timestamp),
                )
                preset_id = cur.lastrowid
                conn.commit()
        else:
            with _connect(self._path) as conn:
                conn.execute(
                    "UPDATE comms_log_filters SET name=?, filters_json=?, updated_at=? WHERE id=? AND user_id=?",
                    (name, payload, timestamp, int(preset_id), str(user)),
                )
                conn.commit()
        return CommsLogFilterPreset(
            id=int(preset_id),
            name=name,
            user_id=str(user),
            filters=filters,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def delete_filter_preset(self, preset_id: int, *, user_id: Optional[str] = None) -> None:
        user = user_id or AppState.get_active_user_id()
        if user is None:
            raise RuntimeError("Active user is required")
        with _connect(self._path) as conn:
            conn.execute(
                "DELETE FROM comms_log_filters WHERE id=? AND user_id=?",
                (int(preset_id), str(user)),
            )
            conn.commit()

    def mark_disposition(self, entry_id: int, disposition: str) -> CommsLogEntry:
        if not disposition:
            disposition = DISPOSITION_OPEN
        return self.update_entry(entry_id, {"disposition": disposition})

    def mark_follow_up(self, entry_id: int, required: bool) -> CommsLogEntry:
        return self.update_entry(entry_id, {"follow_up_required": required})

    def mark_status_update(self, entry_id: int, value: bool) -> CommsLogEntry:
        return self.update_entry(entry_id, {"is_status_update": value})


class ApiCommsLogRepository:
    """CommsLogRepository backed by the SARApp API (MongoDB)."""

    def __init__(self, incident_id: Optional[str] = None, master_repo=None):
        from utils.state import AppState
        incident = incident_id or AppState.get_active_incident()
        if not incident:
            raise RuntimeError("No active incident configured")
        self.incident_id = str(incident)
        self._base = f"/api/incidents/{self.incident_id}/comms-log"

    def _entry_from_response(self, data: dict) -> CommsLogEntry:
        if data.get("attachments") and isinstance(data["attachments"], str):
            try:
                data["attachments"] = json.loads(data["attachments"])
            except Exception:
                data["attachments"] = []
        return CommsLogEntry(
            id=data.get("id"),
            ts_utc=data.get("ts_utc", ""),
            ts_local=data.get("ts_local", ""),
            priority=data.get("priority", "Routine"),
            resource_id=data.get("resource_id"),
            resource_label=data.get("resource_label", ""),
            frequency=data.get("frequency", ""),
            band=data.get("band", ""),
            mode=data.get("mode", ""),
            from_unit=data.get("from_unit", ""),
            to_unit=data.get("to_unit", ""),
            message=data.get("message", ""),
            action_taken=data.get("action_taken", ""),
            follow_up_required=bool(data.get("follow_up_required", False)),
            disposition=data.get("disposition", "Open"),
            operator_user_id=data.get("operator_user_id"),
            operator_display_name=data.get("operator_display_name"),
            team_id=data.get("team_id"),
            task_id=data.get("task_id"),
            vehicle_id=data.get("vehicle_id"),
            personnel_id=data.get("personnel_id"),
            attachments=data.get("attachments") or [],
            geotag_lat=data.get("geotag_lat"),
            geotag_lon=data.get("geotag_lon"),
            notification_level=data.get("notification_level"),
            is_status_update=bool(data.get("is_status_update", False)),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def add_entry(self, entry: CommsLogEntry) -> CommsLogEntry:
        from utils.api_client import api_client
        from dataclasses import asdict
        payload = asdict(entry)
        payload.pop("id", None)
        result = api_client.post(self._base, json=payload)
        return self._entry_from_response(result)

    def get_entry(self, entry_id: int) -> CommsLogEntry:
        from utils.api_client import api_client
        result = api_client.get(f"{self._base}/{entry_id}")
        return self._entry_from_response(result)

    def list_entries(self, query: Optional[CommsLogQuery] = None) -> List[CommsLogEntry]:
        from utils.api_client import api_client
        params: Dict[str, Any] = {}
        if query:
            if query.start_ts_utc:
                params["start_ts_utc"] = query.start_ts_utc
            if query.end_ts_utc:
                params["end_ts_utc"] = query.end_ts_utc
            if query.priorities:
                params["priorities"] = ",".join(query.priorities)
            if query.dispositions:
                params["dispositions"] = ",".join(query.dispositions)
            if query.is_status_update is not None:
                params["is_status_update"] = str(query.is_status_update).lower()
            if query.follow_up_required is not None:
                params["follow_up_required"] = str(query.follow_up_required).lower()
            if query.text_search:
                params["text_search"] = query.text_search
            if query.order_by:
                params["order_by"] = query.order_by
            params["order_desc"] = str(query.order_desc).lower()
            if query.limit is not None:
                params["limit"] = str(query.limit)
            if query.offset:
                params["offset"] = str(query.offset)
        results = api_client.get(self._base, params=params or None)
        return [self._entry_from_response(r) for r in results]

    def update_entry(self, entry_id: int, patch: Dict[str, Any]) -> CommsLogEntry:
        from utils.api_client import api_client
        result = api_client.patch(f"{self._base}/{entry_id}", json=patch)
        return self._entry_from_response(result)

    def delete_entry(self, entry_id: int) -> None:
        from utils.api_client import api_client
        api_client.delete(f"{self._base}/{entry_id}")

    def list_audit_entries(self, entry_id: int) -> List[CommsLogAuditEntry]:
        from utils.api_client import api_client
        results = api_client.get(f"{self._base}/{entry_id}/audit")
        audit = []
        for r in results:
            audit.append(CommsLogAuditEntry(
                id=r.get("id"),
                comms_log_id=entry_id,
                action=r.get("action", ""),
                changed_by=r.get("changed_by"),
                changed_at=r.get("changed_at"),
                change_json=r.get("change_json") or {},
            ))
        return audit

    def list_contact_entities(self) -> List[Dict[str, Any]]:
        from utils.api_client import api_client
        try:
            return api_client.get(f"{self._base}/contacts")
        except Exception:
            return []

    def list_filter_presets(self, user_id: Optional[str] = None) -> List[CommsLogFilterPreset]:
        from utils.api_client import api_client
        from utils.state import AppState
        user = user_id or AppState.get_active_user_id()
        if not user:
            return []
        results = api_client.get(
            f"/api/incidents/{self.incident_id}/comms-log-filters",
            params={"user_id": str(user)},
        )
        return [
            CommsLogFilterPreset(
                id=r.get("preset_id"),
                name=r.get("name", ""),
                user_id=r.get("user_id", ""),
                filters=r.get("filters") or {},
                created_at=r.get("created_at"),
                updated_at=r.get("updated_at"),
            )
            for r in results
        ]

    def save_filter_preset(
        self,
        name: str,
        filters: Dict[str, Any],
        *,
        preset_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> CommsLogFilterPreset:
        from utils.api_client import api_client
        from utils.state import AppState
        user = user_id or AppState.get_active_user_id()
        if not user:
            raise RuntimeError("Active user is required to save presets")
        result = api_client.post(
            f"/api/incidents/{self.incident_id}/comms-log-filters",
            json={"name": name, "filters": filters, "preset_id": preset_id, "user_id": str(user)},
        )
        return CommsLogFilterPreset(
            id=result.get("preset_id"),
            name=result.get("name", name),
            user_id=result.get("user_id", str(user)),
            filters=result.get("filters") or filters,
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
        )

    def delete_filter_preset(self, preset_id: int, *, user_id: Optional[str] = None) -> None:
        from utils.api_client import api_client
        from utils.state import AppState
        user = user_id or AppState.get_active_user_id()
        if not user:
            raise RuntimeError("Active user is required")
        api_client.delete(
            f"/api/incidents/{self.incident_id}/comms-log-filters/{preset_id}",
            params={"user_id": str(user)},
        )

    def mark_disposition(self, entry_id: int, disposition: str) -> CommsLogEntry:
        return self.update_entry(entry_id, {"disposition": disposition or DISPOSITION_OPEN})

    def mark_follow_up(self, entry_id: int, required: bool) -> CommsLogEntry:
        return self.update_entry(entry_id, {"follow_up_required": required})

    def mark_status_update(self, entry_id: int, value: bool) -> CommsLogEntry:
        return self.update_entry(entry_id, {"is_status_update": value})


__all__ = ["CommsLogRepository", "ApiCommsLogRepository"]
