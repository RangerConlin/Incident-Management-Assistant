"""Compatibility shim: provides get_db() backed by the SARApp MongoClient."""

from __future__ import annotations

from pymongo.database import Database

from sarapp_db.mongo.mongo_client import get_client


def get_db(db_name: str) -> Database:
    return get_client()[db_name]
