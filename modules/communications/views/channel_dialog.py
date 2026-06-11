from __future__ import annotations

"""Shared channel editor dialog used by both New and Edit workflows."""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QLabel,
    QGroupBox,
    QDialogButtonBox,
)

from modules.communications.models.incident_repo import infer_band

_FUNCTIONS = ["Command", "Tactical", "Dispatch", "Emergency", "Ground-to-Air",
              "Air-to-Air", "Medical", "Logistics", "Operations", "Safety",
              "Public Info", "Other"]

_MODES = ["FMN", "FMN/D", "AM", "DMR", "P25", "NXDN", "dPMR", "Tetra", "Other"]

_PRIORITIES = ["Primary", "Alternate", "Emergency"]

_ENCRYPTIONS = ["No", "Yes"]

_SYSTEMS = ["NIFOG", "Conventional", "Trunked", "P25", "DMR", "NXDN", "Other"]


class ChannelDialog(QDialog):
    """Modal dialog for creating or editing a communications channel."""

    def __init__(
        self,
        row: Optional[Dict[str, Any]] = None,
        *,
        title: str = "Channel",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)
        self._row = row or {}

        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── Identity ─────────────────────────────────────────────────────────
        id_box = QGroupBox("Identity")
        id_form = QFormLayout(id_box)
        id_form.setLabelAlignment(Qt.AlignRight)

        self.ed_name = QLineEdit(str(self._row.get("channel") or ""))
        self.ed_name.setPlaceholderText("Alpha tag / channel name")

        self.cb_function = self._make_combo(_FUNCTIONS, self._row.get("function") or "Tactical", editable=False)
        self.cb_system   = self._make_combo(_SYSTEMS,   self._row.get("system")   or "NIFOG")
        self.cb_mode     = self._make_combo(_MODES,     self._row.get("mode")     or "FMN",      editable=False)
        self.cb_priority = self._make_combo(_PRIORITIES, self._row.get("priority") or "Primary", editable=False)

        id_form.addRow("Name:", self.ed_name)
        id_form.addRow("Function:", self.cb_function)
        id_form.addRow("System:", self.cb_system)
        id_form.addRow("Mode:", self.cb_mode)
        id_form.addRow("Priority:", self.cb_priority)

        # ── Frequencies ───────────────────────────────────────────────────────
        freq_box = QGroupBox("Frequencies")
        freq_form = QFormLayout(freq_box)
        freq_form.setLabelAlignment(Qt.AlignRight)

        rx_val = self._row.get("rx_freq")
        tx_val = self._row.get("tx_freq")

        self.ed_rx = QLineEdit("" if rx_val is None else str(rx_val))
        self.ed_rx.setPlaceholderText("e.g. 155.1600")
        self.ed_rx_tone = QLineEdit(str(self._row.get("rx_tone") or "CSQ"))
        self.ed_rx_tone.setPlaceholderText("CSQ / CTCSS tone / NAC")

        self.ed_tx = QLineEdit("" if tx_val is None else str(tx_val))
        self.ed_tx.setPlaceholderText("e.g. 155.1600  (blank = simplex)")
        self.ed_tx_tone = QLineEdit(str(self._row.get("tx_tone") or ""))
        self.ed_tx_tone.setPlaceholderText("CSQ / CTCSS tone / NAC")

        # Normalise legacy free-text encryption values to Yes/No
        _enc_raw = str(self._row.get("encryption") or "No")
        _enc_val = "Yes" if _enc_raw not in ("No", "None", "", "0") else "No"
        self.cb_encrypt = self._make_combo(_ENCRYPTIONS, _enc_val, editable=False)

        freq_form.addRow("RX Freq (MHz):", self.ed_rx)
        freq_form.addRow("RX Tone / NAC:", self.ed_rx_tone)
        freq_form.addRow("TX Freq (MHz):", self.ed_tx)
        freq_form.addRow("TX Tone / NAC:", self.ed_tx_tone)
        freq_form.addRow("Encryption:", self.cb_encrypt)

        # ── Assignment ────────────────────────────────────────────────────────
        asgn_box = QGroupBox("Assignment")
        asgn_form = QFormLayout(asgn_box)
        asgn_form.setLabelAlignment(Qt.AlignRight)

        self.ed_div = QLineEdit(str(self._row.get("assignment_division") or ""))
        self.ed_div.setPlaceholderText("Division / Branch")
        self.ed_team = QLineEdit(str(self._row.get("assignment_team") or ""))
        self.ed_team.setPlaceholderText("Team / Unit")

        self.ed_remarks = QTextEdit()
        self.ed_remarks.setPlainText(str(self._row.get("remarks") or ""))
        self.ed_remarks.setFixedHeight(72)
        self.ed_remarks.setPlaceholderText("Optional notes or special instructions")

        asgn_form.addRow("Division:", self.ed_div)
        asgn_form.addRow("Team:", self.ed_team)
        asgn_form.addRow("Remarks:", self.ed_remarks)

        # ── Duplicate warning ─────────────────────────────────────────────────
        self.lbl_dup = QLabel("")
        self.lbl_dup.setStyleSheet("color: #E8A000; font-size: 11px;")
        self.lbl_dup.setVisible(False)

        # ── Buttons ───────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root.addWidget(id_box)
        root.addWidget(freq_box)
        root.addWidget(asgn_box)
        root.addWidget(self.lbl_dup)
        root.addWidget(buttons)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_combo(options: list, value: str, *, editable: bool = True) -> QComboBox:
        cb = QComboBox()
        cb.addItems(options)
        cb.setEditable(editable)
        cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        cb.setMinimumContentsLength(max(len(o) for o in options))
        idx = cb.findText(str(value), Qt.MatchFixedString)
        if idx >= 0:
            cb.setCurrentIndex(idx)
        else:
            cb.setCurrentText(str(value))
        return cb

    @staticmethod
    def _set_combo(combo: QComboBox, value: str):
        idx = combo.findText(str(value), Qt.MatchFixedString)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentText(str(value))

    def _fnum(self, text: str) -> Optional[float]:
        try:
            t = text.strip()
            return float(t) if t else None
        except Exception:
            return None

    def set_dup_warning(self, msg: str):
        self.lbl_dup.setText(msg)
        self.lbl_dup.setVisible(bool(msg))

    def get_patch(self) -> Dict[str, Any]:
        rx = self._fnum(self.ed_rx.text())
        tx = self._fnum(self.ed_tx.text())
        band = infer_band(rx if rx is not None else tx)
        return {
            "channel": self.ed_name.text().strip(),
            "function": self.cb_function.currentText().strip() or "Tactical",
            "system": self.cb_system.currentText().strip() or None,
            "mode": self.cb_mode.currentText().strip() or "FMN",
            "rx_freq": rx,
            "tx_freq": tx,
            "rx_tone": self.ed_rx_tone.text().strip() or None,
            "tx_tone": self.ed_tx_tone.text().strip() or None,
            "encryption": self.cb_encrypt.currentText().strip() or "No",
            "assignment_division": self.ed_div.text().strip() or None,
            "assignment_team": self.ed_team.text().strip() or None,
            "priority": self.cb_priority.currentText().strip() or "Primary",
            "remarks": self.ed_remarks.toPlainText().strip() or None,
            "band": band,
        }


__all__ = ["ChannelDialog"]
