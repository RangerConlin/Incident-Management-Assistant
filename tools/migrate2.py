import re
p = r"modules/personnel_role_management/units_organizations/models/repository.py"
s = open(p,'r',encoding='utf-8').read()
needle = 'conn.execute("CREATE INDEX IF NOT EXISTS idx_ranks_structure_sort ON ranks(rank_structure_id, sort_order)")'
pos = s.find(needle)
if pos == -1:
    raise SystemExit('needle not found')
ins = (
    "\n            # Ensure sort_order exists for ranks index\n"
    "            cols = {row[\"name\"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute(\"PRAGMA table_info('ranks')\").fetchall()}\n"
    "            if 'sort_order' not in cols:\n"
    "                conn.execute(\"ALTER TABLE ranks ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0\")\n"
)
s2 = s[:pos] + ins + s[pos:]
open(p,'w',encoding='utf-8',newline='\n').write(s2)
print('OK')
