"""Items table widget for the detail panel."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from utils.table_view_styles import apply_statusboard_table_behavior

KIND_COL = 0
DESCRIPTION_COL = 1
QUANTITY_COL = 2
UNIT_COL = 3
SPECIAL_INSTRUCTIONS_COL = 4
UNIT_COST_COL = 5
TOTAL_COST_COL = 6


class ItemsTable(QtWidgets.QTableWidget):
    """Editable table representing request items, including the Finance/Admin
    cost-impact fields (estimated unit/total cost) — see
    docs/archive/design-documents/Instructions/finance_architecture.md."""

    headers = ["Kind", "Description", "Quantity", "Unit", "Special Instructions", "Est. Unit Cost", "Est. Total Cost"]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, len(self.headers), parent)
        self.setHorizontalHeaderLabels(self.headers)
        apply_statusboard_table_behavior(self, stretch_last_section=True)
        self.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed)
        self._estimate_ids: list[int | None] = []
        self.itemChanged.connect(self._on_item_changed)

    def set_items(self, items: list[dict[str, object]]) -> None:
        self.blockSignals(True)
        self.setRowCount(0)
        self._estimate_ids = []
        for item in items:
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, KIND_COL, QtWidgets.QTableWidgetItem(str(item.get("kind", ""))))
            self.setItem(row, DESCRIPTION_COL, QtWidgets.QTableWidgetItem(str(item.get("description", ""))))
            self.setItem(row, QUANTITY_COL, QtWidgets.QTableWidgetItem(str(item.get("quantity", ""))))
            self.setItem(row, UNIT_COL, QtWidgets.QTableWidgetItem(str(item.get("unit", ""))))
            self.setItem(row, SPECIAL_INSTRUCTIONS_COL, QtWidgets.QTableWidgetItem(str(item.get("special_instructions", ""))))
            unit_cost = item.get("estimated_unit_cost")
            self.setItem(row, UNIT_COST_COL, QtWidgets.QTableWidgetItem("" if unit_cost is None else f"{float(unit_cost):.2f}"))
            total_item = QtWidgets.QTableWidgetItem(self._format_total(item.get("estimated_total_cost")))
            total_item.setFlags(total_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.setItem(row, TOTAL_COST_COL, total_item)
            self._estimate_ids.append(item.get("estimate_id"))
        self.blockSignals(False)

    @staticmethod
    def _format_total(value: object) -> str:
        if value is None:
            return ""
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return ""

    def _on_item_changed(self, changed_item: QtWidgets.QTableWidgetItem) -> None:
        if changed_item.column() not in (QUANTITY_COL, UNIT_COST_COL):
            return
        row = changed_item.row()
        quantity_item = self.item(row, QUANTITY_COL)
        unit_cost_item = self.item(row, UNIT_COST_COL)
        total_item = self.item(row, TOTAL_COST_COL)
        if total_item is None:
            return
        try:
            quantity = float(quantity_item.text()) if quantity_item and quantity_item.text().strip() else None
            unit_cost = float(unit_cost_item.text()) if unit_cost_item and unit_cost_item.text().strip() else None
        except ValueError:
            return
        self.blockSignals(True)
        total_item.setText(self._format_total(quantity * unit_cost) if quantity is not None and unit_cost is not None else "")
        self.blockSignals(False)

    def items_data(self) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for row in range(self.rowCount()):
            description_item = self.item(row, DESCRIPTION_COL)
            if not description_item or not description_item.text().strip():
                continue
            unit_cost_text = self.item(row, UNIT_COST_COL).text().strip() if self.item(row, UNIT_COST_COL) else ""
            total_cost_text = self.item(row, TOTAL_COST_COL).text().strip() if self.item(row, TOTAL_COST_COL) else ""
            results.append(
                {
                    "kind": self.item(row, KIND_COL).text() if self.item(row, KIND_COL) else "SUPPLY",
                    "description": description_item.text().strip(),
                    "quantity": self.item(row, QUANTITY_COL).text().strip() if self.item(row, QUANTITY_COL) else "1",
                    "unit": self.item(row, UNIT_COL).text().strip() if self.item(row, UNIT_COL) else "unit",
                    "special_instructions": self.item(row, SPECIAL_INSTRUCTIONS_COL).text().strip() if self.item(row, SPECIAL_INSTRUCTIONS_COL) else "",
                    "estimated_unit_cost": unit_cost_text or None,
                    "estimated_total_cost": total_cost_text or None,
                    "estimate_id": self._estimate_ids[row] if row < len(self._estimate_ids) else None,
                }
            )
        return results
