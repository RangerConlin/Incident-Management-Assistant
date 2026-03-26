p = r"modules/personnel_role_management/units_organizations/models/repository.py"
s = open(p,'r',encoding='utf-8').read()
s = s.replace('\nconn.execute("CREATE INDEX IF NOT EXISTS idx_ranks_structure_sort', '\n            conn.execute("CREATE INDEX IF NOT EXISTS idx_ranks_structure_sort')
open(p,'w',encoding='utf-8',newline='\n').write(s)
print('OK')
