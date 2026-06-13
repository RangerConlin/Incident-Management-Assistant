"""
SARApp MongoDB framework verification script.

Safe to run against a live server — does NOT insert records and will NOT
overwrite existing data. The only writes are idempotent index creations.

Usage:
    python shared/sarapp_db/verify_mongo_framework.py

With a specific URI:
    SARAPP_MONGO_URI=mongodb://localhost:27017 python shared/sarapp_db/verify_mongo_framework.py
"""

from __future__ import annotations

import sys
import os

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_shared_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_project_root, _shared_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sarapp_db.mongo.mongo_client import get_mongo_uri, get_client
from sarapp_db.mongo.database_manager import (
    DatabaseManager,
    get_incident_db_name,
    validate_incident_id,
    DB_SYSTEM,
    DB_MASTER,
    DB_INCIDENT_PREFIX,
)
from sarapp_db.mongo.errors import DatabaseConnectionError, InvalidIncidentIdError
from sarapp_db.mongo.indexes import create_incident_indexes, create_master_indexes

# Safe test incident ID — only used to verify DB name construction and index creation.
# No records are inserted.
_TEST_INCIDENT_ID = "dev_framework_check"

_PASS = "  [PASS]"
_FAIL = "  [FAIL]"


def _check(label: str, fn) -> bool:
    try:
        fn()
        print(f"{_PASS}  {label}")
        return True
    except Exception as exc:
        print(f"{_FAIL}  {label}")
        print(f"         {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    print("=" * 60)
    print("SARApp MongoDB Framework Verification")
    print("=" * 60)
    print(f"\nMongoDB URI : {get_mongo_uri()}\n")

    failures = 0

    print("[ Connectivity ]")
    if not _check("ping MongoDB", lambda: get_client().admin.command("ping")):
        print("\nCannot reach MongoDB. Remaining checks skipped.\n")
        return 1

    print("\n[ DatabaseManager ]")
    mgr = DatabaseManager()

    for label, fn in [
        ("is_connected()", lambda: (lambda r: (_ for _ in ()).throw(AssertionError("is_connected() returned False")) if not r else None)(mgr.is_connected())),
        (f"get_system_db() -> {DB_SYSTEM}", lambda: None if mgr.get_system_db().name == DB_SYSTEM else (_ for _ in ()).throw(AssertionError())),
        (f"get_master_db() -> {DB_MASTER}", lambda: None if mgr.get_master_db().name == DB_MASTER else (_ for _ in ()).throw(AssertionError())),
        (f"get_incident_db('{_TEST_INCIDENT_ID}')", lambda: None if mgr.get_incident_db(_TEST_INCIDENT_ID).name == f"{DB_INCIDENT_PREFIX}{_TEST_INCIDENT_ID}" else (_ for _ in ()).throw(AssertionError())),
    ]:
        if not _check(label, fn):
            failures += 1

    print("\n[ Incident ID Validation ]")

    def _valid():
        validate_incident_id("26-T-4301")
        validate_incident_id("dev_framework_check")
        validate_incident_id("2025FAIR")

    def _rejects(value):
        def _fn():
            try:
                validate_incident_id(value)
                raise AssertionError(f"'{value}' was not rejected")
            except InvalidIncidentIdError:
                pass
        return _fn

    for label, fn in [
        ("valid IDs accepted", _valid),
        ("empty ID rejected", _rejects("")),
        ("space in ID rejected", _rejects("my incident")),
        ("slash in ID rejected", _rejects("inc/test")),
        ("dot in ID rejected", _rejects("inc.test")),
    ]:
        if not _check(label, fn):
            failures += 1

    print("\n[ Index Creation — idempotent, no data written ]")
    incident_db = mgr.get_incident_db(_TEST_INCIDENT_ID)
    master_db = mgr.get_master_db()

    for label, fn in [
        (f"incident indexes on '{incident_db.name}'", lambda: create_incident_indexes(incident_db)),
        (f"master indexes on '{master_db.name}'", lambda: create_master_indexes(master_db)),
    ]:
        if not _check(label, fn):
            failures += 1

    print()
    print("=" * 60)
    if failures == 0:
        print("RESULT: All checks passed. Framework is ready.")
    else:
        print(f"RESULT: {failures} check(s) failed. See output above.")
    print("=" * 60)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
