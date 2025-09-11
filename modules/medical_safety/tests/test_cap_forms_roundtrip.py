from datetime import datetime
from pathlib import Path

from modules.medical_safety.services.cap_forms_service import CapFormsService


def test_cap_forms_roundtrip(tmp_path):
    master_db = tmp_path / "master.db"
    incident_db = tmp_path / "incident.db"
    seed_dir = Path(__file__).resolve().parents[1] / "data" / "master_seed"

    svc = CapFormsService(master_db_path=str(master_db))
    svc.seed_cap_templates_from_master(str(seed_dir))
    templates = svc.list_cap_templates()
    assert templates

    svc.ensure_incident_tables(str(incident_db))
    now = datetime.utcnow().isoformat()
    form_id = svc.create_cap_instance(
        str(incident_db), templates[0].id, {"title": "Test", "date": now}, created_utc=now
    )
    svc.validate_cap_instance(str(incident_db), form_id)
    out_pdf = tmp_path / "form.pdf"
    svc.render_cap_instance_pdf(str(incident_db), form_id, str(out_pdf))
    assert out_pdf.exists()
