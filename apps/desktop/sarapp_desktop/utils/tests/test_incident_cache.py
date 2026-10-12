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
    assert incident_cache.is_collection_complete("communications_log") is False

    incident_cache.clear()


def test_is_collection_complete_true_until_something_is_dropped() -> None:
    incident_cache.clear()
    incident_cache.load_snapshot(
        "INC-COMPLETE",
        {"communications_log": [{"_id": "h-1", "person_record": 1, "ts": "2026-07-07T00:00:00+00:00"}]},
        meta={"policy": {"max_heavy_collection_docs": 5, "heavy_collections": ["communications_log"]}},
    )

    assert incident_cache.is_collection_complete("communications_log") is True
    assert incident_cache.is_collection_complete("unloaded_collection") is True

    # Adding more docs than the cap trims the oldest and flips the flag.
    for i in range(2, 8):
        incident_cache.apply_event({
            "collection": "communications_log",
            "op": "created",
            "id": f"h-{i}",
            "doc": {"_id": f"h-{i}", "person_record": 1, "ts": f"2026-07-07T0{i}:00:00+00:00"},
        })

    assert incident_cache.is_collection_complete("communications_log") is False

    incident_cache.clear()


def test_is_collection_complete_reflects_server_reported_truncation() -> None:
    incident_cache.clear()
    incident_cache.load_snapshot(
        "INC-SERVER-TRUNCATED",
        {"communications_log": []},
        meta={"truncated": {"communications_log": {"loaded": 0, "total": 900, "reason": "snapshot byte budget"}}},
    )

    assert incident_cache.is_collection_complete("communications_log") is False

    incident_cache.clear()
