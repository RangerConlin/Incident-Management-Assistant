from __future__ import annotations

import json
from pathlib import Path

from modules.forms_creator.exporting import ExportRequest, ExportRegistry, ExportService, PreparedExport
from modules.forms_creator.exporting.builders import default_registry
from modules.forms_creator.exporting.builders.generic import (
    GENERIC_FORM_IDS,
    GenericFormBuilder,
    generic_form_key,
    generic_form_label,
)
from modules.forms_creator.exporting.builders.ics import (
    Ics203FormBuilder,
    IcsFormBuilder,
    STANDARD_ICS_FORM_IDS,
    ics_form_key,
    ics_form_label,
)
from modules.forms_creator.exporting.builders.intel import (
    Sar135ClueFormBuilder,
    intel_form_key,
)
from modules.forms_creator.exporting.builders.medical import Ics206FormBuilder
from modules.forms_creator.exporting.builders.resource_requests import (
    ResourceRequestFormBuilder,
    register_resource_request_builders,
)
from modules.forms_creator.exporting.builders.task_assignments import (
    TASK_ASSIGNMENT_FORM_IDS,
    TaskAssignmentFormBuilder,
    task_assignment_form_key,
    task_assignment_form_label,
)
from modules.forms_creator.exporting.builders.work_assignments import (
    WorkAssignmentOutputBuilder,
    work_assignment_form_key,
)


class _StaticBuilder:
    def build(self, request: ExportRequest) -> PreparedExport:
        return PreparedExport(
            form_id="test_form",
            output_path=Path("out.pdf"),
            incident_id=request.incident_id,
            extra_data={"target_id": request.target_id},
            metadata={"generated_at": "2026-07-27 12:30:45+00:00"},
        )


def test_export_service_routes_request_to_registered_builder():
    calls = []
    registry = ExportRegistry()
    registry.register("test:form", _StaticBuilder())
    service = ExportService(
        registry,
        generator=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = service.export(
        ExportRequest(
            form_key="test:form",
            target_type="team",
            target_id=3,
            incident_id="INC-1",
        )
    )

    assert result.form_id == "test_form"
    assert result.output_path == Path("out.pdf")
    assert result.generated_at == "2026-07-27 12:30:45+00:00"
    assert calls[0][0][:2] == ("test_form", Path("out.pdf"))
    assert calls[0][1]["incident_id"] == "INC-1"
    assert calls[0][1]["extra_data"] == {"target_id": 3}


def test_work_assignment_builder_prepares_strategy_context(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.work_assignments.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.work_assignments.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.work_assignments.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.work_assignments.api_client.get",
        lambda path: {
            "id": 7,
            "assignment_number": "ST-7",
            "assignment_name": "Ridge Sweep",
            "resources": [
                {
                    "id": 2,
                    "resource_type_text": "Ground Team",
                    "capability_text": "Search",
                    "quantity_required": 2,
                    "quantity_assigned": 1,
                    "quantity_available": 0,
                    "quantity_gap": 1,
                    "assignments": [
                        {"id": 9, "resource_kind": "team", "resource_id": "GT-1", "display_name": "Team 1"}
                    ],
                }
            ],
            "hazards": [{"id": 4, "hazard_type_text": "Heat", "is_resolved": False}],
            "task_links": [{"id": 3, "task_id": 12}],
            "agency_request_links": [{"id": 5, "agency_request_id": 8}],
        },
    )

    prepared = WorkAssignmentOutputBuilder("ICS 215").build(
        ExportRequest(form_key=work_assignment_form_key("ICS 215"), target_id=7)
    )

    assert prepared.form_id == "ics_215"
    assert prepared.incident_id == "INC-1"
    assert prepared.output_path.name == "ST-7_ICS-215_2026-07-27_12-30-45.pdf"
    assert prepared.metadata["output_type"] == "ICS 215"
    assert prepared.extra_data["work_assignment"]["assignment_name"] == "Ridge Sweep"
    assert prepared.extra_data["resource_summary"] == {
        "required": 2,
        "assigned": 1,
        "available": 0,
        "gap": 1,
    }
    assert prepared.extra_data["assigned_resources"][0]["requirement"] == "Ground Team"
    assert prepared.extra_data["hazard_summary"]["open"] == 1


def test_standard_ics_builders_are_registered():
    registry = default_registry()

    for form_id in STANDARD_ICS_FORM_IDS:
        assert registry.get(ics_form_key(form_id))
        assert registry.get(form_id)
        assert registry.get(ics_form_label(form_id))


def test_ics_builder_prepares_incident_scoped_export(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.ics.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.ics.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.ics.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )

    prepared = IcsFormBuilder("ICS 205A").build(
        ExportRequest(
            form_key="ICS 205A",
            target_type="operational_period",
            target_id=2,
            options={"extra_data": {"manual": {"reviewed": True}}},
        )
    )

    assert prepared.form_id == "ics_205a"
    assert prepared.incident_id == "INC-1"
    assert prepared.output_path.name == "ics_205a_operational_period_2_2026-07-27_12-30-45.pdf"
    assert prepared.extra_data["manual"] == {"reviewed": True}
    assert prepared.extra_data["export"]["form_label"] == "ICS 205A"
    assert prepared.extra_data["export"]["target_id"] == 2


def test_ics203_builder_is_registered_as_incident_org_export(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.ics.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.ics.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.ics.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )

    registry = default_registry()
    builder = registry.get("ICS 203")
    prepared = builder.build(ExportRequest(form_key="ICS 203", form_set_id="uscg"))

    assert isinstance(builder, Ics203FormBuilder)
    assert prepared.form_id == "ics_203"
    assert prepared.form_set_id == "uscg"
    assert prepared.output_path.name == "ics_203_2026-07-27_12-30-45.pdf"
    assert prepared.extra_data["export"]["builder_level"] == "ics_203"
    assert prepared.extra_data["export"]["data_domain"] == "incident_organization"
    assert prepared.metadata["builder_level"] == "ics_203"


def test_ics203_variant_row_group_bindings_are_wired():
    root = Path(__file__).resolve().parents[3]
    expected = {
        "uc_commanders": {"name"},
        "org_agency_reps": {"agency", "name"},
    }

    for form_set_id in ("uscg", "ics_canada"):
        mapping_path = root / "forms" / "sets" / form_set_id / "ics_203" / "mapping.json"
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        row_groups = {row["ref"]: row for row in mapping["row_groups"]}

        for ref, required_columns in expected.items():
            columns = set(row_groups[ref]["col_patterns"])
            assert required_columns <= columns
            assert row_groups[ref]["rows_per_page"][0] > 1

        # planning_tech_specialists names and specialties can need different row
        # counts per template (some templates have fewer specialty slots than
        # name slots), so each form set wires them as one or two row_groups
        # covering "name" and "specialty" between them.
        tech_columns = {
            col
            for row in mapping["row_groups"]
            if row["data_key"] == "planning_tech_specialists"
            for col in row["col_patterns"]
        }
        assert {"name", "specialty"} <= tech_columns


def test_ics203_org_branches_bindings_are_wired():
    # uscg's org_branches field-name numbering is regular ({n} per branch), so
    # it uses a row_groups col_pattern; fema and ics_canada have irregular
    # per-branch field naming (see BINDING_PIPELINE.md's ics_203 sections) and
    # use explicit org_branches.<index>.* fields instead. Either mechanism
    # must resolve real data for at least the first branch/division slot.
    root = Path(__file__).resolve().parents[3]

    mapping_path = root / "forms" / "sets" / "uscg" / "ics_203" / "mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    row_groups = {row["ref"]: row for row in mapping["row_groups"]}
    columns = set(row_groups["org_branches"]["col_patterns"])
    assert {
        "name",
        "director_name",
        "deputy_name",
        "divisions.0.name",
        "divisions.0.supervisor_name",
    } <= columns
    assert row_groups["org_branches"]["rows_per_page"][0] > 1

    def _source_key(entry_source):
        if isinstance(entry_source, str):
            return entry_source
        if isinstance(entry_source, dict):
            return str(entry_source.get("key") or "")
        return ""

    for form_set_id in ("fema", "ics_canada"):
        mapping_path = root / "forms" / "sets" / form_set_id / "ics_203" / "mapping.json"
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        explicit_sources = {_source_key(entry.get("source")) for entry in mapping["fields"]}
        assert any(src.startswith("org_branches.0.") for src in explicit_sources)
        assert any(src.startswith("org_branches.0.divisions.0.") for src in explicit_sources)


def test_ics206_builder_is_registered_instead_of_generic():
    registry = default_registry()
    assert isinstance(registry.get("ics_206"), Ics206FormBuilder)
    assert isinstance(registry.get("ICS 206"), Ics206FormBuilder)
    assert isinstance(registry.get(ics_form_key("ics_206")), Ics206FormBuilder)


def test_ics206_builder_prepares_medical_context(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.ics.incident_context.get_active_incident_id",
        lambda: "MED-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.ics.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.medical.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )

    def fake_get(path, params=None):
        assert params == {"op": 2}
        if path.endswith("/aid-stations"):
            return [
                {
                    "id": 1,
                    "name": "Base Medical",
                    "type": "ALS",
                    "contact_frequency": "MED TAC",
                    "location_text": "ICP",
                    "manager_name": "M. Park",
                }
            ]
        if path.endswith("/ambulance-services"):
            return [{"id": 1, "name": "County EMS", "type": "Ground ALS", "phone": "555-0100"}]
        if path.endswith("/hospitals"):
            return [
                {
                    "id": 1,
                    "name": "General Hospital",
                    "address": "100 Main",
                    "phone_er": "555-0200",
                    "ambulance_radio_channel": "MED-1",
                    "helipad": True,
                    "burn_center": False,
                    "level": "II",
                }
            ]
        if path.endswith("/air-ambulance"):
            return [{"id": 1, "name": "Life Flight"}]
        if path.endswith("/comms"):
            return [{"id": 1, "channel": "Med Net"}]
        if path.endswith("/procedures"):
            return {"content": "Call Medical Unit Leader for all injuries."}
        if path.endswith("/signatures"):
            return {"prepared_by": "M. Park", "approved_by": "S. Ortiz", "date": "2026-07-27T12:00:00"}
        raise AssertionError(path)

    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.medical.api_client.get",
        fake_get,
    )

    prepared = Ics206FormBuilder().build(
        ExportRequest(form_key="ics_206", form_set_id="fema", options={"op_period": 2})
    )

    assert prepared.form_id == "ics_206"
    assert prepared.incident_id == "MED-1"
    assert prepared.form_set_id == "fema"
    assert prepared.output_path.name == "ics_206_2026-07-27_12-30-45.pdf"
    assert prepared.extra_data["ics_206_aid_stations"][0]["manager_name"] == "M. Park"
    assert prepared.extra_data["ics_206_aid_stations"][0]["contact_frequency"] == "MED TAC"
    assert prepared.extra_data["ics_206_aid_stations"][0]["paramedics_on_site"] is True
    assert prepared.extra_data["ics_206_ambulance_services"][0]["service_level"] == 2
    assert prepared.extra_data["ics_206_hospitals"][0]["contact_frequency"] == "555-0200 / MED-1"
    assert prepared.extra_data["ics_206_procedures"]["content"].startswith("Call Medical")
    assert prepared.metadata["builder_level"] == "ics_206"
    assert prepared.metadata["op_period"] == 2


def test_ics206_mappings_bind_known_source_fields():
    from pypdf import PdfReader

    root = Path(__file__).resolve().parents[3]
    for form_set_id in ("fema", "ics_canada"):
        form_dir = root / "forms" / "sets" / form_set_id / "ics_206"
        mapping = json.loads((form_dir / "mapping.json").read_text(encoding="utf-8"))
        fields = PdfReader(str(form_dir / "template.pdf")).get_fields() or {}
        leaf_field_names = {
            name
            for name, field in fields.items()
            if field.get("/FT") in {"/Tx", "/Btn", "/Ch"}
        }
        mapped = {
            entry.get("pdf_field")
            for entry in mapping.get("fields", [])
            if entry.get("pdf_field") and entry.get("source")
        }

        assert mapped <= leaf_field_names
        assert leaf_field_names <= mapped


def test_task_assignment_builders_are_registered():
    registry = default_registry()

    for form_id in TASK_ASSIGNMENT_FORM_IDS:
        assert registry.get(task_assignment_form_key(form_id))
        assert registry.get(form_id)
        assert registry.get(task_assignment_form_label(form_id))


def test_sar104_builder_is_registered_instead_of_generic():
    registry = default_registry()
    assert isinstance(registry.get("sar_104"), TaskAssignmentFormBuilder)
    assert isinstance(registry.get("SAR 104"), TaskAssignmentFormBuilder)


def test_capf109_builder_is_registered_instead_of_generic():
    registry = default_registry()
    assert isinstance(registry.get("capf_109"), TaskAssignmentFormBuilder)
    assert isinstance(registry.get("CAPF 109"), TaskAssignmentFormBuilder)


def test_sar104_builder_requires_target_id():
    import pytest

    with pytest.raises(ValueError):
        TaskAssignmentFormBuilder("sar_104").build(ExportRequest(form_key="sar_104"))


def test_sar104_builder_prepares_task_context(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.taskings_repository._build_assignment_export_context",
        lambda task_id, team: {
            "task": {"task_id": "SAR-17"},
            "team": {"leader_name": "J. Rivera"},
        },
    )

    prepared = TaskAssignmentFormBuilder("sar_104").build(
        ExportRequest(form_key="sar_104", target_type="task", target_id=17, options={"team": {"team_id": 7}})
    )

    assert prepared.form_id == "sar_104"
    assert prepared.incident_id == "INC-1"
    assert prepared.form_set_id == "sar"
    assert prepared.output_path.name == "SAR-17_sar_104_2026-07-27_12-30-45.pdf"
    assert prepared.extra_data["task"]["task_id"] == "SAR-17"
    assert prepared.extra_data["team"]["leader_name"] == "J. Rivera"
    assert prepared.metadata["builder_level"] == "sar_104"
    assert prepared.metadata["target_type"] == "task"
    assert prepared.metadata["target_id"] == 17


def test_capf109_builder_prepares_task_context_with_optional_debrief(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.taskings_repository._build_assignment_export_context",
        lambda task_id, team: {
            "task": {"task_id": "CAP-17"},
            "team": {"leader_name": "J. Rivera"},
        },
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.task_assignments.FormDataContext.build_debrief",
        lambda self, debrief_id, incident_id=None: {
            "ground": {
                "clouds": "Clear",
                "precipitation": "None",
            }
        },
    )

    prepared = TaskAssignmentFormBuilder("capf_109").build(
        ExportRequest(
            form_key="capf_109",
            target_type="task",
            target_id=17,
            options={"team": {"team_id": 7}, "debrief_id": 5},
        )
    )

    assert prepared.form_id == "capf_109"
    assert prepared.incident_id == "INC-1"
    assert prepared.form_set_id == "cap"
    assert prepared.output_path.name == "CAP-17_capf_109_2026-07-27_12-30-45.pdf"
    assert prepared.extra_data["task"]["task_id"] == "CAP-17"
    assert prepared.extra_data["debrief"]["ground"]["clouds"] == "Clear"
    assert prepared.metadata["builder_level"] == "capf_109"


def test_sar135_builder_is_registered_instead_of_generic():
    registry = default_registry()
    assert isinstance(registry.get("sar_135"), Sar135ClueFormBuilder)
    assert isinstance(registry.get("SAR 135"), Sar135ClueFormBuilder)
    assert isinstance(registry.get(intel_form_key("sar_135")), Sar135ClueFormBuilder)


def test_sar135_builder_requires_target_id():
    import pytest

    with pytest.raises(ValueError):
        Sar135ClueFormBuilder().build(ExportRequest(form_key="sar_135"))


def test_sar135_builder_prepares_clue_context(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.generic.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.generic.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.intel.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )

    class _Repo:
        def __init__(self, incident_id):
            self.incident_id = incident_id

        def get(self, item_id):
            return {
                "id": item_id,
                "incident_id": self.incident_id,
                "item_type": "Clue",
                "title": "Blue jacket found near creek crossing",
                "confidence": "Probable",
                "urgent_response_needed": True,
                "created_by": "Ops",
                "created_at": "2026-07-27T10:00:00+00:00",
                "location_text": "Fallback location",
                "observations": [
                    {
                        "observed_at": "2026-07-27T12:00:00+00:00",
                        "observer": "A. Patel",
                        "source_team": "Team 4",
                        "summary": "Jacket is dry and appears recently placed.",
                        "location_text": "Creek crossing north bank",
                    }
                ],
            }

        def list(self, **kwargs):
            assert kwargs == {"item_type": "Clue", "include_deleted": True}
            return [
                {
                    "id": "older-clue",
                    "item_type": "Clue",
                    "created_at": "2026-07-27T09:00:00+00:00",
                },
                self.get("clue-1"),
            ]

    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.intel.IntelItemsRepository",
        _Repo,
    )

    prepared = Sar135ClueFormBuilder().build(
        ExportRequest(
            form_key="sar_135",
            target_id="clue-1",
            options={"extra_data": {"sar_135": {"action": {"collect": True}}}},
        )
    )

    assert prepared.form_id == "sar_135"
    assert prepared.incident_id == "INC-1"
    assert prepared.form_set_id == "sar"
    assert prepared.output_path.name == "sar_135_intel_item_clue-1_2026-07-27_12-30-45.pdf"
    assert prepared.extra_data["sar_135"]["clue_id"] == "C-002"
    assert prepared.extra_data["sar_135"]["found_by"] == "Team 4"
    assert prepared.extra_data["sar_135"]["located_by"] == "A. Patel"
    assert "\n\nObservation 07/27/26" in prepared.extra_data["sar_135"]["description_display"]
    assert prepared.extra_data["sar_135"]["description_lines"][0].startswith(
        "Blue jacket found near creek crossing"
    )
    assert "" in prepared.extra_data["sar_135"]["description_lines"]
    assert any(
        line.startswith("Observation 07/27/26")
        for line in prepared.extra_data["sar_135"]["description_lines"]
    )
    assert prepared.extra_data["sar_135"]["urgent_response_needed"] is True
    assert prepared.extra_data["sar_135"]["information_only"] is False
    assert prepared.extra_data["sar_135"]["confidence"]["probably_good"] is True
    assert prepared.extra_data["sar_135"]["action"]["collect"] is True
    assert prepared.extra_data["sar_135"]["action"]["disregard"] is False
    assert prepared.extra_data["clues"][0]["location"] == "Creek crossing north bank"
    assert prepared.metadata["builder_level"] == "sar_135"
    assert prepared.metadata["data_domain"] == "intel_clue"


def test_sar135_mapping_binds_every_leaf_field():
    from pypdf import PdfReader

    root = Path(__file__).resolve().parents[3]
    form_dir = root / "forms" / "sets" / "sar" / "sar_135"
    mapping = json.loads((form_dir / "mapping.json").read_text(encoding="utf-8"))
    fields = PdfReader(str(form_dir / "template.pdf")).get_fields() or {}
    leaf_field_names = {name for name, field in fields.items() if field.get("/FT") is not None}
    mapped = {
        entry.get("pdf_field")
        for entry in mapping.get("fields", [])
        if entry.get("pdf_field") and entry.get("source")
    }

    assert len(leaf_field_names) == 41
    assert leaf_field_names <= mapped


def test_sar135_mapping_uses_template_checkbox_state():
    from pypdf import PdfReader

    root = Path(__file__).resolve().parents[3]
    form_dir = root / "forms" / "sets" / "sar" / "sar_135"
    mapping = json.loads((form_dir / "mapping.json").read_text(encoding="utf-8"))
    fields = PdfReader(str(form_dir / "template.pdf")).get_fields() or {}
    checkbox_names = {name for name, field in fields.items() if field.get("/FT") == "/Btn"}

    for entry in mapping.get("fields", []):
        if entry.get("pdf_field") not in checkbox_names:
            continue
        source = entry.get("source")
        assert isinstance(source, dict)
        assert source.get("checkbox") is True
        assert source.get("checked_value") == "/On"


def test_generic_builders_are_registered_for_remaining_forms():
    registry = default_registry()

    for form_id in GENERIC_FORM_IDS:
        assert registry.get(generic_form_key(form_id))
        assert registry.get(form_id)
        assert registry.get(generic_form_label(form_id))


def test_generic_builder_prepares_fallback_export(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.generic.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.generic.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.generic.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )

    prepared = GenericFormBuilder("SAR 125").build(
        ExportRequest(
            form_key="SAR 125",
            target_type="team",
            target_id=3,
            options={"extra_data": {"manual": {"checked": True}}},
        )
    )

    assert prepared.form_id == "sar_125"
    assert prepared.output_path.name == "sar_125_team_3_2026-07-27_12-30-45.pdf"
    assert prepared.extra_data["manual"] == {"checked": True}
    assert prepared.extra_data["export"]["form_label"] == "SAR 125"
    assert prepared.extra_data["export"]["builder_level"] == "generic"


def test_resource_request_builder_is_registered_instead_of_generic():
    registry = default_registry()
    assert isinstance(registry.get("ics_213rr"), ResourceRequestFormBuilder)
    assert isinstance(registry.get("ICS 213RR"), ResourceRequestFormBuilder)
    assert isinstance(registry.get(ics_form_key("ics_213rr")), ResourceRequestFormBuilder)


def test_resource_request_builder_requires_target_id():
    import pytest

    with pytest.raises(ValueError):
        ResourceRequestFormBuilder().build(ExportRequest(form_key="ics_213rr"))


def test_resource_request_builder_prepares_export_context(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.generic.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.generic.incident_context.get_active_incident_paths",
        lambda: type("Paths", (), {"forms_generated": tmp_path})(),
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.resource_requests.utcnow_seconds",
        lambda: "2026-07-27 12:30:45+00:00",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.resource_requests.api_client.get",
        lambda path: {
            "id": "rr-00000042",
            "incident_id": "INC-1",
            "title": "Need water pumps",
            "requesting_section": "Operations",
            "priority": "IMMEDIATE",
            "status": "SUBMITTED",
            "created_utc": "2026-07-27T12:00:00Z",
            "needed_by_utc": "2026-07-27T18:00:00Z",
            "delivery_location": "Base Camp",
            "justification": "Flooding in sector 4",
            "items": [
                {"id": "i1", "kind": "EQUIPMENT", "description": "Trash pump", "quantity": 2, "unit": "each"},
            ],
        },
    )

    prepared = ResourceRequestFormBuilder().build(
        ExportRequest(form_key="ics_213rr", target_id="rr-00000042")
    )

    assert prepared.form_id == "ics_213rr"
    assert prepared.incident_id == "INC-1"
    assert prepared.output_path.name == "ics_213rr_resource_request_rr-00000042_2026-07-27_12-30-45.pdf"
    assert prepared.extra_data["resource_request"]["request_number"] == "RR-00000042"
    assert prepared.extra_data["resource_request"]["priority"] == "IMMEDIATE"
    assert prepared.extra_data["resource_request"]["delivery_location"] == "Base Camp"
    assert prepared.extra_data["resource_request_items"][0]["description"] == "Trash pump"
    assert prepared.metadata["data_domain"] == "resource_request"


def test_resource_request_builder_raises_when_request_missing(monkeypatch):
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.generic.incident_context.get_active_incident_id",
        lambda: "INC-1",
    )
    monkeypatch.setattr(
        "modules.forms_creator.exporting.builders.resource_requests.api_client.get",
        lambda path: None,
    )

    import pytest

    with pytest.raises(RuntimeError):
        ResourceRequestFormBuilder().build(
            ExportRequest(form_key="ics_213rr", target_id="missing")
        )
