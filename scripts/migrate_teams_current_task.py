#!/usr/bin/env python3
"""Add teams.current_task_id to all incident DBs and optionally backfill.

Backfill heuristic:
  - For each team, choose the most recent task_teams row where time_cleared IS NULL;
    if none, choose the most recent task_teams row (by id) and set as current.

Usage:
  python scripts/migrate_teams_current_task.py --apply [--backfill]
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
        cur = conn.execute("PRAGMA table_info(teams)")
        cols = {row[1] for row in cur.fetchall()}
        if "current_task_id" in cols and not backfill and not apply:
            msgs.append("ok: already has current_task_id")
            return msgs
        if apply and "current_task_id" not in cols:
            conn.execute("ALTER TABLE teams ADD COLUMN current_task_id INTEGER")
            msgs.append("added column: current_task_id INTEGER")
        if backfill:
            # Set to latest active assignment if present, else latest assignment
            try:
                rows = conn.execute("SELECT id FROM teams").fetchall()
                for (team_id,) in rows:
                    active = conn.execute(
                        "SELECT task_id FROM task_teams WHERE teamid=? AND time_cleared IS NULL ORDER BY id DESC LIMIT 1",
                        (team_id,),
                    ).fetchone()
                    if active:
                        conn.execute("UPDATE teams SET current_task_id=? WHERE id=?", (active[0], team_id))
                        continue
                    last = conn.execute(
                        "SELECT task_id FROM task_teams WHERE teamid=? ORDER BY id DESC LIMIT 1",
                        (team_id,),
                    ).fetchone()
                    if last:
                        conn.execute("UPDATE teams SET current_task_id=? WHERE id=?", (last[0], team_id))
                msgs.append("backfilled current_task_id from task_teams")
            except sqlite3.Error as e:
                msgs.append(f"backfill error: {e}")
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

