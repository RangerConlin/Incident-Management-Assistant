-- Initial response toolkit schema
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS initial_hasty_tasks (
    id INTEGER PRIMARY KEY,
    incident_id TEXT NOT NULL,
    area TEXT NOT NULL,
    priority TEXT,
    notes TEXT,
    operations_task_id INTEGER,
    logistics_request_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS initial_reflex_actions (
    id INTEGER PRIMARY KEY,
    incident_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    action TEXT,
    communications_alert_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_initial_hasty_incident ON initial_hasty_tasks(incident_id);
CREATE INDEX IF NOT EXISTS idx_initial_reflex_incident ON initial_reflex_actions(incident_id);
