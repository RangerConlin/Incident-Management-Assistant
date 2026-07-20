"""BottomPanel: collapsible tabbed strip docked at the bottom of the map window.

Tabs: Feature Table, Search Results, Coordinates, Timeline (stub), Downloads
(stub), Log. Collapses to a tab-strip-only sliver; a QSplitter handle above
it lets the user resize it while expanded. Auto-opens when a tool produces
results (search hits, coordinate entry, a new log line).
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from utils.coordinates import format_dms, latlon_to_mgrs, latlon_to_utm
from utils.table_view_styles import apply_statusboard_table_behavior

_COLLAPSED_HEIGHT = 28
_EXPANDED_HEIGHT = 220


class _CoordinatesTab(QWidget):
    coordinateSubmitted = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._lat_edit = QLineEdit(self)
        self._lon_edit = QLineEdit(self)
        self._go_button = QPushButton("Go To", self)
        self._go_button.clicked.connect(self._on_go)
        form.addRow("Latitude", self._lat_edit)
        form.addRow("Longitude", self._lon_edit)
        form.addRow("", self._go_button)
        layout.addLayout(form)

        self._utm_label = QLabel("UTM: -", self)
        self._mgrs_label = QLabel("MGRS: -", self)
        self._dms_label = QLabel("DMS: -", self)
        layout.addWidget(self._utm_label)
        layout.addWidget(self._mgrs_label)
        layout.addWidget(self._dms_label)
        layout.addStretch(1)

    def _on_go(self) -> None:
        try:
            lat = float(self._lat_edit.text())
            lon = float(self._lon_edit.text())
        except ValueError:
            return
        self.show_coordinates(lat, lon)
        self.coordinateSubmitted.emit(lat, lon)

    def show_coordinates(self, lat: float, lon: float) -> None:
        self._lat_edit.setText(f"{lat:.6f}")
        self._lon_edit.setText(f"{lon:.6f}")
        try:
            utm = latlon_to_utm(lat, lon)
            self._utm_label.setText(f"UTM: {utm}")
        except ValueError:
            self._utm_label.setText("UTM: (out of range)")
        try:
            self._mgrs_label.setText(f"MGRS: {latlon_to_mgrs(lat, lon)}")
        except ValueError:
            self._mgrs_label.setText("MGRS: (out of range)")
        self._dms_label.setText(f"DMS: {format_dms(lat, True)}  {format_dms(lon, False)}")


class BottomPanel(QWidget):
    collapsedChanged = Signal(bool)
    coordinateSubmitted = Signal(float, float)
    featureTableRowActivated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collapsed = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._tabs = QTabWidget(self)
        self._tabs.setDocumentMode(True)
        outer.addWidget(self._tabs, 1)

        self._feature_table = QTableWidget(0, 4, self)
        self._feature_table.setHorizontalHeaderLabels(["ID", "Type", "Label", "Layer"])
        apply_statusboard_table_behavior(self._feature_table, stretch_last_section=True)
        self._feature_table.verticalHeader().setVisible(False)
        self._feature_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._feature_table.cellDoubleClicked.connect(self._on_feature_row_activated)
        self._tabs.addTab(self._feature_table, "Feature Table")

        self._search_results = QListWidget(self)
        self._tabs.addTab(self._search_results, "Search Results")

        self._coordinates_tab = _CoordinatesTab(self)
        self._coordinates_tab.coordinateSubmitted.connect(self.coordinateSubmitted)
        self._tabs.addTab(self._coordinates_tab, "Coordinates")

        self._timeline_stub = QLabel("Timeline — coming soon.", self)
        self._timeline_stub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(self._timeline_stub, "Timeline")

        self._downloads_stub = QLabel("Downloads — coming soon.", self)
        self._downloads_stub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tabs.addTab(self._downloads_stub, "Downloads")

        self._log_list = QListWidget(self)
        self._tabs.addTab(self._log_list, "Log")

        self.set_collapsed(True)

    # ------------------------------------------------------------------
    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._tabs.tabBar().setVisible(True)
        for index in range(self._tabs.count()):
            self._tabs.widget(index).setVisible(not collapsed)
        self.setFixedHeight(_COLLAPSED_HEIGHT if collapsed else self.height())
        if not collapsed:
            self.setMinimumHeight(_EXPANDED_HEIGHT)
            self.setMaximumHeight(16777215)
        else:
            self.setMinimumHeight(_COLLAPSED_HEIGHT)
            self.setMaximumHeight(_COLLAPSED_HEIGHT)
        self.collapsedChanged.emit(collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def ensure_expanded(self) -> None:
        if self._collapsed:
            self.set_collapsed(False)

    def show_tab(self, name: str) -> None:
        self.ensure_expanded()
        index = {
            "feature_table": 0,
            "search_results": 1,
            "coordinates": 2,
            "timeline": 3,
            "downloads": 4,
            "log": 5,
        }.get(name)
        if index is not None:
            self._tabs.setCurrentIndex(index)

    # -- Feature Table -----------------------------------------------------
    def set_feature_rows(self, rows: list[tuple[str, str, str, str]]) -> None:
        self._feature_table.setRowCount(len(rows))
        for row_index, (feature_id, feature_type, label, layer) in enumerate(rows):
            self._feature_table.setItem(row_index, 0, QTableWidgetItem(feature_id))
            self._feature_table.setItem(row_index, 1, QTableWidgetItem(feature_type))
            self._feature_table.setItem(row_index, 2, QTableWidgetItem(label))
            self._feature_table.setItem(row_index, 3, QTableWidgetItem(layer))

    def _on_feature_row_activated(self, row: int, _column: int) -> None:
        item = self._feature_table.item(row, 0)
        if item is not None:
            self.featureTableRowActivated.emit(item.text())
            self.show_tab("feature_table")

    # -- Search Results -----------------------------------------------------
    def set_search_results(self, groups: dict[str, list[str]]) -> None:
        self._search_results.clear()
        for group_name, items in groups.items():
            if not items:
                continue
            self._search_results.addItem(f"— {group_name} —")
            for item in items:
                self._search_results.addItem(f"   {item}")
        self.show_tab("search_results")

    # -- Coordinates ----------------------------------------------------
    def show_coordinates(self, lat: float, lon: float) -> None:
        self._coordinates_tab.show_coordinates(lat, lon)
        self.show_tab("coordinates")

    # -- Log --------------------------------------------------------------
    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_list.addItem(f"[{timestamp}] {message}")
