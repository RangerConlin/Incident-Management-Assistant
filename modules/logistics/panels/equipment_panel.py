# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).

"""Equipment inventory panel."""

from PySide6.QtWidgets import QTableWidget, QVBoxLayout, QWidget


class EquipmentPanel(QWidget):
    """Panel showing equipment items with basic table view."""

    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        self.setWindowTitle("Equipment Inventory")

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        layout.addWidget(self.table)
