from pathlib import Path

import pytest

from modules.forms.repositories import MasterFormsRepository
from modules.forms.services import BindingService, InstanceService, RendererService, TemplateService, ValidationService


def test_unified_forms_engine_versioning_audit_finalize_export(tmp_path: Path) -> None:
    master = MasterFormsRepository(tmp_path / "master.db")
    templates = TemplateService(master)
    family = templates.create_family(code="ICS-206", title="Medical Plan", category="medical")
    fields = [{"key": "incident.name", "label": "Incident Name", "field_type": "text", "required": True, "binding_key": "incident.name"}]
    fema = templates.create_template(family_id=family.id, agency="FEMA", code="ICS-206", title="Medical Plan", fields=fields, layout={})
    uscg = templates.create_template(family_id=family.id, agency="USCG", code="ICS-206", title="Medical Plan", fields=fields, layout={})

    fema_v1 = fema["current_version"]["id"]
    uscg_v1 = uscg["current_version"]["id"]
    fema_v2 = templates.create_version(fema["id"], fields=fields + [{"key": "prepared_by.name", "label": "Prepared By", "field_type": "text"}], layout={}, change_summary="add preparer")

    assert fema_v2["id"] != fema_v1
    assert templates.get_template(uscg["id"])["current_version_id"] == uscg_v1

    instances = InstanceService(master, incident_base_dir=tmp_path / "incidents")
    instance = instances.create_instance(incident_id="INC-1", template_version_id=fema_v1, binding_context={"incident": {"name": "North Ridge"}}, created_by="tester")
    assert instance["template_version_id"] == fema_v1
    assert instance["values"]["incident.name"]["value"] == "North Ridge"

    updated = instances.update_values("INC-1", instance["id"], {"incident.name": {"value": "North Ridge Updated", "display_value": "North Ridge Updated", "is_overridden": True, "override_reason": "caller update"}}, "tester")
    assert updated["values"]["incident.name"]["is_overridden"] is True
    assert instances.list_audit("INC-1", instance["id"])

    finalized = instances.finalize("INC-1", instance["id"], "tester")
    assert finalized["status"] == "finalized"
    with pytest.raises(ValueError):
        instances.update_values("INC-1", instance["id"], {"incident.name": "blocked"}, "tester")

    renderer = RendererService(master, output_dir=tmp_path / "exports", incident_base_dir=tmp_path / "incidents")
    summary = renderer.export_instance("INC-1", instance["id"], export_type="summary")
    assert Path(summary["path"]).exists()


def test_binding_missing_and_validation_required() -> None:
    missing = BindingService().resolve("incident.name", {})
    assert missing.error
    results = ValidationService().validate_fields([{"key": "incident.name", "label": "Incident Name", "field_type": "text", "required": True}], {})
    assert results and results[0].blocking
