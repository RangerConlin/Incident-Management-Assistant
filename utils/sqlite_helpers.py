"""SQLite helpers for schema management and upserts.

These utilities wrap the project's `utils.db` connection helpers and
provide a small set of convenience functions: enabling foreign keys,
executing schema scripts, and performing simple UPSERTs by unique key.

All helpers default to operating on the master database, but an explicit
`sqlite3.Connection` can be passed to operate on another database.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterable, Mapping, Any

from .db import get_master_conn


def enable_foreign_keys(conn: sqlite3.Connection) -> None:
    """Ensure foreign key enforcement is enabled for the connection."""
    conn.execute("PRAGMA foreign_keys = ON;")


def exec_script(conn: sqlite3.Connection, sql: str) -> None:
    """Execute a SQL script (multiple statements)."""
    conn.executescript(sql)


def upsert(
    conn: sqlite3.Connection,
    table: str,
    key_columns: Iterable[str],
    values: Mapping[str, Any],
) -> None:
    """Perform a simple UPSERT by `key_columns`.

    The function constructs an INSERT ... ON CONFLICT (...) DO UPDATE SET ...
    statement. Callers are responsible for ensuring a UNIQUE constraint exists
    on the key columns.
    """
    cols = list(values.keys())
    placeholders = ", ".join(["?" for _ in cols])
    # Never update primary key 'id' in upsert to avoid FK churn
    update_cols = [c for c in cols if c not in key_columns and c != "id"]
    assignments = ", ".join([f"{c}=excluded.{c}" for c in update_cols])
    conflict = ", ".join(key_columns)
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({conflict}) DO UPDATE SET {assignments};"
    )
    conn.execute(sql, [values[c] for c in cols])


@contextmanager
def master_cursor() -> Iterable[sqlite3.Cursor]:
    """Context manager yielding a cursor for the master DB with FK ON."""
    conn = get_master_conn()
    try:
        enable_foreign_keys(conn)
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


__all__ = [
    "enable_foreign_keys",
    "exec_script",
    "upsert",
    "master_cursor",
]
