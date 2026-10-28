from PySide6.QtWidgets import QApplication

from modules.planning import get_demobilization_panel

_APP: QApplication | None = None


def test_get_demobilization_panel_returns_widget() -> None:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    panel = get_demobilization_panel("INC-DEMOB")
    try:
        assert panel.windowTitle().startswith("Planning - Demobilization")
    finally:
        panel.close()
