"""
SARApp local -> cloud MongoDB sync.

Mirrors sarapp_master and every sarapp_incident_<id> database from a local
MongoDB instance to the cloud server's MongoDB instance. Destination
collections are dropped and reinserted from the source on every run (full
replace), so the cloud DB ends up an exact copy of local for every database
this script touches.

URI resolution:
    Source (local):  SARAPP_MONGO_URI        (falls back to mongodb://localhost:27017)
    Destination:      SARAPP_CLOUD_MONGO_URI  (required, no default — refuses to run without it)

Usage:
    SARAPP_CLOUD_MONGO_URI=mongodb://user:pass@cloud-host:27017 python data/db/sync_local_to_cloud.py
"""

from __future__ import annotations

import os
import sys

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError

_SOURCE_URI_ENV = "SARAPP_MONGO_URI"
_DEST_URI_ENV = "SARAPP_CLOUD_MONGO_URI"
_DEFAULT_SOURCE_URI = "mongodb://localhost:27017"

_MASTER_DB = "sarapp_master"
_INCIDENT_PREFIX = "sarapp_incident_"
_SYSTEM_DBS = {"admin", "local", "config", "sarapp_system"}


def _connect(uri: str, label: str) -> MongoClient:
    try:
        client: MongoClient = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client
    except (ConnectionFailure, ConfigurationError) as exc:
        print(f"ERROR: cannot connect to {label} MongoDB at '{uri}': {exc}")
        sys.exit(1)


def _sync_database(source_client: MongoClient, dest_client: MongoClient, db_name: str) -> None:
    source_db = source_client[db_name]
    dest_db = dest_client[db_name]

    collection_names = source_db.list_collection_names()
    if not collection_names:
        print(f"  {db_name}: no collections, skipping")
        return

    for coll_name in collection_names:
        docs = list(source_db[coll_name].find({}))
        dest_db[coll_name].drop()
        if docs:
            dest_db[coll_name].insert_many(docs)
        print(f"  {db_name}.{coll_name}: {len(docs)} document(s)")


def main() -> int:
    source_uri = os.environ.get(_SOURCE_URI_ENV, "").strip() or _DEFAULT_SOURCE_URI
    dest_uri = os.environ.get(_DEST_URI_ENV, "").strip()

    if not dest_uri:
        print(f"ERROR: {_DEST_URI_ENV} is not set. Refusing to run without an explicit cloud target.")
        return 1

    print("=" * 65)
    print("SARApp local -> cloud MongoDB sync")
    print("=" * 65)
    print(f"Source (local): {source_uri}")
    print(f"Destination (cloud): {dest_uri}")

    source_client = _connect(source_uri, "source")
    dest_client = _connect(dest_uri, "destination")

    db_names = [
        name for name in source_client.list_database_names()
        if name not in _SYSTEM_DBS and (name == _MASTER_DB or name.startswith(_INCIDENT_PREFIX))
    ]

    if not db_names:
        print("No master or incident databases found locally. Nothing to sync.")
        return 0

    for db_name in sorted(db_names):
        print(f"\n--- {db_name} ---")
        _sync_database(source_client, dest_client, db_name)

    print("\nSync complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
