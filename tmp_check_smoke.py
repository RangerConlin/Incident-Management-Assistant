import os, sqlite3
from modules.logistics.checkin import repository as repo
from utils import incident_context as ic
ic.set_active_incident('X1')
repo.create_or_update_personnel_master({'id':'T1','first_name':'A','last_name':'B'})
repo.copy_personnel_to_incident({'id':'T1','first_name':'A','last_name':'B'})
path = os.path.join(os.environ['CHECKIN_DATA_DIR'],'incidents','X1.db')
with sqlite3.connect(path) as conn:
    print(conn.execute("select status from personnel_incident where id='T1'").fetchone())
print('OK')