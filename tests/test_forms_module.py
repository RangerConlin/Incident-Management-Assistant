import json
from pathlib import Path

import pytest

from modules.forms import render_form
from modules.forms.templating import resolve_template
from modules.forms.render import FormValidationError
from modules.forms.examples import ics_205_example


def test_registry_resolution():
    info = resolve_template("ics_205", "latest")
    assert info.pdf_path is None or not info.pdf_path.exists()
    assert info.mapping_path.exists()
    assert info.schema_path.exists()


def test_render_form_produces_pdf(tmp_path: Path):
    pdf_bytes = render_form("ics_205", "2023.10", ics_205_example)
    out = tmp_path / "out.pdf"
    out.write_bytes(pdf_bytes)
    assert out.stat().st_size > 0


def test_schema_validation_error():
    bad = json.loads(json.dumps(ics_205_example))
    del bad["incident"]["name"]
    with pytest.raises(FormValidationError):
        render_form("ics_205", "2023.10", bad)
