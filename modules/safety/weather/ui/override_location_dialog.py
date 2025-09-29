from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QDialogButtonBox,
    QFormLayout,
    QDoubleSpinBox,
    QGroupBox,
    QCheckBox,
    QListWidget,
)

from ._geometry import GeometryHelper


class OverrideLocationDialog(QDialog):
    applyRequested = Signal(float, float)

    def __init__(self, icp_available: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Weather Location")
        self.setModal(True)
        self._build_ui(icp_available)
        GeometryHelper.restore(self, "OverrideLocationDialog")

    def closeEvent(self, e):
        GeometryHelper.save(self, "OverrideLocationDialog")
        super().closeEvent(e)

    def _build_ui(self, icp_available: bool) -> None:
        v = QVBoxLayout(self)
        group = QGroupBox("Choose Source")
        gl = QVBoxLayout(group)

        self.optICP = QCheckBox("Use ICP location")
        self.optICP.setChecked(icp_available)
        self.optICP.setEnabled(icp_available)
        self.optManual = QCheckBox("Manual coordinates")
        self.optSearch = QCheckBox("City/ZIP search")

        gl.addWidget(self.optICP)
        # Manual row
        manual_row = QHBoxLayout()
        self.spnLat = QDoubleSpinBox(); self.spnLat.setRange(-90.0, 90.0); self.spnLat.setDecimals(6); self.spnLat.setPrefix("Lat ")
        self.spnLon = QDoubleSpinBox(); self.spnLon.setRange(-180.0, 180.0); self.spnLon.setDecimals(6); self.spnLon.setPrefix("Lon ")
        self.btnUseCursor = QPushButton("Use current map cursor")
        manual_row.addWidget(self.spnLat); manual_row.addWidget(self.spnLon); manual_row.addWidget(self.btnUseCursor)
        gl.addLayout(manual_row)
        gl.addWidget(self.optManual)

        # Search row
        search_row = QHBoxLayout()
        self.txtSearch = QLineEdit(); self.txtSearch.setPlaceholderText("City or ZIP")
        self.btnSearch = QPushButton("Search")
        self.listResults = QListWidget()
        search_row.addWidget(self.txtSearch); search_row.addWidget(self.btnSearch)
        gl.addLayout(search_row)
        gl.addWidget(self.listResults)
        gl.addWidget(self.optSearch)

        v.addWidget(group)

        self.errLabel = QLabel("")
        self.errLabel.setStyleSheet("color:#b71c1c;")
        v.addWidget(self.errLabel)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Apply")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._on_apply)
        v.addWidget(buttons)

        QShortcut(QKeySequence("Esc"), self, activated=self.reject)

    def _on_apply(self) -> None:
        if self.optManual.isChecked():
            lat = float(self.spnLat.value()); lon = float(self.spnLon.value())
            self.applyRequested.emit(lat, lon)
            self.accept()
            return
        if self.optICP.isChecked():
            # No coordinates emitted; caller should switch to ICP
            self.applyRequested.emit(float("nan"), float("nan"))
            self.accept()
            return
        if self.optSearch.isChecked():
            # UI-only: pick first search result if any
            self.accept()
            return
        self.errLabel.setText("Select a location option or enter valid coordinates.")

