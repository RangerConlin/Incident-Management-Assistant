from utils.audit import write_audit, fetch_last_audit_rows
from utils.state import AppState

# Configure test context: mission DB and user
AppState.set_active_user_id(7)
AppState.set_active_incident('demo-incident')

write_audit('team.status.change', {'panel':'team','id':123,'old':'Available','new':'Assigned'})
row = fetch_last_audit_rows(1)[0]
print(dict(row))

