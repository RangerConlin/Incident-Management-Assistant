from __future__ import annotations

from sarapp_db.api.routers import organizations as org_router


class _FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def __iter__(self):
        return iter(self._docs)

    def sort(self, key, _direction=1):
        return _FakeCursor(sorted(self._docs, key=lambda d: d.get(key) or 0))


class _FakeCollection:
    """Minimal in-memory stand-in for a Mongo collection."""

    def __init__(self) -> None:
        self.docs: list[dict] = []

    def find(self, query: dict | None = None, projection: dict | None = None):
        query = query or {}
        return _FakeCursor([d for d in self.docs if self._matches(d, query)])

    def find_one(self, query: dict, projection: dict | None = None):
        for d in self.docs:
            if self._matches(d, query):
                return d
        return None

    def insert_one(self, doc: dict) -> None:
        self.docs.append(dict(doc))

    def delete_many(self, query: dict) -> None:
        self.docs = [d for d in self.docs if not self._matches(d, query)]

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        return all(doc.get(k) == v for k, v in query.items())


def setup_function(_fn) -> None:
    org_router._default_types_seeded = False
    org_router._default_rank_structures_seeded = False


def _fresh_cols(monkeypatch):
    org_types = _FakeCollection()
    rank_structures = _FakeCollection()
    ranks = _FakeCollection()
    monkeypatch.setattr(org_router, "_org_types_col", lambda: org_types)
    monkeypatch.setattr(org_router, "_rank_structures_col", lambda: rank_structures)
    monkeypatch.setattr(org_router, "_ranks_col", lambda: ranks)
    return org_types, rank_structures, ranks


def test_seed_default_rank_structures_creates_templates_and_ranks(monkeypatch) -> None:
    org_types, rank_structures, ranks = _fresh_cols(monkeypatch)

    org_router._seed_default_rank_structures_if_needed(rank_structures)

    names = {d["name"] for d in rank_structures.docs}
    expected = {name for name, _org_type, _ranks in org_router.DEFAULT_RANK_STRUCTURES}
    assert names == expected

    fire = next(d for d in rank_structures.docs if d["name"] == "Fire Department (Standard)")
    fire_ranks = [r for r in ranks.docs if r["rank_structure_id"] == fire["int_id"]]
    assert [r["rank_code"] for r in fire_ranks] == ["FF", "ENG", "LT", "CPT", "BC", "DC", "CHIEF"]
    # Linked to the matching organization type, seeded as a side effect.
    assert fire["organization_type_id"] is not None
    org_type = next(t for t in org_types.docs if t["int_id"] == fire["organization_type_id"])
    assert org_type["name"] == "Fire/Rescue"


def test_seed_default_rank_structures_is_idempotent(monkeypatch) -> None:
    _org_types, rank_structures, ranks = _fresh_cols(monkeypatch)

    org_router._seed_default_rank_structures_if_needed(rank_structures)
    structure_count = len(rank_structures.docs)
    rank_count = len(ranks.docs)

    org_router._default_rank_structures_seeded = False
    org_router._seed_default_rank_structures_if_needed(rank_structures)

    assert len(rank_structures.docs) == structure_count
    assert len(ranks.docs) == rank_count


def test_organization_inherits_parent_rank_structure_when_unset(monkeypatch) -> None:
    organizations = _FakeCollection()
    rank_structures = _FakeCollection()
    monkeypatch.setattr(org_router, "_rank_structures_col", lambda: rank_structures)

    rank_structures.insert_one({"int_id": 1, "name": "Fire Department (Standard)"})

    parent = {"int_id": 10, "name": "County Fire", "default_rank_structure_id": 1, "parent_organization_id": None}
    child = {"int_id": 11, "name": "Engine 1", "default_rank_structure_id": None, "parent_organization_id": 10}
    organizations.docs = [parent, child]

    enriched_child = org_router._enrich_organization(organizations, child)
    assert enriched_child["effective_rank_structure_id"] == 1
    assert enriched_child["rank_structure_inherited"] is True
    assert enriched_child["effective_rank_structure_name"] == "Fire Department (Standard)"

    enriched_parent = org_router._enrich_organization(organizations, parent)
    assert enriched_parent["effective_rank_structure_id"] == 1
    assert enriched_parent["rank_structure_inherited"] is False


def test_organization_explicit_rank_structure_overrides_inheritance(monkeypatch) -> None:
    organizations = _FakeCollection()
    rank_structures = _FakeCollection()
    monkeypatch.setattr(org_router, "_rank_structures_col", lambda: rank_structures)

    rank_structures.insert_one({"int_id": 1, "name": "Fire Department (Standard)"})
    rank_structures.insert_one({"int_id": 2, "name": "EMS (Standard)"})

    parent = {"int_id": 10, "name": "County Fire", "default_rank_structure_id": 1, "parent_organization_id": None}
    child = {"int_id": 11, "name": "Medic 1", "default_rank_structure_id": 2, "parent_organization_id": 10}
    organizations.docs = [parent, child]

    enriched_child = org_router._enrich_organization(organizations, child)
    assert enriched_child["effective_rank_structure_id"] == 2
    assert enriched_child["rank_structure_inherited"] is False
    assert enriched_child["effective_rank_structure_name"] == "EMS (Standard)"


def test_organization_with_no_rank_structure_anywhere_in_chain(monkeypatch) -> None:
    organizations = _FakeCollection()
    rank_structures = _FakeCollection()
    monkeypatch.setattr(org_router, "_rank_structures_col", lambda: rank_structures)

    parent = {"int_id": 10, "name": "Unaffiliated Group", "default_rank_structure_id": None, "parent_organization_id": None}
    child = {"int_id": 11, "name": "Sub Team", "default_rank_structure_id": None, "parent_organization_id": 10}
    organizations.docs = [parent, child]

    enriched_child = org_router._enrich_organization(organizations, child)
    assert enriched_child["effective_rank_structure_id"] is None
    assert enriched_child["rank_structure_inherited"] is False
    assert enriched_child["effective_rank_structure_name"] is None
