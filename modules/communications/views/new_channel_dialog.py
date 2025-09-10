from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QDialogButtonBox, QLabel
)

from ..controller import ICS205Controller, PLAN_COLUMNS


class NewChannelDialog(QDialog):
    def __init__(self, controller: ICS205Controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle('New Channel')
        self.controller = controller
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.name = QLineEdit()
        form.addRow('Channel Name', self.name)
        self.function = QLineEdit('Tactical')
        form.addRow('Function', self.function)
        self.mode = QLineEdit('FMN')
        form.addRow('Mode', self.mode)
        self.rx = QLineEdit()
        form.addRow('RX Freq (MHz)', self.rx)
        self.tx = QLineEdit()
        form.addRow('TX Freq (MHz)', self.tx)
        self.include_chk = QCheckBox()
        self.include_chk.setChecked(True)
        form.addRow('Include on 205', self.include_chk)
        self.remarks = QLineEdit()
        form.addRow('Remarks', self.remarks)

        self.info = QLabel()
        layout.addWidget(self.info)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name.textChanged.connect(self._check_duplicate)

    def _check_duplicate(self, text: str):
        existing = [r['channel'] for r in self.controller.planModel.rows]
        if text in existing:
            self.info.setText('Duplicate channel name')
        else:
            self.info.setText('')

    def _accept(self):
        if not self.controller.repo:
            self.reject()
            return
        master_row = {
            'id': None,
            'name': self.name.text(),
            'function': self.function.text() or 'Tactical',
            'rx_freq': float(self.rx.text() or 0),
            'tx_freq': float(self.tx.text() or 0) if self.tx.text() else None,
            'rx_tone': 'CSQ',
            'tx_tone': 'CSQ',
            'system': None,
            'mode': self.mode.text() or 'FMN',
            'notes': self.remarks.text(),
            'line_a': 0,
            'line_c': 0,
        }
        defaults = {
            'include_on_205': 1 if self.include_chk.isChecked() else 0,
        }
        self.controller.repo.add_from_master(master_row, defaults)
        self.accept()
