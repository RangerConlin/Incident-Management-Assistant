"""Filters bar widget used in the request list panel."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ...models.enums import Priority, RequestStatus


class FiltersBar(QtWidgets.QWidget):
    """Compact widget exposing filtering controls for the list view."""

    filtersChanged = QtCore.Signal(dict)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._debounce = QtCore.QTimer(self)
        self._debounce.setInterval(250)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._emit_filters)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.status_buttons: dict[RequestStatus, QtWidgets.QToolButton] = {}
        status_container = QtWidgets.QWidget(self)
        status_layout = QtWidgets.QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(4)
        for status in RequestStatus:
            button = QtWidgets.QToolButton(status_container)
            button.setText(status.value.title())
            button.setCheckable(True)
            button.clicked.connect(self._emit_filters)
            self.status_buttons[status] = button
            status_layout.addWidget(button)
        layout.addWidget(status_container)

        self.priority_combo = QtWidgets.QComboBox(self)
        self.priority_combo.addItem("All Priorities", None)
        for priority in Priority:
            self.priority_combo.addItem(priority.value.title(), priority.value)
        self.priority_combo.currentIndexChanged.connect(self._emit_filters)
        layout.addWidget(self.priority_combo)

        self.start_date = QtWidgets.QDateEdit(self)
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setSpecialValueText("Start")
        self.start_date.setDate(self.start_date.minimumDate())
        self.start_date.dateChanged.connect(self._emit_filters)
        layout.addWidget(self.start_date)

        self.end_date = QtWidgets.QDateEdit(self)
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setSpecialValueText("End")
        self.end_date.setDate(self.end_date.minimumDate())
        self.end_date.dateChanged.connect(self._emit_filters)
        layout.addWidget(self.end_date)

        self.search_field = QtWidgets.QLineEdit(self)
        self.search_field.setPlaceholderText("Search requests…")
        self.search_field.textChanged.connect(self._on_search_text)
        layout.addWidget(self.search_field, stretch=1)

        layout.addStretch(1)

    # ------------------------------------------------------------------ helpers
    def _on_search_text(self, _: str) -> None:
        self._debounce.start()

    def _emit_filters(self) -> None:
        self.filtersChanged.emit(self.filters())

    # ------------------------------------------------------------------ API
    def filters(self) -> dict[str, object]:
        status = [status.value for status, button in self.status_buttons.items() if button.isChecked()]
        priority = self.priority_combo.currentData()
        start = (
            self.start_date.date().toString("yyyy-MM-dd")
            if self.start_date.date() != self.start_date.minimumDate()
            else None
        )
        end = (
            self.end_date.date().toString("yyyy-MM-dd")
            if self.end_date.date() != self.end_date.minimumDate()
            else None
        )
        text = self.search_field.text().strip() or None

        filters: dict[str, object] = {}
        if status:
            filters["status"] = status
        if priority:
            filters["priority"] = priority
        if start:
            filters["start"] = f"{start}T00:00:00Z"
        if end:
            filters["end"] = f"{end}T23:59:59Z"
        if text:
            filters["text"] = text
        return filters

    def set_filters(self, filters: dict[str, object]) -> None:
        for status, button in self.status_buttons.items():
            button.setChecked(status.value in filters.get("status", []))
        priority = filters.get("priority")
        index = self.priority_combo.findData(priority)
        self.priority_combo.setCurrentIndex(index if index >= 0 else 0)
        if "start" in filters:
            self.start_date.setDate(QtCore.QDate.fromString(filters["start"][:10], "yyyy-MM-dd"))
        if "end" in filters:
            self.end_date.setDate(QtCore.QDate.fromString(filters["end"][:10], "yyyy-MM-dd"))
        if "text" in filters:
            self.search_field.setText(filters["text"])
        self._emit_filters()
