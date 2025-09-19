-- Resource Requests schema initialisation.
-- The script is idempotent; it will only create tables that do not yet exist.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS resource_requests (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    title TEXT NOT NULL,
    requesting_section TEXT NOT NULL,
    needed_by_utc TEXT,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    created_utc TEXT NOT NULL,
    created_by_id TEXT NOT NULL,
    last_updated_utc TEXT NOT NULL,
    justification TEXT,
    delivery_location TEXT,
    comms_requirements TEXT,
    links TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS resource_request_items (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref_id TEXT,
    description TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    special_instructions TEXT,
    FOREIGN KEY (request_id) REFERENCES resource_requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resource_request_approvals (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    note TEXT,
    ts_utc TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES resource_requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resource_fulfillments (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    supplier_id TEXT,
    assigned_team_id TEXT,
    assigned_vehicle_id TEXT,
    eta_utc TEXT,
    status TEXT NOT NULL,
    note TEXT,
    ts_utc TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES resource_requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor_id TEXT,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    ts_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_status ON resource_requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_priority ON resource_requests(priority);
CREATE INDEX IF NOT EXISTS idx_requests_needed_by ON resource_requests(needed_by_utc);
CREATE INDEX IF NOT EXISTS idx_items_request ON resource_request_items(request_id);
CREATE INDEX IF NOT EXISTS idx_approvals_request ON resource_request_approvals(request_id);
CREATE INDEX IF NOT EXISTS idx_fulfillments_request ON resource_fulfillments(request_id);
