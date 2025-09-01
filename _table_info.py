import sqlite3
con = sqlite3.connect('data/incidents/2025-FAIR.db')
cur = con.execute('PRAGMA table_info(narrative_entries)')
for r in cur.fetchall():
    print(r)
cur = con.execute('SELECT * FROM narrative_entries LIMIT 3')
cols = [d[0] for d in cur.description]
print('COLUMNS', cols)
for row in cur.fetchall():
    print(tuple(row))
con.close()
