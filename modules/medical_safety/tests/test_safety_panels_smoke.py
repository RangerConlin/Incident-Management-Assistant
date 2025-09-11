import pytest

try:
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover - headless environments
    QApplication = None  # type: ignore[assignment]
    pytest.skip("QtWidgets not available", allow_module_level=True)

from modules import medical_safety as ms


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_panels_smoke(app):
    panels = [
        ms.get_dashboard_panel(),
        ms.get_208_panel(),
        ms.get_215A_panel(),
        ms.get_hazard_log_panel(),
        ms.get_briefings_panel(),
        ms.get_incidents_panel(),
        ms.get_ppe_panel(),
        ms.get_cap_forms_panel(),
        ms.get_cap_form_editor_panel(),
    ]
    for p in panels:
        assert p is not None
