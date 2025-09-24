"""Tests for the autofill scaffolding."""

from __future__ import annotations

from app.modules.planning.iap.models.autofill import AutofillEngine, AutofillResult, AutofillRule
from app.modules.planning.iap.models.iap_models import FormInstance


def test_preview_reflects_existing_fields() -> None:
    form = FormInstance(form_id="ICS-205", title="Comms Plan", op_number=1, fields={"net": "TAC-1"})
    engine = AutofillEngine({"ICS-205": [AutofillRule(target_field="net", source="comms")]})

    result = engine.preview_for_form(form)

    assert isinstance(result, AutofillResult)
    assert result.populated_fields["net"] == "TAC-1"
    assert result.sources["net"] == "comms"


def test_describe_rules_returns_human_strings() -> None:
    engine = AutofillEngine({"ICS-202": [AutofillRule(target_field="incident_name", source="incident", description="Incident name")]})

    descriptions = engine.describe_rules("ICS-202")

    assert descriptions == ["Incident name"]
