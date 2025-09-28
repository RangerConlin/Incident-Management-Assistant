from __future__ import annotations

"""Modal dialog to edit an existing ICS-205 plan row."""

from typing import Any, Dict

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QTextEdit,
    QLabel,
    QDialogButtonBox,
)

from modules.communications.models.incident_repo import infer_band


class EditChannelDialog(QDialog):
    def __init__(self, row: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Channel")
        self.setModal(True)
        self._row = row

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.ed_name = QLineEdit(str(row.get("channel") or ""))
        self.ed_function = QLineEdit(str(row.get("function") or ""))
        self.ed_system = QLineEdit(str(row.get("system") or ""))
        self.ed_mode = QLineEdit(str(row.get("mode") or ""))
        self.cb_include = QCheckBox("Include on ICS-205")
        self.cb_include.setChecked(bool(int(row.get("include_on_205") or 0)))
        self.ed_rx = QLineEdit("" if row.get("rx_freq") is None else str(row.get("rx_freq")))
        self.ed_rx.setPlaceholderText("MHz e.g., 155.1600")
        self.ed_rx_tone = QLineEdit(str(row.get("rx_tone") or ""))
        self.ed_tx = QLineEdit("" if row.get("tx_freq") is None else str(row.get("tx_freq")))
        self.ed_tx.setPlaceholderText("MHz e.g., 155.1600")
        self.ed_tx_tone = QLineEdit(str(row.get("tx_tone") or ""))
        self.ed_encrypt = QLineEdit(str(row.get("encryption") or "None"))
        self.ed_div = QLineEdit(str(row.get("assignment_division") or ""))
        self.ed_team = QLineEdit(str(row.get("assignment_team") or ""))
        self.ed_priority = QLineEdit(str(row.get("priority") or "Normal"))
        self.ed_remarks = QTextEdit()
        self.ed_remarks.setPlainText(str(row.get("remarks") or ""))

        for label, widget in (
            ("Channel Name (Alpha Tag):", self.ed_name),
            ("Function:", self.ed_function),
            ("System:", self.ed_system),
            ("Mode:", self.ed_mode),
            ("RX Freq (MHz):", self.ed_rx),
            ("RX Tone:", self.ed_rx_tone),
            ("TX Freq (MHz):", self.ed_tx),
            ("TX Tone:", self.ed_tx_tone),
            ("Encryption:", self.ed_encrypt),
            ("Assignment Division:", self.ed_div),
            ("Assignment Team:", self.ed_team),
            ("Priority:", self.ed_priority),
            ("Remarks:", self.ed_remarks),
        ):
            form.addRow(label, widget)

        layout.addLayout(form)
        layout.addWidget(self.cb_include)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_patch(self) -> Dict[str, Any]:
        def fnum(txt: str):
            try:
                t = txt.strip()
                return float(t) if t else None
            except Exception:
                return None

        rx = fnum(self.ed_rx.text())
        tx = fnum(self.ed_tx.text())
        band = infer_band(rx if rx is not None else tx)
        return {
            "channel": self.ed_name.text().strip(),
            "function": self.ed_function.text().strip(),
            "system": self.ed_system.text().strip() or None,
            "mode": self.ed_mode.text().strip(),
            "rx_freq": rx,
            "tx_freq": tx,
            "rx_tone": self.ed_rx_tone.text().strip() or None,
            "tx_tone": self.ed_tx_tone.text().strip() or None,
            "encryption": self.ed_encrypt.text().strip() or "None",
            "assignment_division": self.ed_div.text().strip() or None,
            "assignment_team": self.ed_team.text().strip() or None,
            "priority": self.ed_priority.text().strip() or "Normal",
            "include_on_205": 1 if self.cb_include.isChecked() else 0,
            "remarks": self.ed_remarks.toPlainText().strip() or None,
            "band": band,
        }


__all__ = ["EditChannelDialog"]
