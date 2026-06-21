from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DB = ROOT / "data" / "db"
if str(DATA_DB) not in sys.path:
    sys.path.insert(0, str(DATA_DB))


def test_sarapp_api_app_registers_migrated_routers() -> None:
    from sarapp_db.api.app import create_app

    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/api/resource-types" in paths
    assert "/api/hazard-types" in paths
    assert "/api/objectives" in paths
    assert "/api/incidents/{incident_id}/org/positions" in paths
    assert "/api/lookup/task-types" in paths
    assert "/api/comms/master-channels" in paths
    assert "/api/incidents/{incident_id}/comms-log" in paths
    assert "/api/safety/reports" in paths
    assert "/api/safety/orm/form" in paths
    assert "/api/incidents/{incident_id}/planned/{tool}" in paths
