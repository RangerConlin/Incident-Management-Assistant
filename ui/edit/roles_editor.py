from __future__ import annotations

import sqlite3
from typing import Any

from PySide6.QtWidgets import QLineEdit

from .base_dialog import BaseEditDialog
from models import database


class RolesAdapter:
    """Data access layer for the ``roles`` table in the master database."""

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self.conn = conn or database.get_connection()
        self.conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                module_access TEXT,
                description TEXT,
                short_name TEXT UNIQUE,
                module_hint TEXT
            )
            """
        )
        self.conn.commit()

    # CRUD --------------------------------------------------------------
    def list(self) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, short_name AS code, name, description AS category FROM roles ORDER BY id"
        )
        return [dict(row) for row in cur.fetchall()]

    def create(self, payload: dict[str, Any]) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO roles (short_name, name, description) VALUES (?, ?, ?)",
            (payload.get("code"), payload.get("name"), payload.get("category")),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update(self, role_id: int, payload: dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE roles SET short_name=?, name=?, description=? WHERE id=?",
            (
                payload.get("code"),
                payload.get("name"),
                payload.get("category"),
                role_id,
            ),
        )
        self.conn.commit()

    def delete(self, role_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM roles WHERE id=?", (role_id,))
        self.conn.commit()


class RolesEditor(BaseEditDialog):
    """QtWidgets editor for user roles."""

    def __init__(self, db_conn: sqlite3.Connection | None = None, parent=None):
        super().__init__("Roles", "Manage user roles and permissions", parent)

        self.code_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.category_edit = QLineEdit()
        self.form_layout.addRow("Code", self.code_edit)
        self.form_layout.addRow("Name", self.name_edit)
        self.form_layout.addRow("Category", self.category_edit)

        self.set_columns([("code", "Code"), ("name", "Name"), ("category", "Category")])
        self.set_adapter(RolesAdapter(db_conn))

    # mapping ------------------------------------------------------------
    def _populate_form(self, record: dict[str, Any]) -> None:
        self.code_edit.setText(record.get("code", ""))
        self.name_edit.setText(record.get("name", ""))
        self.category_edit.setText(record.get("category", ""))

    def _collect_form(self) -> dict[str, Any]:
        return {
            "code": self.code_edit.text().strip().upper(),
            "name": self.name_edit.text().strip(),
            "category": self.category_edit.text().strip() or None,
        }
