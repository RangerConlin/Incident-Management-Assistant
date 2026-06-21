import sys,re
p = r"modules/personnel/units_organizations/models/repository.py"
s = open(p,'r',encoding='utf-8').read()
s = re.sub(r"^\s*CREATE INDEX IF NOT EXISTS idx_ranks_structure_sort ON ranks\(rank_structure_id, sort_order\);\r?\n","", s, flags=re.M)
m = re.search(r"conn\.executescript\(\s*\"\"\".*?\"\"\"\s*\)\s*", s, re.S)
if not m:
    print('ERROR: executescript block not found', file=sys.stderr)
    sys.exit(1)
ins = (
    "\n            # --- Legacy schema migrations ---\n"
    "            # Ensure ranks.rank_structure_id exists before creating index.\n"
    "            cols = {row[\"name\"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute(\"PRAGMA table_info('ranks')\").fetchall()}\n"
    "            if 'rank_structure_id' not in cols:\n"
    "                conn.execute(\"ALTER TABLE ranks ADD COLUMN rank_structure_id INTEGER\")\n"
    "                # Best-effort backfill from older column names if present\n"
    "                legacy_cols = {row[\"name\"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute(\"PRAGMA table_info('ranks')\").fetchall()}\n"
    "                if 'structure_id' in legacy_cols:\n"
    "                    conn.execute(\"UPDATE ranks SET rank_structure_id = structure_id WHERE rank_structure_id IS NULL\")\n"
    "                elif 'rank_structure' in legacy_cols:\n"
    "                    conn.execute(\"UPDATE ranks SET rank_structure_id = rank_structure WHERE rank_structure_id IS NULL\")\n"
    "            conn.execute(\"CREATE INDEX IF NOT EXISTS idx_ranks_structure_sort ON ranks(rank_structure_id, sort_order)\")\n"
)
s2 = s[:m.end()] + ins + s[m.end():]
open(p,'w',encoding='utf-8',newline='\n').write(s2)
