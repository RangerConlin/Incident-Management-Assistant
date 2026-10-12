import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.admin.hazard_types.models import HazardDefaultSpe, HazardType
from modules.admin.hazard_types.windows.hazard_type_editor_window import HazardTypeDetailForm


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_detail_form_populates_and_computes_spe() -> None:
    app = _app()
    form = HazardTypeDetailForm()
    app.processEvents()

    form.set_hazard_type(
        HazardType(
            id=12,
            name="Chainsaw Operations",
            category="Operational",
            description="Saw work in timber and debris fields.",
            aliases=["Saw Work"],
            controls=["Establish escape routes"],
            ppe=["Helmet", "Eye Protection"],
            standard_safety_language="Only trained personnel may operate chainsaws.",
            default_spe=HazardDefaultSpe(
                severity=5,
                probability=5,
                exposure=4,
                score=100,
                band="Very High",
                action="Discontinue / Stop",
            ),
            active=True,
        )
    )
    app.processEvents()

    assert form.score_value.text() == "100"
    assert form.band_value.text() == "Very High"
    assert form.action_value.text() == "Discontinue / Stop"

    model = form.to_model()
    assert model.default_spe is not None
    assert model.default_spe.score == 100
    assert model.default_spe.exposure == 4


def test_detail_form_defaults_new_records_to_valid_spe_range() -> None:
    app = _app()
    form = HazardTypeDetailForm()
    app.processEvents()

    model = form.to_model()

    assert model.default_spe is not None
    assert model.default_spe.severity == 1
    assert model.default_spe.probability == 1
    assert model.default_spe.exposure == 1
    assert model.default_spe.score == 1
