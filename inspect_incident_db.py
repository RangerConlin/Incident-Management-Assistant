import sqlite3
path='data/incidents/26-T-4301.db'
conn=sqlite3.connect(path)
conn.row_factory=sqlite3.Row
cur=conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables=[r[0] for r in cur.fetchall()]
print('TABLES:', tables)
if 'personnel' in tables:
    cols=conn.execute("PRAGMA table_info(personnel)").fetchall()
    print('PERSONNEL COLUMNS:', [(c[1],c[2]) for c in cols])
    try:
        rows=conn.execute("SELECT * FROM personnel LIMIT 5").fetchall()
        print('SAMPLE:', [dict(r) for r in rows])
    except Exception as e:
        print('SELECT ERROR:', e)
else:
    print('No personnel table')
