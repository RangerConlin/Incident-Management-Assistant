from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from utils import incident_context
from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.models.spatial_feature_link import SpatialFeatureLink
from modules.gis.services.schema_bootstrap import ensure_spatial_schema


class SpatialRepository:
    """Incident-scoped persistence for shared spatial features and links."""

    def __init__(self, incident_id: str | None = None) -> None:
        self._incident_id = incident_id or incident_context.get_active_incident_id()
        if not self._incident_id:
            raise RuntimeError("An active incident is required for the spatial repository.")

    @property
    def incident_id(self) -> str:
        return str(self._incident_id)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db_path = incident_context.get_active_incident_db_path()
        conn = sqlite3.connect(os.path.abspath(str(db_path)))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=3000")
        except Exception:
            pass
        ensure_spatial_schema(conn)
        try:
            yield conn
        finally:
            conn.close()

    def create_feature(self, feature: SpatialFeature) -> SpatialFeature:
        now = _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO spatial_features (
                    incident_id, feature_type, feature_subtype, geometry_type, label,
                    description, status, source_module, source_record_type,
                    source_record_id, geometry_wkt, centroid_lat, centroid_lon,
                    bbox_min_lat, bbox_min_lon, bbox_max_lat, bbox_max_lon,
                    elevation_m, start_time, end_time, is_planning_only, is_visible,
                    is_locked, is_archived, layer_key, style_key, created_at,
                    updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.incident_id,
                    str(feature.feature_type),
                    feature.feature_subtype,
                    str(feature.geometry_type),
                    feature.label,
                    feature.description,
                    feature.status,
                    feature.source_module,
                    feature.source_record_type,
                    feature.source_record_id,
                    feature.geometry_wkt,
                    feature.centroid_lat,
                    feature.centroid_lon,
                    feature.bbox_min_lat,
                    feature.bbox_min_lon,
                    feature.bbox_max_lat,
                    feature.bbox_max_lon,
                    feature.elevation_m,
                    _as_iso(feature.start_time),
                    _as_iso(feature.end_time),
                    int(feature.is_planning_only),
                    int(feature.is_visible),
                    int(feature.is_locked),
                    int(feature.is_archived),
                    feature.layer_key,
                    feature.style_key,
                    _as_iso(feature.created_at or now),
                    _as_iso(feature.updated_at or now),
                    feature.created_by,
                    feature.updated_by,
                ),
            )
            conn.commit()
            feature_id = int(cur.lastrowid)
        stored = self.get_feature(feature_id)
        if stored is None:
            raise RuntimeError("Spatial feature insert failed.")
        return stored

    def update_feature(self, feature_id: int, updates: dict[str, Any]) -> SpatialFeature | None:
        if not updates:
            return self.get_feature(feature_id)

        allowed = {
            "geometry_type",
            "feature_subtype",
            "label",
            "description",
            "status",
            "geometry_wkt",
            "centroid_lat",
            "centroid_lon",
            "bbox_min_lat",
            "bbox_min_lon",
            "bbox_max_lat",
            "bbox_max_lon",
            "elevation_m",
            "start_time",
            "end_time",
            "is_planning_only",
            "is_visible",
            "is_locked",
            "is_archived",
            "layer_key",
            "style_key",
            "updated_by",
        }
        changed = {key: value for key, value in updates.items() if key in allowed}
        if not changed:
            return self.get_feature(feature_id)

        if "start_time" in changed:
            changed["start_time"] = _as_iso(changed["start_time"])
        if "end_time" in changed:
            changed["end_time"] = _as_iso(changed["end_time"])
        if "geometry_type" in changed:
            changed["geometry_type"] = str(changed["geometry_type"])
        for flag_field in ("is_planning_only", "is_visible", "is_locked", "is_archived"):
            if flag_field in changed:
                changed[flag_field] = int(bool(changed[flag_field]))

        changed["updated_at"] = _as_iso(_utc_now())

        set_sql = ", ".join(f"{key}=?" for key in changed)
        params = list(changed.values()) + [self.incident_id, feature_id]

        with self._connect() as conn:
            conn.execute(
                f"UPDATE spatial_features SET {set_sql} WHERE incident_id=? AND id=?",
                params,
            )
            conn.commit()

        return self.get_feature(feature_id)

    def archive_feature(self, feature_id: int, updated_by: str | None = None) -> SpatialFeature | None:
        return self.update_feature(
            feature_id,
            {
                "is_archived": 1,
                "status": "archived",
                "updated_by": updated_by,
            },
        )

    def get_feature(self, feature_id: int) -> SpatialFeature | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM spatial_features WHERE incident_id=? AND id=?",
                (self.incident_id, feature_id),
            ).fetchone()
        return _row_to_feature(row) if row else None

    def list_features(self, include_archived: bool = False) -> list[SpatialFeature]:
        where = "" if include_archived else " AND is_archived=0"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM spatial_features WHERE incident_id=?{where} ORDER BY updated_at DESC, id DESC",
                (self.incident_id,),
            ).fetchall()
        return [_row_to_feature(row) for row in rows]

    def list_features_by_type(self, feature_type: FeatureType, include_archived: bool = False) -> list[SpatialFeature]:
        where = "" if include_archived else " AND is_archived=0"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM spatial_features WHERE incident_id=? AND feature_type=?{where} ORDER BY id DESC",
                (self.incident_id, str(feature_type)),
            ).fetchall()
        return [_row_to_feature(row) for row in rows]

    def list_features_by_module(self, module_name: str, include_archived: bool = False) -> list[SpatialFeature]:
        where = "" if include_archived else " AND is_archived=0"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM spatial_features WHERE incident_id=? AND source_module=?{where} ORDER BY id DESC",
                (self.incident_id, module_name),
            ).fetchall()
        return [_row_to_feature(row) for row in rows]

    def list_features_for_record(self, module_name: str, record_type: str, record_id: str) -> list[SpatialFeature]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM spatial_features
                WHERE incident_id=?
                  AND source_module=?
                  AND source_record_type=?
                  AND source_record_id=?
                  AND is_archived=0
                ORDER BY id DESC
                """,
                (self.incident_id, module_name, record_type, str(record_id)),
            ).fetchall()
        return [_row_to_feature(row) for row in rows]

    def create_link(self, link: SpatialFeatureLink) -> SpatialFeatureLink:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO spatial_feature_links (
                    incident_id, feature_id, linked_module, linked_record_type,
                    linked_record_id, relationship_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.incident_id,
                    link.feature_id,
                    link.linked_module,
                    link.linked_record_type,
                    link.linked_record_id,
                    link.relationship_type,
                    _as_iso(link.created_at or _utc_now()),
                ),
            )
            conn.commit()
            link_id = int(cur.lastrowid)
            row = conn.execute(
                "SELECT * FROM spatial_feature_links WHERE incident_id=? AND id=?",
                (self.incident_id, link_id),
            ).fetchone()
        if not row:
            raise RuntimeError("Spatial link insert failed.")
        return _row_to_link(row)

    def list_links_for_feature(self, feature_id: int) -> list[SpatialFeatureLink]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM spatial_feature_links WHERE incident_id=? AND feature_id=? ORDER BY id DESC",
                (self.incident_id, feature_id),
            ).fetchall()
        return [_row_to_link(row) for row in rows]

    def list_related_features(self, module_name: str, record_type: str, record_id: str) -> list[SpatialFeature]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT sf.*
                FROM spatial_feature_links sfl
                JOIN spatial_features sf ON sf.id = sfl.feature_id
                WHERE sfl.incident_id=?
                  AND sf.incident_id=?
                  AND sfl.linked_module=?
                  AND sfl.linked_record_type=?
                  AND sfl.linked_record_id=?
                  AND sf.is_archived=0
                ORDER BY sf.id DESC
                """,
                (self.incident_id, self.incident_id, module_name, record_type, str(record_id)),
            ).fetchall()
        return [_row_to_feature(row) for row in rows]

    def delete_link(self, link_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM spatial_feature_links WHERE incident_id=? AND id=?",
                (self.incident_id, link_id),
            )
            conn.commit()
        return cur.rowcount > 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _row_to_feature(row: sqlite3.Row) -> SpatialFeature:
    return SpatialFeature(
        id=int(row["id"]),
        incident_id=str(row["incident_id"]),
        feature_type=FeatureType(str(row["feature_type"])),
        feature_subtype=row["feature_subtype"],
        geometry_type=GeometryType(str(row["geometry_type"])),
        label=str(row["label"]),
        description=row["description"],
        status=str(row["status"]),
        source_module=str(row["source_module"]),
        source_record_type=str(row["source_record_type"]),
        source_record_id=str(row["source_record_id"]),
        geometry_wkt=str(row["geometry_wkt"]),
        centroid_lat=row["centroid_lat"],
        centroid_lon=row["centroid_lon"],
        bbox_min_lat=row["bbox_min_lat"],
        bbox_min_lon=row["bbox_min_lon"],
        bbox_max_lat=row["bbox_max_lat"],
        bbox_max_lon=row["bbox_max_lon"],
        elevation_m=row["elevation_m"],
        start_time=_parse_iso(row["start_time"]),
        end_time=_parse_iso(row["end_time"]),
        is_planning_only=bool(row["is_planning_only"]),
        is_visible=bool(row["is_visible"]),
        is_locked=bool(row["is_locked"]),
        is_archived=bool(row["is_archived"]),
        layer_key=str(row["layer_key"]),
        style_key=row["style_key"],
        created_at=_parse_iso(row["created_at"]),
        updated_at=_parse_iso(row["updated_at"]),
        created_by=row["created_by"],
        updated_by=row["updated_by"],
    )


def _row_to_link(row: sqlite3.Row) -> SpatialFeatureLink:
    return SpatialFeatureLink(
        id=int(row["id"]),
        incident_id=str(row["incident_id"]),
        feature_id=int(row["feature_id"]),
        linked_module=str(row["linked_module"]),
        linked_record_type=str(row["linked_record_type"]),
        linked_record_id=str(row["linked_record_id"]),
        relationship_type=str(row["relationship_type"]),
        created_at=_parse_iso(row["created_at"]),
    )
