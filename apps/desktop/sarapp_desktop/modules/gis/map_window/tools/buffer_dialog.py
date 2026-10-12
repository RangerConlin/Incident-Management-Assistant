"""BufferDialog: distance list, units, preview, output destination, preserve/merge options.

Wired to geometry_service.buffer_wkt (shapely-backed). Works on any
drawn/selected geometry: circle for points, corridor for lines, expansion
for polygons (shapely.buffer() already produces the right shape for each
input geometry type, so no per-type branching is needed here beyond
picking the right projected geometry — see geometry_service.buffer_wkt).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from modules.gis.map_window.tools.draw_tools import parse_ring_distances
from modules.gis.services.geometry_service import GeometryBufferError, buffer_distance_to_meters, buffer_wkt


class BufferDialog(QDialog):
    def __init__(self, source_geometry_wkt: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Buffer")
        self._source_geometry_wkt = source_geometry_wkt
        self._result_wkt: str | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._distance_edit = QLineEdit(self)
        self._distance_edit.setPlaceholderText("e.g. 100, 250, 500")
        form.addRow("Distances", self._distance_edit)

        self._unit_combo = QComboBox(self)
        self._unit_combo.addItem("Meters", "meters")
        self._unit_combo.addItem("Miles", "miles")
        form.addRow("Units", self._unit_combo)

        self._output_combo = QComboBox(self)
        self._output_combo.addItem("New drawing feature", "new_drawing")
        self._output_combo.addItem("Planning overlay", "planning_overlay")
        form.addRow("Output destination", self._output_combo)

        self._preserve_source_check = QCheckBox("Preserve source geometry", self)
        self._preserve_source_check.setChecked(True)
        form.addRow("", self._preserve_source_check)

        self._merge_overlaps_check = QCheckBox("Merge overlapping rings", self)
        form.addRow("", self._merge_overlaps_check)

        layout.addLayout(form)

        self._preview_label = QLabel("", self)
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        preview_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply, self)
        preview_button.button(QDialogButtonBox.StandardButton.Apply).setText("Preview")
        preview_button.accepted.connect(self._on_preview)
        layout.addWidget(preview_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def distances_meters(self) -> list[float]:
        unit = self._unit_combo.currentData()
        raw_distances = parse_ring_distances(self._distance_edit.text())
        return [buffer_distance_to_meters(d, unit) for d in raw_distances]

    def preserve_source(self) -> bool:
        return self._preserve_source_check.isChecked()

    def merge_overlaps(self) -> bool:
        return self._merge_overlaps_check.isChecked()

    def output_destination(self) -> str:
        return str(self._output_combo.currentData())

    def result_wkt_list(self) -> list[str]:
        return self._preview_wkt_list()

    def _preview_wkt_list(self) -> list[str]:
        distances = self.distances_meters()
        results: list[str] = []
        for distance in distances:
            try:
                results.append(
                    buffer_wkt(self._source_geometry_wkt, distance, merge_overlaps=self.merge_overlaps())
                )
            except GeometryBufferError as exc:
                self._preview_label.setText(str(exc))
                return []
        return results

    def _on_preview(self) -> None:
        results = self._preview_wkt_list()
        if results:
            self._preview_label.setText(f"{len(results)} buffer ring(s) ready.")

    def _on_accept(self) -> None:
        results = self._preview_wkt_list()
        if not results:
            QMessageBox.warning(self, "Add Buffer", "Enter at least one valid positive distance.")
            return
        self.accept()
