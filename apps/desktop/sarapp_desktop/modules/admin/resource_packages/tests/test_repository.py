"""Desktop-side repository tests for Resource Packages (no Qt, no Mongo)."""
from __future__ import annotations

from modules.admin.resource_packages.data.repository import ApiResourcePackageRepository
from modules.admin.resource_packages.models import (
    MinimumQuantityRequirement,
    PackageResourceRef,
    RequiredPosition,
    ResourcePackage,
)
from utils.api_client import api_client


def _sample_doc(**overrides):
    doc = {
        "id": "pkg-1",
        "name": "Ground Team Alpha",
        "owning_organization": "CAP Squadron 1",
        "resources": [
            {"resource_type": "personnel", "resource_id": 1, "membership": "fixed", "role": "Team Leader"},
            {"resource_type": "vehicle", "resource_id": 2, "membership": "preferred", "role": ""},
        ],
        "required_positions": [{"role": "Ground Team Member", "qualification": "GTM3", "quantity": 2}],
        "minimum_quantities": [{"description": "4 personnel", "resource_kind": "personnel", "minimum_count": 4}],
        "is_active": True,
        "personnel_count": 1,
        "vehicle_count": 1,
    }
    doc.update(overrides)
    return doc


def test_list_packages_round_trip(monkeypatch):
    monkeypatch.setattr(api_client, "get", lambda path, params=None: [_sample_doc()])
    repo = ApiResourcePackageRepository()
    packages = repo.list_packages()
    assert len(packages) == 1
    pkg = packages[0]
    assert pkg.name == "Ground Team Alpha"
    assert pkg.personnel_count == 1
    assert pkg.required_positions[0].quantity == 2
    assert pkg.minimum_quantities[0].minimum_count == 4
    assert pkg.resources_of("personnel")[0].role == "Team Leader"


def test_save_package_sends_combined_membership(monkeypatch):
    sent = {}

    def fake_post(path, json=None):
        sent["path"] = path
        sent["json"] = json
        return _sample_doc()

    monkeypatch.setattr(api_client, "post", fake_post)

    package = ResourcePackage(
        name="Ground Team Alpha",
        resources=[
            PackageResourceRef(resource_type="personnel", resource_id=1, membership="fixed", role="Team Leader"),
            PackageResourceRef(resource_type="vehicle", resource_id=2, membership="preferred"),
            PackageResourceRef(resource_type="equipment", resource_id=3, membership="optional"),
        ],
        required_positions=[RequiredPosition(role="Ground Team Member", qualification="GTM3", quantity=2)],
        minimum_quantities=[MinimumQuantityRequirement(description="4 personnel", minimum_count=4)],
    )
    ApiResourcePackageRepository().save_package(package)

    assert sent["path"] == "/api/resource-packages"
    membership_kinds = {r["membership"] for r in sent["json"]["resources"]}
    assert membership_kinds == {"fixed", "preferred", "optional"}
    assert sent["json"]["required_positions"][0]["role"] == "Ground Team Member"


def test_save_package_with_id_uses_put(monkeypatch):
    calls = {}
    monkeypatch.setattr(api_client, "put", lambda path, json=None: (calls.setdefault("path", path), _sample_doc())[1])
    package = ResourcePackage(id="pkg-1", name="Ground Team Alpha")
    ApiResourcePackageRepository().save_package(package)
    assert calls["path"] == "/api/resource-packages/pkg-1"


def test_duplicate_and_set_active(monkeypatch):
    monkeypatch.setattr(api_client, "post", lambda path: _sample_doc(name="Ground Team Alpha Copy 1"))
    dup = ApiResourcePackageRepository().duplicate_package("pkg-1")
    assert dup.name == "Ground Team Alpha Copy 1"

    monkeypatch.setattr(api_client, "patch", lambda path, json=None: _sample_doc(is_active=False))
    archived = ApiResourcePackageRepository().set_active("pkg-1", False)
    assert archived.is_active is False
