"""Password enrollment + JWT login for the web client (see auth_sessions.py).

Covers: /password/set requires an existing personnel record, succeeds once,
and refuses a second attempt on the same account; /login rejects an unknown
username or wrong password and otherwise returns a valid, decodable token
tied to the right person_record.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("SARAPP_JWT_SECRET", "test-secret-for-auth-password-login")

import jwt
from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.api.routers import auth_sessions
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db


PERSON_RECORD = 9001
PERSON_ID = "test-auth-9001"
USERNAME = "test-auth-9001"


def _personnel_col():
    return get_master_db()[MasterCollections.PERSONNEL]


def _users_col():
    return get_master_db()[MasterCollections.USERS]


def _sessions_col():
    return get_master_db()[MasterCollections.USER_SESSIONS]


def _clear():
    _personnel_col().delete_many({"person_record": PERSON_RECORD})
    _users_col().delete_many({"user_id": USERNAME})
    _sessions_col().delete_many({"user_id": USERNAME})


def _seed_personnel():
    _personnel_col().insert_one(
        {
            "person_record": PERSON_RECORD,
            "person_id": PERSON_ID,
            "first_name": "Test",
            "last_name": "Auth",
        }
    )


def test_set_password_requires_existing_personnel():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            "/api/auth/password/set",
            json={"username": USERNAME, "password": "a-real-password"},
        )
    assert res.status_code == 404
    _clear()


def test_set_password_then_login_round_trip():
    _clear()
    _seed_personnel()
    app = create_app()
    with TestClient(app) as client:
        set_res = client.post(
            "/api/auth/password/set",
            json={"username": USERNAME, "password": "a-real-password"},
        )
        assert set_res.status_code == 201
        assert set_res.json() == {"status": "ok", "username": USERNAME}

        login_res = client.post(
            "/api/auth/login",
            json={"username": USERNAME, "password": "a-real-password"},
        )
    assert login_res.status_code == 200
    body = login_res.json()
    assert "token" in body and body["token"]
    assert body["user"]["user_id"] == USERNAME
    assert "password_hash" not in body["user"]
    assert "password_salt" not in body["user"]
    assert body["personnel"]["person_record"] == PERSON_RECORD

    decoded = jwt.decode(
        body["token"], auth_sessions._JWT_SECRET, algorithms=[auth_sessions._JWT_ALGORITHM]
    )
    assert decoded["sub"] == USERNAME
    assert decoded["person_record"] == PERSON_RECORD
    _clear()


def test_set_password_twice_is_conflict():
    _clear()
    _seed_personnel()
    app = create_app()
    with TestClient(app) as client:
        first = client.post(
            "/api/auth/password/set",
            json={"username": USERNAME, "password": "a-real-password"},
        )
        assert first.status_code == 201
        second = client.post(
            "/api/auth/password/set",
            json={"username": USERNAME, "password": "a-different-password"},
        )
    assert second.status_code == 409
    _clear()


def test_login_wrong_password_is_unauthorized():
    _clear()
    _seed_personnel()
    app = create_app()
    with TestClient(app) as client:
        client.post(
            "/api/auth/password/set",
            json={"username": USERNAME, "password": "a-real-password"},
        )
        res = client.post(
            "/api/auth/login",
            json={"username": USERNAME, "password": "not-the-password"},
        )
    assert res.status_code == 401
    _clear()


def test_login_unknown_username_is_unauthorized():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            "/api/auth/login",
            json={"username": "no-such-user", "password": "whatever"},
        )
    assert res.status_code == 401
    _clear()
