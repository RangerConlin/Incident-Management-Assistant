from __future__ import annotations

from sarapp_db.api.routers import organizations as org_router


class _FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def __iter__(self):
        return iter(self._docs)

    def sort(self, *_args, **_kwargs):
        return self


class _FakeOrgTypesCollection:
    """Minimal in-memory stand-in for the Mongo organization_types collection."""

    def __init__(self) -> None:
        self.docs: list[dict] = []

    def find(self, query: dict | None = None, projection: dict | None = None):
        return _FakeCursor(list(self.docs))

    def insert_one(self, doc: dict) -> None:
        self.docs.append(dict(doc))


def setup_function(_fn) -> None:
    # The seeding helper only seeds once per process; reset the guard so
    # each test exercises a fresh collection.
    org_router._default_types_seeded = False


def test_seed_default_types_inserts_all_canonical_names() -> None:
    col = _FakeOrgTypesCollection()

    org_router._seed_default_types_if_needed(col)

    names = {doc["name"] for doc in col.docs}
    expected = {name for name, _description in org_router.DEFAULT_ORGANIZATION_TYPES}
    assert names == expected


def test_seed_default_types_is_idempotent() -> None:
    col = _FakeOrgTypesCollection()

    org_router._seed_default_types_if_needed(col)
    count_after_first = len(col.docs)

    # Reset only the in-process guard, not the collection, to simulate a
    # second server process seeding against an already-seeded database.
    org_router._default_types_seeded = False
    org_router._seed_default_types_if_needed(col)

    assert len(col.docs) == count_after_first


def test_seed_default_types_preserves_existing_entries() -> None:
    col = _FakeOrgTypesCollection()
    col.docs.append({"int_id": 1, "name": "Air Agency", "description": "Custom override"})

    org_router._seed_default_types_if_needed(col)

    air_agency_docs = [doc for doc in col.docs if doc["name"] == "Air Agency"]
    assert len(air_agency_docs) == 1
    assert air_agency_docs[0]["description"] == "Custom override"
