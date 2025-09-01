import sqlite3, json
import pathlib
for db in pathlib.Path('data/incidents').glob('*.db'):
    con = sqlite3.connect(str(db))
    cur = con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
    names = [r[0] for r in cur.fetchall()]
    print('DB', db.name, 'tables count', len(names))
    if 'task_narrative' in names:
        cur = con.execute('PRAGMA table_info(task_narrative)')
        cols = [ (r[1], r[2]) for r in cur.fetchall()]
        print(' task_narrative cols:', cols)
        cur = con.execute('SELECT COUNT(*) FROM task_narrative')
        print(' task_narrative rows:', cur.fetchone()[0])
    con.close()
