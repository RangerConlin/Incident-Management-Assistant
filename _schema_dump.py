import sqlite3
con=sqlite3.connect('data/master.db')
cur=con.cursor()
for name,sql in cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table';").fetchall():
    print(name)
    print(sql or '')
con.close()
