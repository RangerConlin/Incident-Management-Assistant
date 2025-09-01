#!/usr/bin/env python3
"""Add teams.needs_attention (boolean) to all incident DBs.

By default, runs in dry-run mode and prints what would change.
Pass --apply to execute ALTER TABLE statements.

Notes:
- SQLite does not have a native BOOLEAN type; we use BOOLEAN with DEFAULT 0,
  which stores values as 0/1 integers under the hood.

Usage examples:
  - Dry run (default):
      python scripts/migrate_teams_needs_attention.py

  - Apply changes to all DBs under data/incidents:
      python scripts/migrate_teams_needs_attention.py --apply

  - Also backfill NULL values to 0 (false):
      python scripts/migrate_teams_needs_attention.py --apply --backfill

  - Target a subset of DBs via glob:
      python scripts/migrate_teams_needs_attention.py --apply --glob "data/incidents/25-*.db"
"""
from __future__ import annotations

import argparse
import glob
import os
import sqlite3


def has_table(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def table_columns(conn: sqlite3.Connection, name: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({name})")
    return {row[1] for row in cur.fetchall()}


def migrate_db(path: str, apply: bool, backfill: bool) -> tuple[bool, list[str]]:
    """Migrate a single DB. Returns (changed, messages)."""
    msgs: list[str] = []
    changed = False
    try:
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA busy_timeout=3000")
        except Exception:
            pass
        if not has_table(conn, "teams"):
            msgs.append("- skip: no teams table")
            return changed, msgs

        cols = table_columns(conn, "teams")
        to_add: list[tuple[str, str]] = []
        if "needs_attention" not in cols:
            # Use BOOLEAN with DEFAULT 0 for clarity; SQLite stores as 0/1
            to_add.append(("needs_attention", "BOOLEAN DEFAULT 0"))

        if not to_add and not backfill:
            msgs.append("- ok: already up to date")
            return changed, msgs

        if apply:
            for col, typ in to_add:
                conn.execute(f"ALTER TABLE teams ADD COLUMN {col} {typ}")
                msgs.append(f"- added column: {col} {typ}")
                changed = True
            if backfill:
                conn.execute(
                    "UPDATE teams SET needs_attention=0 WHERE needs_attention IS NULL"
                )
                msgs.append("- backfilled NULL needs_attention -> 0 (false)")
                changed = True
            conn.commit()
        else:
            if to_add:
                msgs.append("- would add: " + ", ".join([f"{c} {t}" for c, t in to_add]))
            if backfill:
                msgs.append("- would backfill NULL needs_attention -> 0 (false)")
    except sqlite3.Error as e:
        msgs.append(f"! sqlite error: {e}")
    except Exception as e:
        msgs.append(f"! error: {e}")
    finally:
        try:
            conn.close()  # type: ignore[has-type]
        except Exception:
            pass
    return changed, msgs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=os.path.join("data", "incidents", "*.db"), help="Glob for incident DBs")
    ap.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    ap.add_argument("--backfill", action="store_true", help="Backfill NULL needs_attention to 0 (false)")
    args = ap.parse_args()

    paths = sorted(glob.glob(args.glob))
    if not paths:
        print(f"No databases matched: {args.glob}")
        return

    print(f"Scanning {len(paths)} database(s) -> {('apply' if args.apply else 'dry-run')}\n")
    total_changed = 0
    for p in paths:
        rel = os.path.relpath(p)
        changed, msgs = migrate_db(p, args.apply, args.backfill)
        status = "UPDATED" if changed else "OK"
        print(f"[{status}] {rel}")
        for m in msgs:
            print("   ", m)
    print("\nDone.")


if __name__ == "__main__":
    main()

