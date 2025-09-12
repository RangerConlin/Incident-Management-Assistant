from utils.audit import write_audit, fetch_last_audit_rows
from utils.state import AppState

# Configure test context: no incident, set a user id
AppState.set_active_user_id(99)
AppState.set_active_incident(None)

# Perform a write; this will trigger in-code migration if needed
write_audit("test.event", {"ping": "pong"}, prefer_mission=False)

row = fetch_last_audit_rows(1)[0]
print(dict(row))

