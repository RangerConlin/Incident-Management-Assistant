from __future__ import annotations

from utils.edit_window_kit import sync_result_allows_collection_refresh


def test_synced_result_allows_collection_refresh() -> None:
    assert sync_result_allows_collection_refresh({"synced": True}, "personnel") is True


def test_unrelated_full_tick_pull_failure_allows_collection_refresh() -> None:
    result = {
        "synced": False,
        "details": {
            "pull_failed_collections": ["vehicles"],
        },
    }

    assert sync_result_allows_collection_refresh(result, "personnel") is True


def test_matching_full_tick_pull_failure_blocks_collection_refresh() -> None:
    result = {
        "synced": False,
        "details": {
            "pull_failed_collections": ["personnel", "vehicles"],
        },
    }

    assert sync_result_allows_collection_refresh(result, "personnel") is False
