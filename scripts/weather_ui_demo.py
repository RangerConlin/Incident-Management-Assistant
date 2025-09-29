from PySide6.QtWidgets import QApplication, QMainWindow, QAction, QWidget

from modules.safety.weather.ui import (
    WeatherSummaryPanel,
    OverrideLocationDialog,
    AlertPopup,
    AlertDetailsWindow,
    HWOViewerWindow,
    WeatherTimelineWindow,
    WeatherSettingsDialog,
    ExportBriefingSnippetDialog,
    AviationWeatherWindow,
)


def main() -> None:
    app = QApplication.instance() or QApplication([])
    win = QMainWindow()
    win.setWindowTitle("Weather Safety UI Demo")
    bar = win.menuBar()
    m = bar.addMenu("Windows")
    act_summary = QAction("Weather Summary Panel", win)
    act_override = QAction("Override Location", win)
    act_popup = QAction("Alert Popup", win)
    act_details = QAction("Alert Details", win)
    act_hwo = QAction("HWO Viewer", win)
    act_timeline = QAction("Timeline View", win)
    act_settings = QAction("Settings", win)
    act_export = QAction("Export Snippet", win)
    act_aviation = QAction("Aviation Weather", win)
    for a in (act_summary, act_override, act_popup, act_details, act_hwo, act_timeline, act_settings, act_export, act_aviation):
        m.addAction(a)

    central = QWidget(); win.setCentralWidget(central)
    act_summary.triggered.connect(lambda: WeatherSummaryPanel(win).show())
    act_override.triggered.connect(lambda: OverrideLocationDialog(parent=win).show())
    act_popup.triggered.connect(lambda: AlertPopup("Severe Thunderstorm Warning", "Area XYZ — 12:00–13:30Z", parent=win).show())
    act_details.triggered.connect(lambda: AlertDetailsWindow("Severe Thunderstorm Warning", "Severe", parent=win).show())
    act_hwo.triggered.connect(lambda: HWOViewerWindow(parent=win).show())
    act_timeline.triggered.connect(lambda: WeatherTimelineWindow(parent=win).show())
    act_settings.triggered.connect(lambda: WeatherSettingsDialog(parent=win).show())
    act_export.triggered.connect(lambda: ExportBriefingSnippetDialog(parent=win).show())
    act_aviation.triggered.connect(lambda: AviationWeatherWindow(parent=win).show())
    win.resize(1024, 720)
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
