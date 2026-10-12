from modules.planning import get_demobilization_panel


def test_get_demobilization_panel_returns_widget(qtbot) -> None:
    panel = get_demobilization_panel("INC-DEMOB")
    qtbot.addWidget(panel)

    assert panel.windowTitle() == "Planning - Demobilization"
