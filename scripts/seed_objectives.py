import sqlite3
from pathlib import Path
import sys
from datetime import datetime

db_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'data/incidents/2025-FAIR.db')
con = sqlite3.connect(str(db_path))
cur = con.cursor()
cnt = cur.execute("SELECT COUNT(*) FROM incident_objectives").fetchone()[0]
if cnt == 0:
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    cur.execute(
        "INSERT INTO incident_objectives (mission_id, description, status, priority, created_by, created_at, customer, assigned_section) VALUES (?,?,?,?,?,?,?,?)",
        (1, 'Establish ICP and safety perimeter', 'Pending', 'Normal', 1, now, 'Public Safety', 'OPS')
    )
    con.commit()
    print("Seeded 1 objective")
else:
    print(f"Already has {cnt} objectives; nothing to seed")
con.close()

