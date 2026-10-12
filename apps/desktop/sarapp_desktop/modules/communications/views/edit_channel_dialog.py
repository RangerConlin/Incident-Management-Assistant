from __future__ import annotations

"""Dialog for editing an existing ICS-205 plan row.

Only edits incident-specific fields (assignment, priority, encryption,
remarks). Channel identity (name, frequencies, tones, mode, system) is owned
by the master catalog and shown here read-only for context - to change it,
edit the channel in the Channel Library / master catalog instead.
"""

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

_PRIORITIES = ["Primary", "Alternate", "Emergency"]
_ENCRYPTIONS = ["No", "Yes"]


class EditChannelDialog(QDialog):
    """Modal dialog for editing a plan row's incident-specific fields."""

    def __init__(self, row: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Channel Assignment")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._row = row or {}

        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── Channel identity (read-only) ────────────────────────────────────
        id_box = QGroupBox("Channel (from master catalog)")
        id_form = QFormLayout(id_box)
        id_form.setLabelAlignment(Qt.AlignRight)
        id_form.addRow("Name:", QLabel(str(self._row.get("channel") or "")))
        id_form.addRow("Function:", QLabel(str(self._row.get("function") or "")))
        freq_text = str(self._row.get("rx_freq") or "")
        if self._row.get("tx_freq"):
            freq_text += f"  /  TX {self._row.get('tx_freq')}"
        id_form.addRow("RX Freq:", QLabel(freq_text))
        id_form.addRow("System / Mode:", QLabel(f"{self._row.get('system') or ''}  {self._row.get('mode') or ''}".strip()))

        # ── Assignment (editable) ────────────────────────────────────────────
        asgn_box = QGroupBox("Assignment for this incident")
        asgn_form = QFormLayout(asgn_box)
        asgn_form.setLabelAlignment(Qt.AlignRight)

        self.ed_div = QLineEdit(str(self._row.get("assignment_division") or ""))
        self.ed_div.setPlaceholderText("Division / Branch")
        self.ed_team = QLineEdit(str(self._row.get("assignment_team") or ""))
        self.ed_team.setPlaceholderText("Team / Unit")

        self.cb_priority = self._make_combo(_PRIORITIES, self._row.get("priority") or "Primary")

        _enc_raw = str(self._row.get("encryption") or "No")
        _enc_val = "Yes" if _enc_raw not in ("No", "None", "", "0") else "No"
        self.cb_encrypt = self._make_combo(_ENCRYPTIONS, _enc_val)

        self.ed_remarks = QTextEdit()
        self.ed_remarks.setPlainText(str(self._row.get("remarks") or ""))
        self.ed_remarks.setFixedHeight(72)
        self.ed_remarks.setPlaceholderText("Optional notes or special instructions")

        asgn_form.addRow("Division:", self.ed_div)
        asgn_form.addRow("Team:", self.ed_team)
        asgn_form.addRow("Priority:", self.cb_priority)
        asgn_form.addRow("Encryption:", self.cb_encrypt)
        asgn_form.addRow("Remarks:", self.ed_remarks)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root.addWidget(id_box)
        root.addWidget(asgn_box)
        root.addWidget(buttons)

    @staticmethod
    def _make_combo(options: list, value: str) -> QComboBox:
        cb = QComboBox()
        cb.addItems(options)
        cb.setEditable(False)
        idx = cb.findText(str(value), Qt.MatchFixedString)
        if idx >= 0:
            cb.setCurrentIndex(idx)
        return cb

    def get_patch(self) -> Dict[str, Any]:
        return {
            "assignment_division": self.ed_div.text().strip() or None,
            "assignment_team": self.ed_team.text().strip() or None,
            "priority": self.cb_priority.currentText().strip() or "Primary",
            "encryption": self.cb_encrypt.currentText().strip() or "No",
            "remarks": self.ed_remarks.toPlainText().strip() or None,
        }


__all__ = ["EditChannelDialog"]
