"""Qt widgets panel presenting the vehicle inventory list."""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer, QModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtCore import QAbstractTableModel

from .vehicle_edit_window import VehicleEditDialog, VehicleRepository

logger = logging.getLogger(__name__)


class VehicleTableModel(QAbstractTableModel):
    """Simple table model to display vehicles in a QTableView."""

    _COLUMNS: list[tuple[str, str]] = [
        ("id", "ID"),
        ("vin", "VIN"),
        ("license_plate", "Plate"),
        ("year", "Year"),
        ("make", "Make"),
        ("model", "Model"),
        ("capacity", "Capacity"),
        ("type_id", "Type"),
        ("status_id", "Status"),
        ("tags", "Tags"),
        ("organization", "Organization"),
    ]

    def __init__(self, vehicles: Optional[list[dict[str, Any]]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._vehicles: list[dict[str, Any]] = vehicles or []

    # ------------------------------------------------------------------
    # Qt model interface
    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        if parent and parent.isValid():
            return 0
        return len(self._vehicles)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        if parent and parent.isValid():
            return 0
        return len(self._COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        record = self._vehicles[index.row()]
        key, _ = self._COLUMNS[index.column()]
        value = record.get(key)

        if role in (Qt.DisplayRole, Qt.EditRole):
            if value is None:
                return ""
            if isinstance(value, list):
                return ", ".join(str(item) for item in value)
            return str(value)

        if role == Qt.TextAlignmentRole:
            if key in {"id", "year", "capacity"}:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            try:
                return self._COLUMNS[section][1]
            except IndexError:  # pragma: no cover - defensive
                return None
        return str(section + 1)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def set_vehicles(self, vehicles: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._vehicles = vehicles
        self.endResetModel()

    def vehicle_at(self, row: int) -> Optional[dict[str, Any]]:
        if 0 <= row < len(self._vehicles):
            return self._vehicles[row]
        return None

    def find_row_by_id(self, vehicle_id: Any) -> int:
        target = str(vehicle_id)
        for idx, record in enumerate(self._vehicles):
            if str(record.get("id")) == target:
                return idx
        return -1


class VehicleInventoryWidget(QWidget):
    """Widget exposing search and CRUD controls for vehicles."""

    def __init__(
        self,
        repository: Optional[VehicleRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository or VehicleRepository()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(350)
        self._search_timer.timeout.connect(self._apply_search)

        self._model = VehicleTableModel(parent=self)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setDynamicSortFilter(True)
        self._proxy_model.setSortCaseSensitivity(Qt.CaseInsensitive)

        self.search_edit: QLineEdit
        self.table_view: QTableView
        self.add_button: QPushButton
        self.edit_button: QPushButton
        self.delete_button: QPushButton
        self.refresh_button: QPushButton

        self._setup_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search vehicles")
        self.search_edit.setAccessibleName("Search vehicles")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.returnPressed.connect(self._apply_search)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setAccessibleName("Refresh vehicle list")
        self.refresh_button.clicked.connect(self.refresh)

        search_row.addWidget(search_label)
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.refresh_button)
        layout.addLayout(search_row)

        self.table_view = QTableView()
        self.table_view.setModel(self._proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.sortByColumn(4, Qt.AscendingOrder)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.doubleClicked.connect(self._open_selected_vehicle)
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setSortIndicatorShown(True)

        # Context actions for keyboard shortcuts
        delete_action = QAction("Delete Vehicle", self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        delete_action.triggered.connect(self._delete_selected_vehicle)
        self.addAction(delete_action)

        layout.addWidget(self.table_view, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        self.add_button = QPushButton("Add")
        self.add_button.setAccessibleName("Add vehicle")
        self.add_button.clicked.connect(self._open_add_vehicle)
        button_row.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setAccessibleName("Edit selected vehicle")
        self.edit_button.clicked.connect(self._open_selected_vehicle)
        button_row.addWidget(self.edit_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setAccessibleName("Delete selected vehicle")
        self.delete_button.clicked.connect(self._delete_selected_vehicle)
        button_row.addWidget(self.delete_button)

        layout.addLayout(button_row)

        selection_model = self.table_view.selectionModel()
        selection_model.selectionChanged.connect(lambda *_: self._update_actions_state())
        self._update_actions_state()

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.load_data()

    def load_data(self, *, select_id: Any | None = None) -> None:
        current_selection = self.selected_vehicle_id()
        target_id = select_id if select_id is not None else current_selection

        search_text = self.search_edit.text().strip()

        try:
            vehicles = self._repository.list_vehicles(search_text or None)
        except Exception as exc:  # pragma: no cover - UI branch
            logger.error("Failed to load vehicles: %s", exc)
            QMessageBox.critical(
                self,
                "Unable to Load Vehicles",
                f"The vehicle list could not be loaded.\n\n{exc}",
            )
            return

        self._model.set_vehicles(vehicles)
        self.table_view.resizeColumnsToContents()
        self._update_actions_state()

        if target_id is not None:
            self.select_vehicle(target_id)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------
    def selected_vehicle(self) -> Optional[dict[str, Any]]:
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return None
        indexes = selection_model.selectedRows()
        if not indexes:
            return None
        proxy_index = indexes[0]
        source_index = self._proxy_model.mapToSource(proxy_index)
        return self._model.vehicle_at(source_index.row())

    def selected_vehicle_id(self) -> Any | None:
        record = self.selected_vehicle()
        if record is None:
            return None
        return record.get("id")

    def select_vehicle(self, vehicle_id: Any) -> None:
        row = self._model.find_row_by_id(vehicle_id)
        if row < 0:
            self.table_view.clearSelection()
            return
        source_index = self._model.index(row, 0)
        proxy_index = self._proxy_model.mapFromSource(source_index)
        if proxy_index.isValid():
            self.table_view.selectRow(proxy_index.row())
            self.table_view.scrollTo(proxy_index, QTableView.PositionAtCenter)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------
    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _apply_search(self) -> None:
        self.load_data()

    def _update_actions_state(self) -> None:
        has_selection = self.selected_vehicle() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _open_add_vehicle(self) -> None:
        dialog = VehicleEditDialog(repository=self._repository, parent=self)
        dialog.vehicleSaved.connect(self._handle_vehicle_saved)
        dialog.exec()

    def _open_selected_vehicle(self, _index: QModelIndex | None = None) -> None:
        vehicle_id = self.selected_vehicle_id()
        if vehicle_id is None:
            return
        dialog = VehicleEditDialog(vehicle_id=vehicle_id, repository=self._repository, parent=self)
        dialog.vehicleSaved.connect(self._handle_vehicle_saved)
        dialog.exec()

    def _handle_vehicle_saved(self, record: dict[str, Any]) -> None:
        self.load_data(select_id=record.get("id"))

    def _delete_selected_vehicle(self) -> None:
        record = self.selected_vehicle()
        if record is None:
            return

        vehicle_id = record.get("id")
        if vehicle_id is None:
            return

        confirmation = QMessageBox.question(
            self,
            "Delete Vehicle",
            f"Are you sure you want to delete vehicle #{vehicle_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmation != QMessageBox.Yes:
            return

        try:
            self._repository.delete_vehicle(vehicle_id)
        except LookupError as exc:  # pragma: no cover - UI branch
            QMessageBox.warning(
                self,
                "Vehicle Not Found",
                f"The selected vehicle could not be deleted.\n\n{exc}",
            )
        except Exception as exc:  # pragma: no cover - UI branch
            logger.error("Failed to delete vehicle %s: %s", vehicle_id, exc)
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"The vehicle could not be deleted.\n\n{exc}",
            )
        else:
            self.load_data()


class VehicleInventoryDialog(QDialog):
    """Modal window wrapping :class:`VehicleInventoryWidget`."""

    def __init__(
        self,
        repository: Optional[VehicleRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Vehicles")
        self.setModal(True)
        self.setMinimumSize(960, 560)

        layout = QVBoxLayout(self)
        self.inventory_widget = VehicleInventoryWidget(repository=repository, parent=self)
        layout.addWidget(self.inventory_widget)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.setAutoDefault(True)
        close_button.clicked.connect(self.reject)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.inventory_widget.setFocus()

