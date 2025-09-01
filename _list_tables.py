import sqlite3
con = sqlite3.connect('data/incidents/2025-FAIR.db')
cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for (n,) in cur.fetchall():
    print(n)
con.close()
