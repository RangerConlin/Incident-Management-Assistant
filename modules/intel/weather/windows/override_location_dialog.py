"""Override location dialog for weather data."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class OverrideLocationDialog(QDialog):
    """Dialog allowing the user to select alternate weather coordinates."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("overrideLocationDialog")
        self.setWindowTitle("Set Weather Location")
        self.setWindowFlag(Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.button_group = QButtonGroup(self)

        self.use_icp = QRadioButton("Use ICP location", self)
        self.use_icp.setAccessibleName("Use ICP Location Option")
        self.button_group.addButton(self.use_icp, 0)
        self.use_icp.setChecked(True)
        layout.addWidget(self.use_icp)

        manual_group = QGroupBox("Manual coordinates", self)
        manual_layout = QFormLayout(manual_group)
        manual_layout.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        self.manual_option = QRadioButton("Manual coordinates", manual_group)
        self.manual_option.setAccessibleName("Manual Coordinates Option")
        self.button_group.addButton(self.manual_option, 1)
        manual_layout.addRow(self.manual_option)
        self.lat_spin = QSpinBox(manual_group)
        self.lat_spin.setRange(-90, 90)
        self.lat_spin.setAccessibleName("Latitude")
        manual_layout.addRow("Lat", self.lat_spin)
        self.lon_spin = QSpinBox(manual_group)
        self.lon_spin.setRange(-180, 180)
        self.lon_spin.setAccessibleName("Longitude")
        manual_layout.addRow("Lon", self.lon_spin)
        layout.addWidget(manual_group)

        city_group = QGroupBox("Nearest city/ZIP", self)
        city_layout = QVBoxLayout(city_group)
        self.city_option = QRadioButton("Nearest city/ZIP", city_group)
        self.city_option.setAccessibleName("Nearest City Option")
        self.button_group.addButton(self.city_option, 2)
        city_layout.addWidget(self.city_option)
        self.search_box = QLineEdit(city_group)
        self.search_box.setAccessibleName("City Search")
        city_layout.addWidget(self.search_box)
        layout.addWidget(city_group)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok, Qt.Horizontal, self
        )
        self.buttons.button(QDialogButtonBox.Ok).setText("Apply")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.button_group.idToggled.connect(lambda _id, checked: self._update_apply_state())
        self.lat_spin.valueChanged.connect(lambda _value: self._update_apply_state())
        self.lon_spin.valueChanged.connect(lambda _value: self._update_apply_state())
        self.search_box.textChanged.connect(lambda _text: self._update_apply_state())

        QWidget.setTabOrder(self.use_icp, self.manual_option)
        QWidget.setTabOrder(self.manual_option, self.lat_spin)
        QWidget.setTabOrder(self.lat_spin, self.lon_spin)
        QWidget.setTabOrder(self.lon_spin, self.city_option)
        QWidget.setTabOrder(self.city_option, self.search_box)
        QWidget.setTabOrder(self.search_box, self.buttons.button(QDialogButtonBox.Ok))

    def showEvent(self, event) -> None:  # noqa: D401
        super().showEvent(event)
        self.setFixedSize(360, 320)
        self._update_apply_state()

    # --- Accessors for selection state ---
    def selected_mode(self) -> str:
        """Return one of: 'icp', 'manual', or 'city'."""
        if self.use_icp.isChecked():
            return "icp"
        if self.manual_option.isChecked():
            return "manual"
        if self.city_option.isChecked():
            return "city"
        return "icp"

    def get_manual_coords(self) -> tuple[float, float]:
        """Return the lat/lon from the manual inputs (even if not selected)."""
        return float(self.lat_spin.value()), float(self.lon_spin.value())

    def get_city_query(self) -> str:
        """Return the nearest city/ZIP query text."""
        return self.search_box.text().strip()

    def _update_apply_state(self) -> None:
        manual_valid = self.manual_option.isChecked()
        city_valid = self.city_option.isChecked() and bool(self.search_box.text().strip())
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(manual_valid or city_valid or self.use_icp.isChecked())


def show_window(parent: QWidget | None = None) -> OverrideLocationDialog:
    dialog = OverrideLocationDialog(parent)
    dialog.open()
    return dialog


__all__ = ["OverrideLocationDialog", "show_window"]
