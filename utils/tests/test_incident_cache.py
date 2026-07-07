from __future__ import annotations

from utils.incident_cache import incident_cache


def test_incident_cache_tracks_meta_and_trims_heavy_collections() -> None:
    incident_cache.clear()
    incident_cache.load_snapshot(
        "INC-LIMITS",
        {
            "communications_log": [
                {"_id": "log-1", "text": "one"},
                {"_id": "log-2", "text": "two"},
            ]
        },
        meta={
            "policy": {
                "max_collection_docs": 100,
                "max_heavy_collection_docs": 2,
                "heavy_collections": ["communications_log"],
            },
            "truncated": {"communications_log": {"loaded": 2, "total": 5}},
        },
    )

    incident_cache.apply_event(
        {
            "collection": "communications_log",
            "op": "created",
            "id": "log-3",
            "doc": {"_id": "log-3", "text": "three"},
        }
    )

    rows = incident_cache.get_all("communications_log")
    telemetry = incident_cache.telemetry()

    assert len(rows) == 2
    assert [row["_id"] for row in rows] == ["log-2", "log-3"]
    assert incident_cache.snapshot_meta()["truncated"]["communications_log"]["total"] == 5
    assert telemetry["collections"]["communications_log"]["truncated"] is True

    incident_cache.clear()
