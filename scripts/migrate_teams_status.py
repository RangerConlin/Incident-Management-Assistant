#!/usr/bin/env python3
"""Add team-level status columns to all incident DBs.

By default, runs in dry-run mode and prints what would change.
Pass --apply to execute ALTER TABLE statements.

Usage examples:
  - Dry run (default):
      python scripts/migrate_teams_status.py

  - Apply changes to all DBs under data/incidents:
      python scripts/migrate_teams_status.py --apply

  - Also backfill status to 'Available' where NULL:
      python scripts/migrate_teams_status.py --apply --backfill

  - Target a subset of DBs via glob:
      python scripts/migrate_teams_status.py --apply --glob "data/incidents/25-*.db"
"""
from __future__ import annotations

import argparse
import glob
import os
import sqlite3
from datetime import datetime


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
        if "status" not in cols:
            to_add.append(("status", "TEXT"))
        if "status_updated" not in cols:
            to_add.append(("status_updated", "TEXT"))

        if not to_add and not backfill:
            msgs.append("- ok: already up to date")
            return changed, msgs

        if apply:
            for col, typ in to_add:
                conn.execute(f"ALTER TABLE teams ADD COLUMN {col} {typ}")
                msgs.append(f"- added column: {col} {typ}")
                changed = True
            if backfill:
                now = datetime.utcnow().isoformat()
                # Only backfill rows where status IS NULL
                conn.execute(
                    "UPDATE teams SET status='Available', status_updated=? WHERE status IS NULL",
                    (now,),
                )
                msgs.append("- backfilled NULL status -> 'Available'")
                changed = True
            conn.commit()
        else:
            if to_add:
                msgs.append("- would add: " + ", ".join([f"{c} {t}" for c, t in to_add]))
            if backfill:
                msgs.append("- would backfill NULL status -> 'Available'")
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
    ap.add_argument("--backfill", action="store_true", help="Backfill NULL status to 'Available'")
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

