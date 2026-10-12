"""Unit tests for the master_link sub-document builder (no Mongo needed)."""
from __future__ import annotations

import pytest

from sarapp_db.mongo.master_link import (
    CONFLICT,
    LINKED,
    LOCAL_ONLY,
    ORPHANED,
    build_master_link,
    mark_orphaned,
)


def test_build_master_link_defaults_to_linked():
    link = build_master_link(
        master_collection="personnel",
        master_id="abc-123",
        master_server_origin="server-1",
    )
    assert link["master_collection"] == "personnel"
    assert link["master_id"] == "abc-123"
    assert link["master_server_origin"] == "server-1"
    assert link["central_master_id"] is None
    assert link["sync_state"] == LINKED
    assert link["conflict"] is None
    assert link["last_synced_at"]


def test_build_master_link_orphaned_without_master_id():
    link = build_master_link(
        master_collection="personnel",
        master_server_origin="server-1",
        sync_state=ORPHANED,
    )
    assert link["master_id"] is None
    assert link["sync_state"] == ORPHANED


def test_build_master_link_requires_master_id_unless_orphaned():
    for state in (LINKED, CONFLICT, LOCAL_ONLY):
        with pytest.raises(ValueError):
            build_master_link(
                master_collection="personnel",
                master_server_origin="server-1",
                sync_state=state,
            )


def test_build_master_link_rejects_unknown_sync_state():
    with pytest.raises(ValueError):
        build_master_link(
            master_collection="personnel",
            master_id="abc-123",
            master_server_origin="server-1",
            sync_state="bogus",
        )


def test_mark_orphaned_does_not_mutate_input():
    original = build_master_link(
        master_collection="personnel",
        master_id="abc-123",
        master_server_origin="server-1",
    )
    updated = mark_orphaned(original)

    assert updated["sync_state"] == ORPHANED
    assert original["sync_state"] == LINKED
