import json
from datetime import datetime
from pathlib import Path

from modules.medical_safety.services.safety_service import SafetyService
from modules.medical_safety.models.safety_models import ICS208, ICS215AItem


def test_safety_db_roundtrip(tmp_path):
    db = tmp_path / "incident.db"
    svc = SafetyService()
    svc.ensure_incident_tables(str(db))

    now = datetime.utcnow().isoformat()
    ics = ICS208(None, 1, "Test", "Msg", now, now)
    svc.save_ics208(str(db), ics)
    fetched = svc.get_ics208(str(db), 1)
    assert fetched and fetched.title == "Test"

    item = ICS215AItem(
        None,
        1,
        None,
        "Terrain",
        "Loose rocks",
        "Wear helmets",
        "High",
        "High",
        "Medium",
        None,
        "Open",
        None,
        None,
        now,
        now,
    )
    item_id = svc.upsert_215a_item(str(db), item)
    items = svc.list_215a_items(str(db), 1)
    assert any(i.id == item_id for i in items)
