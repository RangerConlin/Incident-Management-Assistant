"""Items table widget for the detail panel."""

from __future__ import annotations

from PySide6 import QtWidgets


class ItemsTable(QtWidgets.QTableWidget):
    """Editable table representing request items."""

    headers = ["Kind", "Description", "Quantity", "Unit", "Special Instructions"]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, len(self.headers), parent)
        self.setHorizontalHeaderLabels(self.headers)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed)

    def set_items(self, items: list[dict[str, object]]) -> None:
        self.setRowCount(0)
        for item in items:
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QtWidgets.QTableWidgetItem(str(item.get("kind", ""))))
            self.setItem(row, 1, QtWidgets.QTableWidgetItem(str(item.get("description", ""))))
            self.setItem(row, 2, QtWidgets.QTableWidgetItem(str(item.get("quantity", ""))))
            self.setItem(row, 3, QtWidgets.QTableWidgetItem(str(item.get("unit", ""))))
            self.setItem(row, 4, QtWidgets.QTableWidgetItem(str(item.get("special_instructions", ""))))

    def items_data(self) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for row in range(self.rowCount()):
            description_item = self.item(row, 1)
            if not description_item or not description_item.text().strip():
                continue
            results.append(
                {
                    "kind": self.item(row, 0).text() if self.item(row, 0) else "SUPPLY",
                    "description": description_item.text().strip(),
                    "quantity": self.item(row, 2).text().strip() if self.item(row, 2) else "1",
                    "unit": self.item(row, 3).text().strip() if self.item(row, 3) else "unit",
                    "special_instructions": self.item(row, 4).text().strip() if self.item(row, 4) else "",
                }
            )
        return results
