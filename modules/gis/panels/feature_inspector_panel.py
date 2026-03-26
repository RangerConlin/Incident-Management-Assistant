from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.services.spatial_repository import SpatialRepository
from modules.gis.widgets.geometry_summary_widget import GeometrySummaryWidget


class FeatureInspectorPanel(QWidget):
    """Read-focused detail panel for a selected spatial feature."""

    def __init__(self, repository: SpatialRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._feature: SpatialFeature | None = None

        layout = QVBoxLayout(self)

        identity_group = QGroupBox("Identity")
        identity_form = QFormLayout(identity_group)
        self._id_value = QLabel("-")
        self._label_value = QLabel("-")
        self._feature_type_value = QLabel("-")
        self._status_value = QLabel("-")
        identity_form.addRow("Feature ID", self._id_value)
        identity_form.addRow("Label", self._label_value)
        identity_form.addRow("Feature Type", self._feature_type_value)
        identity_form.addRow("Status", self._status_value)

        linkage_group = QGroupBox("Source Record")
        linkage_form = QFormLayout(linkage_group)
        self._source_module_value = QLabel("-")
        self._source_record_value = QLabel("-")
        linkage_form.addRow("Module", self._source_module_value)
        linkage_form.addRow("Record", self._source_record_value)

        flags_group = QGroupBox("Flags and Timestamps")
        flags_form = QFormLayout(flags_group)
        self._flags_value = QLabel("-")
        self._created_value = QLabel("-")
        self._updated_value = QLabel("-")
        flags_form.addRow("Flags", self._flags_value)
        flags_form.addRow("Created", self._created_value)
        flags_form.addRow("Updated", self._updated_value)

        self._geometry_summary = GeometrySummaryWidget(self)

        links_group = QGroupBox("Related Links")
        links_layout = QVBoxLayout(links_group)
        self._links_table = QTableWidget(0, 4)
        self._links_table.setHorizontalHeaderLabels(
            ["Module", "Record Type", "Record ID", "Relationship"]
        )
        self._links_table.verticalHeader().setVisible(False)
        links_layout.addWidget(self._links_table)

        layout.addWidget(identity_group)
        layout.addWidget(self._geometry_summary)
        layout.addWidget(linkage_group)
        layout.addWidget(flags_group)
        layout.addWidget(links_group)

    def set_feature(self, feature: SpatialFeature | None) -> None:
        self._feature = feature
        self._geometry_summary.set_feature(feature)
        self._refresh_ui()

    def load_feature(self, feature_id: int) -> None:
        self.set_feature(self._repository.get_feature(feature_id))

    def _refresh_ui(self) -> None:
        feature = self._feature
        if feature is None:
            self._id_value.setText("-")
            self._label_value.setText("-")
            self._feature_type_value.setText("-")
            self._status_value.setText("-")
            self._source_module_value.setText("-")
            self._source_record_value.setText("-")
            self._flags_value.setText("-")
            self._created_value.setText("-")
            self._updated_value.setText("-")
            self._links_table.setRowCount(0)
            return

        self._id_value.setText(str(feature.id))
        self._label_value.setText(feature.label)
        self._feature_type_value.setText(str(feature.feature_type))
        self._status_value.setText(feature.status)
        self._source_module_value.setText(feature.source_module)
        self._source_record_value.setText(
            f"{feature.source_record_type}:{feature.source_record_id}"
        )
        flags = [
            f"planning_only={feature.is_planning_only}",
            f"visible={feature.is_visible}",
            f"locked={feature.is_locked}",
            f"archived={feature.is_archived}",
        ]
        self._flags_value.setText(", ".join(flags))
        self._created_value.setText(str(feature.created_at) if feature.created_at else "-")
        self._updated_value.setText(str(feature.updated_at) if feature.updated_at else "-")

        links = self._repository.list_links_for_feature(feature.id or -1)
        self._links_table.setRowCount(len(links))
        for row, link in enumerate(links):
            self._links_table.setItem(row, 0, QTableWidgetItem(link.linked_module))
            self._links_table.setItem(row, 1, QTableWidgetItem(link.linked_record_type))
            self._links_table.setItem(row, 2, QTableWidgetItem(link.linked_record_id))
            self._links_table.setItem(row, 3, QTableWidgetItem(link.relationship_type))
