import sqlite3
path='data/master.db'
conn=sqlite3.connect(path)
conn.row_factory=sqlite3.Row
cur=conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables=[r[0] for r in cur.fetchall()]
print('TABLES:', tables[:10], '...')
if 'personnel' in tables:
    cols=conn.execute("PRAGMA table_info(personnel)").fetchall()
    print('MASTER PERSONNEL COLUMNS:', [(c[1],c[2]) for c in cols])
    try:
        rows=conn.execute("SELECT id,name,callsign,role,phone FROM personnel LIMIT 3").fetchall()
        print('MASTER SAMPLE:', [tuple(r) for r in rows])
    except Exception as e:
        print('MASTER SELECT ERROR:', e)
else:
    print('No master personnel table')
