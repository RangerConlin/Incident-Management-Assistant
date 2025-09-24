"""Tests for the SQLite-backed IAP repository."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from app.modules.planning.iap.models.iap_models import FormInstance, IAPPackage
from app.modules.planning.iap.models.repository import IAPRepository


def _build_package() -> IAPPackage:
    start = datetime(2025, 9, 23, 7, 0, 0)
    end = start + timedelta(hours=12)
    package = IAPPackage(
        incident_id="TEST-INC",
        op_number=2,
        op_start=start,
        op_end=end,
    )
    package.forms.append(
        FormInstance(
            form_id="ICS-202",
            title="Incident Objectives",
            op_number=2,
            fields={"incident_name": "Test Incident"},
        )
    )
    package.forms.append(
        FormInstance(
            form_id="ICS-205",
            title="Communications Plan",
            op_number=2,
            fields={"nets": ["TAC-1"]},
        )
    )
    return package


def test_initialize_creates_tables(tmp_path) -> None:
    repo = IAPRepository(tmp_path / "incident.db")
    repo.initialize()

    with sqlite3.connect(tmp_path / "incident.db") as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'iap_%'"
            ).fetchall()
        }
    assert {"iap_packages", "iap_forms", "iap_changelog"}.issubset(tables)


def test_save_and_load_package_roundtrip(tmp_path) -> None:
    repo = IAPRepository(tmp_path / "incident.db")
    package = _build_package()

    repo.save_package(package)
    repo.save_forms(package, package.forms)

    loaded = repo.get_package("TEST-INC", 2)
    assert loaded.incident_id == package.incident_id
    assert loaded.op_number == package.op_number
    assert loaded.status == "draft"
    assert len(loaded.forms) == 2
    assert loaded.get_form("ICS-205").fields["nets"] == ["TAC-1"]


def test_list_packages_orders_by_op(tmp_path) -> None:
    repo = IAPRepository(tmp_path / "incident.db")
    pkg_one = _build_package()
    pkg_one.op_number = 1
    pkg_one.forms = [FormInstance(form_id="ICS-202", title="Objectives", op_number=1)]
    pkg_two = _build_package()
    repo.save_package(pkg_two)
    repo.save_forms(pkg_two, pkg_two.forms)
    repo.save_package(pkg_one)
    repo.save_forms(pkg_one, pkg_one.forms)

    packages = repo.list_packages("TEST-INC")
    assert [pkg.op_number for pkg in packages] == [1, 2]


def test_incident_name_lookup(tmp_path) -> None:
    master_db = tmp_path / "master.db"
    with sqlite3.connect(master_db) as conn:
        conn.execute("CREATE TABLE incidents (id INTEGER PRIMARY KEY, number TEXT, name TEXT)")
        conn.execute("INSERT INTO incidents (number, name) VALUES (?, ?)", ("TEST-INC", "Test Incident"))
        conn.commit()

    repo = IAPRepository(tmp_path / "incident.db", master_db)
    assert repo.incident_name("TEST-INC") == "Test Incident"
    assert repo.incident_name("UNKNOWN") is None
