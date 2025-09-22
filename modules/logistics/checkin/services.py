"""Simplified service layer for the Logistics Check-In window.

The previous iteration of this module exposed a large rule engine and a
complex roster workflow.  The Logistics team requested a leaner
implementation that focuses on selecting master records and duplicating
those rows into the active incident database.  This module therefore
exposes lightweight helpers to list master records, create new entries,
and copy them into the incident scope.  The tables are created on demand
so tests can run against temporary SQLite files.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import sqlite3

from utils.db import get_incident_conn, get_master_conn


@dataclass(frozen=True)
class FieldSpec:
    """Metadata describing a field exposed in the "new record" dialog."""

    name: str
    label: str
    required: bool = False
    placeholder: Optional[str] = None


@dataclass(frozen=True)
class EntityConfig:
    """Configuration for a master/incident entity pair."""

    key: str
    title: str
    master_table: str
    incident_table: str
    id_column: str
    sort_column: str
    display_columns: Tuple[Tuple[str, str], ...]
    form_fields: Tuple[FieldSpec, ...]
    id_field: Optional[FieldSpec] = None
    autoincrement: bool = True


_MASTER_SCHEMAS: Dict[str, str] = {
    "personnel": """
        CREATE TABLE IF NOT EXISTS personnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rank TEXT,
            callsign TEXT,
            role TEXT,
            contact TEXT,
            unit TEXT,
            phone TEXT,
            email TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            emergency_contact_relationship TEXT
        )
    """,
    "equipment": """
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT,
            serial_number TEXT,
            condition TEXT,
            notes TEXT
        )
    """,
    "vehicle": """
        CREATE TABLE IF NOT EXISTS vehicles (
            id TEXT PRIMARY KEY,
            vin TEXT,
            license_plate TEXT,
            year INTEGER,
            make TEXT,
            model TEXT,
            capacity INTEGER,
            type_id TEXT,
            status_id TEXT NOT NULL DEFAULT 'Available',
            tags TEXT,
            organization TEXT
        )
    """,
    "aircraft": """
        CREATE TABLE IF NOT EXISTS aircraft (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tail_number TEXT NOT NULL,
            callsign TEXT,
            type TEXT NOT NULL,
            make_model TEXT,
            capacity INTEGER,
            status TEXT NOT NULL DEFAULT 'Available',
            base_location TEXT,
            current_assignment TEXT,
            capabilities TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

_INCIDENT_SCHEMAS: Dict[str, str] = {
    key: schema.replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE IF NOT EXISTS")
    for key, schema in _MASTER_SCHEMAS.items()
}

ENTITY_CONFIG: Dict[str, EntityConfig] = {
    "personnel": EntityConfig(
        key="personnel",
        title="Personnel",
        master_table="personnel",
        incident_table="personnel",
        id_column="id",
        sort_column="name",
        display_columns=(
            ("id", "ID"),
            ("name", "Name"),
            ("role", "Role"),
            ("callsign", "Callsign"),
        ),
        form_fields=(
            FieldSpec("name", "Name", required=True),
            FieldSpec("role", "Role"),
            FieldSpec("callsign", "Callsign"),
            FieldSpec("phone", "Phone"),
        ),
        autoincrement=True,
    ),
    "vehicle": EntityConfig(
        key="vehicle",
        title="Vehicle",
        master_table="vehicles",
        incident_table="vehicles",
        id_column="id",
        sort_column="id",
        display_columns=(
            ("id", "ID"),
            ("make", "Make"),
            ("model", "Model"),
            ("status_id", "Status"),
        ),
        form_fields=(
            FieldSpec("make", "Make"),
            FieldSpec("model", "Model"),
            FieldSpec("license_plate", "License Plate"),
            FieldSpec("status_id", "Status"),
        ),
        id_field=FieldSpec("id", "Vehicle ID", required=True),
        autoincrement=False,
    ),
    "equipment": EntityConfig(
        key="equipment",
        title="Equipment",
        master_table="equipment",
        incident_table="equipment",
        id_column="id",
        sort_column="name",
        display_columns=(
            ("id", "ID"),
            ("name", "Name"),
            ("type", "Type"),
            ("condition", "Condition"),
        ),
        form_fields=(
            FieldSpec("name", "Name", required=True),
            FieldSpec("type", "Type"),
            FieldSpec("serial_number", "Serial Number"),
            FieldSpec("condition", "Condition"),
        ),
        autoincrement=True,
    ),
    "aircraft": EntityConfig(
        key="aircraft",
        title="Aircraft",
        master_table="aircraft",
        incident_table="aircraft",
        id_column="id",
        sort_column="tail_number",
        display_columns=(
            ("id", "ID"),
            ("tail_number", "Tail Number"),
            ("type", "Type"),
            ("status", "Status"),
        ),
        form_fields=(
            FieldSpec("tail_number", "Tail Number", required=True),
            FieldSpec("type", "Type", required=True),
            FieldSpec("callsign", "Callsign"),
            FieldSpec("base_location", "Base Location"),
        ),
        autoincrement=True,
    ),
}

ENTITY_ORDER: Tuple[str, ...] = ("personnel", "vehicle", "equipment", "aircraft")


def _get_config(entity_type: str) -> EntityConfig:
    try:
        return ENTITY_CONFIG[entity_type]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown entity type: {entity_type}") from exc


def _ensure_master_schema(conn: sqlite3.Connection, config: EntityConfig) -> None:
    conn.execute(_MASTER_SCHEMAS[config.key])
    conn.commit()


def _ensure_incident_schema(conn: sqlite3.Connection, config: EntityConfig) -> None:
    conn.execute(_INCIDENT_SCHEMAS[config.key])
    conn.commit()


def iter_entity_configs() -> Iterable[EntityConfig]:
    """Yield entity configurations in UI order."""

    for key in ENTITY_ORDER:
        yield ENTITY_CONFIG[key]


def get_entity_config(entity_type: str) -> EntityConfig:
    """Return the configuration for ``entity_type``."""

    return _get_config(entity_type)


class CheckInService:
    """Facade that manages master and incident check-in records."""

    def list_master_records(self, entity_type: str) -> List[Dict[str, Any]]:
        """Return all master records for ``entity_type`` sorted for display."""

        config = _get_config(entity_type)
        with get_master_conn() as master_conn:
            _ensure_master_schema(master_conn, config)
            rows = master_conn.execute(
                f"SELECT * FROM {config.master_table} ORDER BY {config.sort_column}"
            ).fetchall()
        incident_ids = self._incident_id_set(config)
        results: List[Dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            identifier = record.get(config.id_column)
            record["_checked_in"] = str(identifier) in incident_ids if identifier is not None else False
            results.append(record)
        return results

    def create_master_record(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new master record and return the stored row."""

        config = _get_config(entity_type)
        columns: List[str] = []
        values: List[Any] = []
        supplied_id: Optional[Any] = None

        if config.id_field is not None:
            supplied = data.get(config.id_column)
            supplied_str = supplied.strip() if isinstance(supplied, str) else supplied
            if config.id_field.required and not supplied_str:
                raise ValueError(f"{config.id_field.label} is required")
            if supplied_str:
                supplied_id = supplied_str
                columns.append(config.id_column)
                values.append(supplied_str)

        for field in config.form_fields:
            raw_value = data.get(field.name)
            text_value = raw_value.strip() if isinstance(raw_value, str) else raw_value
            if field.required:
                if not text_value:
                    raise ValueError(f"{field.label} is required")
                columns.append(field.name)
                values.append(text_value)
            else:
                if text_value not in (None, ""):
                    columns.append(field.name)
                    values.append(text_value)

        if not columns:
            raise ValueError("No data provided")

        placeholders = ", ".join("?" for _ in columns)
        column_list = ", ".join(columns)
        sql = f"INSERT INTO {config.master_table} ({column_list}) VALUES ({placeholders})"

        with get_master_conn() as master_conn:
            _ensure_master_schema(master_conn, config)
            try:
                cur = master_conn.execute(sql, values)
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"{config.title} already exists with that identifier") from exc
            master_conn.commit()
            if supplied_id is not None:
                new_id = supplied_id
            else:
                new_id = cur.lastrowid

        record = self._get_master_record(config, new_id)
        record["_checked_in"] = False
        return record

    def check_in(self, entity_type: str, record_id: Any) -> Dict[str, Any]:
        """Copy the master record into the incident database."""

        config = _get_config(entity_type)
        record = self._get_master_record(config, record_id)
        columns = list(record.keys())
        values = [record[column] for column in columns]
        placeholders = ", ".join("?" for _ in columns)
        column_list = ", ".join(columns)
        sql = (
            f"INSERT OR REPLACE INTO {config.incident_table} ({column_list})"
            f" VALUES ({placeholders})"
        )
        with get_incident_conn() as incident_conn:
            _ensure_incident_schema(incident_conn, config)
            incident_conn.execute(sql, values)
            incident_conn.commit()
        record["_checked_in"] = True
        return record

    def _incident_id_set(self, config: EntityConfig) -> set[str]:
        with get_incident_conn() as incident_conn:
            _ensure_incident_schema(incident_conn, config)
            rows = incident_conn.execute(
                f"SELECT {config.id_column} FROM {config.incident_table}"
            ).fetchall()
        identifiers: set[str] = set()
        for row in rows:
            value = row[config.id_column]
            if value is not None:
                identifiers.add(str(value))
        return identifiers

    def _normalize_identifier(self, config: EntityConfig, record_id: Any) -> Any:
        if record_id is None:
            raise ValueError("Record identifier is required")
        if config.autoincrement:
            if isinstance(record_id, int):
                return record_id
            text = str(record_id).strip()
            if not text:
                raise ValueError("Record identifier is required")
            try:
                return int(text)
            except ValueError as exc:
                raise ValueError(f"Invalid identifier for {config.title}") from exc
        return str(record_id).strip()

    def _get_master_record(self, config: EntityConfig, record_id: Any) -> Dict[str, Any]:
        normalized = self._normalize_identifier(config, record_id)
        with get_master_conn() as master_conn:
            _ensure_master_schema(master_conn, config)
            row = master_conn.execute(
                f"SELECT * FROM {config.master_table} WHERE {config.id_column} = ?",
                (normalized,),
            ).fetchone()
        if row is None:
            raise ValueError(f"{config.title} record not found")
        return dict(row)


_service: Optional[CheckInService] = None


def get_service() -> CheckInService:
    """Return a shared :class:`CheckInService` instance."""

    global _service
    if _service is None:
        _service = CheckInService()
    return _service


def reset_service() -> None:
    """Reset the shared service instance (useful for tests)."""

    global _service
    _service = None


__all__ = [
    "CheckInService",
    "EntityConfig",
    "FieldSpec",
    "ENTITY_ORDER",
    "ENTITY_CONFIG",
    "get_entity_config",
    "iter_entity_configs",
    "get_service",
    "reset_service",
]
