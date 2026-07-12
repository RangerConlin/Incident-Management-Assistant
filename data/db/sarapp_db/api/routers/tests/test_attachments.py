"""Router-level tests for incident attachment uploads and downloads."""

from __future__ import annotations

import hashlib
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[4]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sarapp_db.api.routers import attachments


class _FakeRepository:
    def __init__(self) -> None:
        self._col = self
        self.docs: list[dict[str, Any]] = []

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            value = doc.get(key)
            if isinstance(expected, dict):
                if "$exists" in expected and (key in doc) is not expected["$exists"]:
                    return False
                if "$ne" in expected and value == expected["$ne"]:
                    return False
                continue
            if value != expected:
                return False
        return True

    def find_one(self, query: dict[str, Any], sort: list[tuple[str, int]] | None = None) -> dict[str, Any] | None:
        matches = [doc for doc in self.docs if self._matches(doc, query)]
        if not matches:
            return None
        if sort:
            key, direction = sort[0]
            matches.sort(key=lambda doc: doc.get(key, 0), reverse=direction < 0)
        return dict(matches[0])

    def insert_one(self, doc: dict[str, Any]) -> dict[str, Any]:
        stored = dict(doc)
        stored["_id"] = ObjectId()
        self.docs.append(stored)
        return dict(stored)

    def find_many(
        self,
        query: dict[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
    ) -> list[dict[str, Any]]:
        matches = [doc for doc in self.docs if self._matches(doc, query or {})]
        for key, direction in reversed(sort or []):
            matches.sort(key=lambda doc: doc.get(key, ""), reverse=direction < 0)
        return [dict(doc) for doc in matches]

    def update_one(self, doc_id: ObjectId, updates: dict[str, Any]) -> dict[str, Any]:
        for doc in self.docs:
            if doc.get("_id") == doc_id:
                doc.update(updates)
                return dict(doc)
        raise KeyError(doc_id)


class _FakeGridFS:
    def __init__(self) -> None:
        self.files: dict[ObjectId, bytes] = {}

    def put(self, data: bytes, **_: Any) -> ObjectId:
        file_id = ObjectId()
        self.files[file_id] = data
        return file_id

    def get(self, file_id: ObjectId) -> BytesIO:
        return BytesIO(self.files[file_id])

    def delete(self, file_id: ObjectId) -> None:
        del self.files[file_id]


def _client(monkeypatch):
    repo = _FakeRepository()
    gridfs = _FakeGridFS()
    monkeypatch.setattr(attachments, "_repo", lambda _incident_id: repo)
    monkeypatch.setattr(attachments, "_fs", lambda _incident_id: gridfs)

    app = FastAPI()
    app.include_router(attachments.router, prefix="/api")
    return TestClient(app), repo, gridfs


def test_upload_list_download_and_soft_delete_attachment(monkeypatch):
    client, _repo, gridfs = _client(monkeypatch)
    content = b"%PDF-1.7\nassignment packet"

    created = client.post(
        "/api/incidents/INC-1/attachments",
        data={
            "owner_type": "task",
            "owner_id": "104",
            "category": "form-export",
            "uploaded_by": "7",
            "description": "SAR 104",
        },
        files={"file": ("sar-104.pdf", content, "application/pdf")},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["id"] == 1
    assert body["attachment_id"] == "INC-1-ATT-1"
    assert body["owner_type"] == "task"
    assert body["owner_id"] == "104"
    assert body["filename"] == "sar-104.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["size_bytes"] == len(content)
    assert body["checksum_sha256"] == hashlib.sha256(content).hexdigest()
    assert "_id" not in body
    assert len(gridfs.files) == 1

    listed = client.get(
        "/api/incidents/INC-1/attachments",
        params={"owner_type": "task", "owner_id": "104"},
    )
    assert listed.status_code == 200
    assert [item["attachment_id"] for item in listed.json()] == ["INC-1-ATT-1"]

    downloaded = client.get("/api/incidents/INC-1/attachments/INC-1-ATT-1/download")
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert "sar-104.pdf" in downloaded.headers["content-disposition"]

    deleted = client.delete("/api/incidents/INC-1/attachments/1")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    assert client.get("/api/incidents/INC-1/attachments/1").status_code == 404
    assert client.get("/api/incidents/INC-1/attachments").json() == []
    deleted_items = client.get(
        "/api/incidents/INC-1/attachments",
        params={"include_deleted": True},
    ).json()
    assert deleted_items[0]["deleted"] is True
    assert len(gridfs.files) == 1


def test_delete_attachment_with_purge_removes_gridfs_file(monkeypatch):
    client, _repo, gridfs = _client(monkeypatch)

    created = client.post(
        "/api/incidents/INC-1/attachments",
        data={"owner_type": "iap", "owner_id": "2"},
        files={"file": ("iap.pdf", b"iap packet", "application/pdf")},
    )
    assert created.status_code == 201
    assert len(gridfs.files) == 1

    deleted = client.delete(
        "/api/incidents/INC-1/attachments/1",
        params={"purge_file": True},
    )

    assert deleted.status_code == 200
    assert gridfs.files == {}
