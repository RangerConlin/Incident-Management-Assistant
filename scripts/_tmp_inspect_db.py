import sqlite3, sys

db = sys.argv[1] if len(sys.argv) > 1 else 'data/incidents/26-T-4301.db'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
print('DB:', db)
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print('TABLES:', ', '.join(tables))
for t in tables:
    info = conn.execute(f"PRAGMA table_info({t})").fetchall()
    cols = [f"{c[1]} [{c[2]}]" for c in info]
    print(f"\n-- {t} --\n" + "\n".join(cols))

print('\nSamples:')
for t in ['teams','tasks','team_tasks','assignments','task_assignments','ops_tasks','mission_tasks']:
    if t in tables:
        rows = conn.execute(f"SELECT * FROM {t} LIMIT 5").fetchall()
        print(f"\n{t}: {len(rows)} rows")
        for r in rows:
            print(dict(r))
conn.close()
