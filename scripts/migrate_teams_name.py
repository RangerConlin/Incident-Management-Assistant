#!/usr/bin/env python3
"""Add teams.name to all incident DBs and optionally backfill.

Backfill rule: if name is NULL or empty, set to 'Team <id>'.

Usage:
  python scripts/migrate_teams_name.py --apply [--backfill]
"""
from __future__ import annotations

import argparse
import glob
import os
import sqlite3


def migrate(path: str, apply: bool, backfill: bool) -> list[str]:
    msgs: list[str] = []
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA busy_timeout=3000")
    except Exception:
        pass
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(teams)").fetchall()}
        if apply and "name" not in cols:
            conn.execute("ALTER TABLE teams ADD COLUMN name TEXT")
            msgs.append("added column: name TEXT")
        if backfill:
            conn.execute("UPDATE teams SET name = 'Team ' || id WHERE name IS NULL OR TRIM(name) = ''")
            msgs.append("backfilled team names to 'Team <id>' where blank")
        if apply or backfill:
            conn.commit()
    except sqlite3.Error as e:
        msgs.append(f"sqlite error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return msgs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=os.path.join("data", "incidents", "*.db"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backfill", action="store_true")
    args = ap.parse_args()

    paths = sorted(glob.glob(args.glob))
    if not paths:
        print(f"No databases matched: {args.glob}")
        return
    print(f"Scanning {len(paths)} DB(s) -> {'apply' if args.apply else 'dry-run'}{' + backfill' if args.backfill else ''}\n")
    for p in paths:
        msgs = migrate(p, args.apply, args.backfill)
        print(os.path.relpath(p))
        for m in msgs:
            print("  -", m)
    print("\nDone.")


if __name__ == "__main__":
    main()

