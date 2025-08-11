# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).

"""Dialog for equipment check-in and check-out."""

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class CheckInCheckoutDialog(QDialog):
    def __init__(self, mission_id: str, equipment_id: int):
        super().__init__()
        self.mission_id = mission_id
        self.equipment_id = equipment_id
        self.setWindowTitle("Check In/Out")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Equipment ID: {equipment_id}"))

        close_btn = QPushButton("Close")
        layout.addWidget(close_btn)
        close_btn.clicked.connect(self.accept)
