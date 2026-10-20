"""New/Edit Search Segment dialog (SAR Toolkit — Search Segment Management).

GIS geometry is explicitly optional: the "Attach GIS geometry" checkbox is
off by default, and a segment can be saved with it unchecked and no
`gis_reference` at all.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.sartoolkit.models.segment import (
    PLANNING_STATUSES,
    REVIEW_STATUSES,
    SEARCH_STATUSES,
    SearchSegment,
)


class SegmentDialog(QDialog):
    def __init__(self, segment: Optional[SearchSegment] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._segment = segment or SearchSegment()
        self.setWindowTitle("Edit Segment" if segment else "New Segment")
        self.setMinimumWidth(480)

        form = QFormLayout()

        self.ed_name = QLineEdit(self._segment.name)
        form.addRow("Name*", self.ed_name)

        self.ed_description = QPlainTextEdit(self._segment.description)
        self.ed_description.setFixedHeight(60)
        form.addRow("Description", self.ed_description)

        self.ed_boundary = QPlainTextEdit(self._segment.boundary_description)
        self.ed_boundary.setFixedHeight(60)
        form.addRow("Boundary Description", self.ed_boundary)

        self.ed_map_ref = QLineEdit(self._segment.map_reference)
        form.addRow("Map Reference", self.ed_map_ref)

        self.chk_gis = QCheckBox("Attach GIS geometry")
        self.chk_gis.setChecked(bool(self._segment.gis_reference))
        form.addRow("", self.chk_gis)

        self.ed_gis = QLineEdit()
        if isinstance(self._segment.gis_reference, str):
            self.ed_gis.setText(self._segment.gis_reference)
        self.ed_gis.setPlaceholderText("Optional GIS reference / feature id")
        self.ed_gis.setEnabled(self.chk_gis.isChecked())
        self.chk_gis.toggled.connect(self.ed_gis.setEnabled)
        form.addRow("GIS Reference", self.ed_gis)

        self.ed_parent = QLineEdit(str(self._segment.parent_segment_id or ""))
        self.ed_parent.setPlaceholderText("Optional parent segment id (for subdivision)")
        form.addRow("Parent Segment ID", self.ed_parent)

        self.ed_terrain = QPlainTextEdit(self._segment.terrain_notes)
        self.ed_terrain.setFixedHeight(50)
        form.addRow("Terrain Notes", self.ed_terrain)

        self.ed_access = QPlainTextEdit(self._segment.access_notes)
        self.ed_access.setFixedHeight(50)
        form.addRow("Access Notes", self.ed_access)

        self.ed_hazards = QPlainTextEdit(self._segment.hazards)
        self.ed_hazards.setFixedHeight(50)
        form.addRow("Hazards", self.ed_hazards)

        self.sp_size = QDoubleSpinBox()
        self.sp_size.setRange(0, 1_000_000)
        self.sp_size.setDecimals(1)
        self.sp_size.setSuffix(" acres")
        self.sp_size.setSpecialValueText("(unspecified)")
        self.sp_size.setValue(self._segment.size_estimate or 0)
        form.addRow("Size Estimate", self.sp_size)

        self.cmb_planning = QComboBox()
        self.cmb_planning.addItems(PLANNING_STATUSES)
        self.cmb_planning.setCurrentText(self._segment.planning_status)
        form.addRow("Planning Status", self.cmb_planning)

        self.cmb_search = QComboBox()
        self.cmb_search.addItems(SEARCH_STATUSES)
        self.cmb_search.setCurrentText(self._segment.search_status)
        form.addRow("Search Status", self.cmb_search)

        self.cmb_review = QComboBox()
        self.cmb_review.addItems(REVIEW_STATUSES)
        self.cmb_review.setCurrentText(self._segment.review_status)
        form.addRow("Review Status", self.cmb_review)

        self.ed_created_by = QLineEdit(self._segment.created_by)
        form.addRow("Created By", self.ed_created_by)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self.ed_name.text().strip():
            self.ed_name.setFocus()
            return
        self.accept()

    def result_segment(self) -> SearchSegment:
        seg = self._segment
        seg.name = self.ed_name.text().strip()
        seg.description = self.ed_description.toPlainText().strip()
        seg.boundary_description = self.ed_boundary.toPlainText().strip()
        seg.map_reference = self.ed_map_ref.text().strip()
        seg.gis_reference = self.ed_gis.text().strip() if self.chk_gis.isChecked() and self.ed_gis.text().strip() else None
        seg.parent_segment_id = self.ed_parent.text().strip() or None
        seg.terrain_notes = self.ed_terrain.toPlainText().strip()
        seg.access_notes = self.ed_access.toPlainText().strip()
        seg.hazards = self.ed_hazards.toPlainText().strip()
        seg.size_estimate = self.sp_size.value() or None
        seg.planning_status = self.cmb_planning.currentText()
        seg.search_status = self.cmb_search.currentText()
        seg.review_status = self.cmb_review.currentText()
        seg.created_by = self.ed_created_by.text().strip()
        return seg
