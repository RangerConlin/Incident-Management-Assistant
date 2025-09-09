import sqlite3
from pathlib import Path
import sys

db_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'data/incidents/2025-FAIR.db')
print(f"DB: {db_path} exists={db_path.exists()} size={db_path.stat().st_size if db_path.exists() else 0}")
con = sqlite3.connect(str(db_path))
con.row_factory = sqlite3.Row
cur = con.cursor()
print("Tables:")
for (name,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(" -", name)

def try_query(sql, params=()):
    try:
        rows = list(cur.execute(sql, params))
        print(f"OK: {sql} -> {len(rows)} rows")
        return rows
    except Exception as e:
        print(f"ERR: {sql} -> {e}")
        return []

try_query("SELECT COUNT(*) FROM incident_objectives")
rows = try_query("SELECT id, assigned_section, priority, status, customer, due_time FROM incident_objectives ORDER BY id DESC LIMIT 5")
for r in rows:
    print(dict(r))

print("\nincident_objectives schema:")
for r in cur.execute("PRAGMA table_info(incident_objectives)"):
    print(dict(zip(['cid','name','type','notnull','dflt_value','pk'], r)))
con.close()
