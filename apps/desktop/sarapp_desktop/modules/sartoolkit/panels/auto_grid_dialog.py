"""Auto-Create Grid dialog (SAR Toolkit — Search Segment Management).

Collects grid-tiling parameters and runs a confirm step before the batch
create call. Actual polygon clipping against another feature is NOT
implemented — `clip_to` is stored as a plain value only (see
server/sarapp_db/sarapp_db/api/routers/search_segments.py).
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class AutoGridDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto-Create Grid")
        self.setMinimumWidth(420)

        form = QFormLayout()

        self.sp_lat = QDoubleSpinBox()
        self.sp_lat.setRange(-90, 90)
        self.sp_lat.setDecimals(6)
        form.addRow("Origin Latitude", self.sp_lat)

        self.sp_lon = QDoubleSpinBox()
        self.sp_lon.setRange(-180, 180)
        self.sp_lon.setDecimals(6)
        form.addRow("Origin Longitude", self.sp_lon)

        self.sp_orientation = QDoubleSpinBox()
        self.sp_orientation.setRange(0, 359.9)
        self.sp_orientation.setSuffix(" deg")
        form.addRow("Orientation", self.sp_orientation)

        self.sp_cell_acres = QDoubleSpinBox()
        self.sp_cell_acres.setRange(0.1, 100000)
        self.sp_cell_acres.setValue(40)
        self.sp_cell_acres.setSuffix(" acres")
        form.addRow("Cell Size", self.sp_cell_acres)

        self.sp_rows = QSpinBox()
        self.sp_rows.setRange(1, 200)
        self.sp_rows.setValue(3)
        form.addRow("Rows", self.sp_rows)

        self.sp_cols = QSpinBox()
        self.sp_cols.setRange(1, 200)
        self.sp_cols.setValue(3)
        form.addRow("Columns", self.sp_cols)

        self.cmb_naming = QComboBox()
        self.cmb_naming.addItem("Sequential (SEG-01, SEG-02, ...)", "sequential")
        self.cmb_naming.addItem("Row/Column (A1, A2, ...)", "row_col")
        form.addRow("Naming Scheme", self.cmb_naming)

        self.ed_prefix = QLineEdit("SEG")
        form.addRow("Name Prefix", self.ed_prefix)

        self.ed_clip_to = QLineEdit()
        self.ed_clip_to.setPlaceholderText("Optional — e.g. a GIS feature id to clip against (not yet implemented)")
        form.addRow("Clip To", self.ed_clip_to)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setCenterButtons(True)
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _confirm(self) -> None:
        count = self.sp_rows.value() * self.sp_cols.value()
        reply = QMessageBox.question(
            self,
            "Confirm Grid Creation",
            f"This will create {count} new segment(s) of {self.sp_cell_acres.value():g} acres each. Continue?",
        )
        if reply == QMessageBox.Yes:
            self.accept()

    def result_params(self) -> dict[str, Any]:
        return {
            "origin_lat": self.sp_lat.value(),
            "origin_lon": self.sp_lon.value(),
            "orientation_deg": self.sp_orientation.value(),
            "cell_acres": self.sp_cell_acres.value(),
            "rows": self.sp_rows.value(),
            "columns": self.sp_cols.value(),
            "naming_scheme": self.cmb_naming.currentData(),
            "name_prefix": self.ed_prefix.text().strip() or "SEG",
            "clip_to": self.ed_clip_to.text().strip() or None,
        }
