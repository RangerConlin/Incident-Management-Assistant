from __future__ import annotations

import sqlite3


def ensure_spatial_schema(conn: sqlite3.Connection) -> None:
    """Ensure spatial framework tables exist in an incident-scoped database."""

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spatial_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            feature_type TEXT NOT NULL,
            feature_subtype TEXT,
            geometry_type TEXT NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            source_module TEXT NOT NULL,
            source_record_type TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            geometry_wkt TEXT NOT NULL,
            centroid_lat REAL,
            centroid_lon REAL,
            bbox_min_lat REAL,
            bbox_min_lon REAL,
            bbox_max_lat REAL,
            bbox_max_lon REAL,
            elevation_m REAL,
            start_time TEXT,
            end_time TEXT,
            is_planning_only INTEGER NOT NULL DEFAULT 0,
            is_visible INTEGER NOT NULL DEFAULT 1,
            is_locked INTEGER NOT NULL DEFAULT 0,
            is_archived INTEGER NOT NULL DEFAULT 0,
            layer_key TEXT NOT NULL,
            style_key TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_by TEXT,
            updated_by TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spatial_features_incident ON spatial_features(incident_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spatial_features_type ON spatial_features(incident_id, feature_type, is_archived)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spatial_features_source ON spatial_features(incident_id, source_module, source_record_type, source_record_id)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spatial_feature_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            feature_id INTEGER NOT NULL,
            linked_module TEXT NOT NULL,
            linked_record_type TEXT NOT NULL,
            linked_record_id TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(feature_id) REFERENCES spatial_features(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spatial_links_feature ON spatial_feature_links(incident_id, feature_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spatial_links_record ON spatial_feature_links(incident_id, linked_module, linked_record_type, linked_record_id)"
    )

    conn.commit()
