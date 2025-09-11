from __future__ import annotations

"""Modal dialog for creating a brand‑new channel and adding it to the plan."""

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QTextEdit,
    QLabel,
    QDialogButtonBox,
)


class NewChannelDialog(QDialog):
    def __init__(self, incident_repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Channel")
        self.setModal(True)
        self._repo = incident_repo

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.ed_name = QLineEdit()
        self.ed_function = QLineEdit("Tactical")
        self.ed_system = QLineEdit("NIFOG")
        self.ed_mode = QLineEdit("FMN")
        self.cb_include = QCheckBox("Include on ICS‑205")
        self.cb_include.setChecked(True)
        self.ed_rx = QLineEdit()
        self.ed_rx.setPlaceholderText("MHz e.g., 155.1600")
        self.ed_rx_tone = QLineEdit("CSQ")
        self.ed_tx = QLineEdit()
        self.ed_tx.setPlaceholderText("MHz e.g., 155.1600")
        self.ed_tx_tone = QLineEdit()
        self.ed_encrypt = QLineEdit("None")
        self.ed_div = QLineEdit()
        self.ed_team = QLineEdit()
        self.ed_priority = QLineEdit("Normal")
        self.ed_remarks = QTextEdit()

        self.lbl_dup = QLabel("")
        self.lbl_dup.setStyleSheet("color: orange")

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
        layout.addWidget(self.lbl_dup)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # duplicate check
        for w in (self.ed_name, self.ed_rx, self.ed_tx):
            w.textChanged.connect(self._check_duplicate)

    def _check_duplicate(self):
        try:
            rx = float(self.ed_rx.text()) if self.ed_rx.text().strip() else None
            tx = float(self.ed_tx.text()) if self.ed_tx.text().strip() else None
        except ValueError:
            rx = None
            tx = None
        name = self.ed_name.text().strip()
        dups = []
        for r in self._repo.list_plan():
            same_name = name and (r.get("channel") or "").strip().lower() == name.lower()
            same_freq = (rx is not None and r.get("rx_freq") == rx) and ((tx or 0) == (r.get("tx_freq") or 0))
            if same_name or same_freq:
                dups.append(r)
        if dups:
            self.lbl_dup.setText(f"• Potential duplicate: {len(dups)} similar row(s) exist")
        else:
            self.lbl_dup.setText("")

    def get_channel_data(self) -> Dict[str, Any]:
        def fnum(txt: str):
            try:
                return float(txt) if txt.strip() else None
            except Exception:
                return None
        return {
            "channel": self.ed_name.text().strip(),
            "function": self.ed_function.text().strip() or "Tactical",
            "system": self.ed_system.text().strip() or None,
            "mode": self.ed_mode.text().strip() or "FMN",
            "rx_freq": fnum(self.ed_rx.text()),
            "tx_freq": fnum(self.ed_tx.text()),
            "rx_tone": self.ed_rx_tone.text().strip() or None,
            "tx_tone": self.ed_tx_tone.text().strip() or None,
            "encryption": self.ed_encrypt.text().strip() or "None",
            "assignment_division": self.ed_div.text().strip() or None,
            "assignment_team": self.ed_team.text().strip() or None,
            "priority": self.ed_priority.text().strip() or "Normal",
            "include_on_205": self.cb_include.isChecked(),
            "remarks": self.ed_remarks.toPlainText().strip() or None,
        }

