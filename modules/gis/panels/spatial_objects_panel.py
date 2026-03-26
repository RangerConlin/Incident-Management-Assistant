from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.services.spatial_repository import SpatialRepository


class SpatialObjectsPanel(QWidget):
    """Table-oriented panel for browsing spatial features without rendering a map."""

    featureSelected = Signal(int)

    def __init__(self, repository: SpatialRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._rows_by_id: dict[int, SpatialFeature] = {}

        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 8, self)
        self._table.setHorizontalHeaderLabels(
            [
                "Label",
                "Feature Type",
                "Geometry Type",
                "Source Module",
                "Source Record",
                "Status",
                "Layer",
                "Visible",
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.itemSelectionChanged.connect(self._emit_selection)

        layout.addWidget(self._table)

        self.reload()

    def reload(self) -> None:
        features = self._repository.list_features(include_archived=False)
        self._rows_by_id = {item.id: item for item in features if item.id is not None}

        self._table.setRowCount(len(features))
        for row, feature in enumerate(features):
            source_record = f"{feature.source_record_type}:{feature.source_record_id}"
            values = [
                feature.label,
                str(feature.feature_type),
                str(feature.geometry_type),
                feature.source_module,
                source_record,
                feature.status,
                feature.layer_key,
                "Yes" if feature.is_visible else "No",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, feature.id)
                self._table.setItem(row, col, item)

    def _emit_selection(self) -> None:
        selected = self._table.selectedItems()
        if not selected:
            return
        feature_id = selected[0].data(Qt.UserRole)
        if feature_id is None:
            return
        self.featureSelected.emit(int(feature_id))
