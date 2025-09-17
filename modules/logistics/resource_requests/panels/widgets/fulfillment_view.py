"""Fulfillment summary widget."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class FulfillmentView(QtWidgets.QWidget):
    """Displays fulfillment details with lightweight action hooks."""

    assignRequested = QtCore.Signal()
    updateRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        self.status_label = QtWidgets.QLabel("No fulfillment recorded")
        self.supplier_label = QtWidgets.QLabel("-")
        self.team_label = QtWidgets.QLabel("-")
        self.vehicle_label = QtWidgets.QLabel("-")
        self.eta_label = QtWidgets.QLabel("-")
        form.addRow("Status", self.status_label)
        form.addRow("Supplier", self.supplier_label)
        form.addRow("Team", self.team_label)
        form.addRow("Vehicle", self.vehicle_label)
        form.addRow("ETA", self.eta_label)
        layout.addLayout(form)

        button_bar = QtWidgets.QHBoxLayout()
        self.assign_button = QtWidgets.QPushButton("Assign…")
        self.assign_button.clicked.connect(self.assignRequested)
        self.update_button = QtWidgets.QPushButton("Update Status…")
        self.update_button.clicked.connect(self.updateRequested)
        button_bar.addWidget(self.assign_button)
        button_bar.addWidget(self.update_button)
        button_bar.addStretch(1)
        layout.addLayout(button_bar)

    def set_fulfillment(self, record: dict[str, object] | None) -> None:
        if not record:
            self.status_label.setText("No fulfillment recorded")
            self.supplier_label.setText("-")
            self.team_label.setText("-")
            self.vehicle_label.setText("-")
            self.eta_label.setText("-")
            self.update_button.setEnabled(False)
            return

        self.status_label.setText(str(record.get("status", "")))
        self.supplier_label.setText(str(record.get("supplier_id", "-")))
        self.team_label.setText(str(record.get("assigned_team_id", "-")))
        self.vehicle_label.setText(str(record.get("assigned_vehicle_id", "-")))
        self.eta_label.setText(str(record.get("eta_utc", "-")))
        self.update_button.setEnabled(True)
