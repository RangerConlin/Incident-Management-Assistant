import sqlite3, json
con = sqlite3.connect('data/master.db')
cur = con.execute('PRAGMA table_info(canned_comm_entries)')
cols = [{'cid':r[0],'name':r[1],'type':r[2],'notnull':r[3],'dflt':r[4],'pk':r[5]} for r in cur.fetchall()]
print(json.dumps(cols, indent=2))
cur = con.execute('SELECT * FROM canned_comm_entries LIMIT 5')
rows = cur.fetchall()
print('ROWS',len(rows))
print([d[0] for d in cur.description])
for r in rows:
    print([str(v) for v in r])
