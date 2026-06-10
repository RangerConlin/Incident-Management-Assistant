from __future__ import annotations

from PySide6.QtWidgets import QLabel, QFormLayout, QGroupBox, QPlainTextEdit, QVBoxLayout, QWidget

from modules.gis.models.spatial_feature import SpatialFeature


class GeometrySummaryWidget(QWidget):
    """Read-only geometry summary used by GIS inspection panels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        group = QGroupBox("Geometry")
        form = QFormLayout(group)
        self._geometry_type_value = QLabel("-")
        self._centroid_value = QLabel("-")
        self._bounds_value = QLabel("-")

        self._wkt_preview = QPlainTextEdit()
        self._wkt_preview.setReadOnly(True)
        self._wkt_preview.setPlaceholderText("No geometry loaded")
        self._wkt_preview.setMaximumBlockCount(40)

        form.addRow("Type", self._geometry_type_value)
        form.addRow("Centroid", self._centroid_value)
        form.addRow("Bounds", self._bounds_value)
        form.addRow("WKT", self._wkt_preview)

        layout.addWidget(group)

    def set_feature(self, feature: SpatialFeature | None) -> None:
        if feature is None:
            self._geometry_type_value.setText("-")
            self._centroid_value.setText("-")
            self._bounds_value.setText("-")
            self._wkt_preview.setPlainText("")
            return

        self._geometry_type_value.setText(str(feature.geometry_type))
        if feature.centroid_lat is not None and feature.centroid_lon is not None:
            self._centroid_value.setText(f"{feature.centroid_lat:.6f}, {feature.centroid_lon:.6f}")
        else:
            self._centroid_value.setText("Not computed")

        if None not in (
            feature.bbox_min_lat,
            feature.bbox_min_lon,
            feature.bbox_max_lat,
            feature.bbox_max_lon,
        ):
            self._bounds_value.setText(
                f"[{feature.bbox_min_lat:.6f}, {feature.bbox_min_lon:.6f}]"
                f" - [{feature.bbox_max_lat:.6f}, {feature.bbox_max_lon:.6f}]"
            )
        else:
            self._bounds_value.setText("Not computed")

        self._wkt_preview.setPlainText(feature.geometry_wkt or "")
