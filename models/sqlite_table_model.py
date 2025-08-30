from __future__ import annotations

import os
import sqlite3
from typing import Any, List, Sequence, Tuple

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QByteArray


class SqliteTableModel(QAbstractTableModel):
    """
    Generic read-only QAbstractTableModel backed by a SQLite SELECT result.

    - roleNames(): {Qt.UserRole+1+i: b"<column_name>"}
    - data():
        * DisplayRole/EditRole -> cell value at [row][column]
        * custom roles -> column by role name
    - load_query(sql, params=()) loads data and headers with resetModel
    """

    def __init__(self, db_path: str, parent=None) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._headers: List[str] = []
        self._rows: List[Tuple[Any, ...]] = []

    # --- Qt model API ---
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._headers)

    def roleNames(self):  # type: ignore[override]
        return {Qt.UserRole + 1 + i: QByteArray(h.encode()) for i, h in enumerate(self._headers)}

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        if r < 0 or c < 0 or r >= len(self._rows) or c >= len(self._headers):
            return None

        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._rows[r][c]

        # custom role -> resolve to column index
        base = Qt.UserRole + 1
        if role >= base:
            col = role - base
            if 0 <= col < len(self._headers):
                return self._rows[r][col]
        return None

    # --- Loader ---
    def load_query(self, sql: str, params: Sequence[Any] | None = None) -> None:
        params = params or ()
        rows: List[Tuple[Any, ...]] = []
        headers: List[str] = []

        # Resolve db path relative to repo root if needed
        db_path = self._db_path
        if not os.path.isabs(db_path):
            here = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.normpath(os.path.join(here, os.pardir))
            db_path = os.path.join(repo_root, db_path)

        con = None
        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute(sql, tuple(params))
            headers = [d[0] for d in (cur.description or [])]
            for row in cur.fetchall():
                rows.append(tuple(row))
        except sqlite3.Error as e:
            print(f"[SqliteTableModel] load_query error: {e}")
            rows, headers = [], []
        finally:
            try:
                if con:
                    con.close()
            except Exception:
                pass

        self.beginResetModel()
        self._headers = headers
        self._rows = rows
        self.endResetModel()

