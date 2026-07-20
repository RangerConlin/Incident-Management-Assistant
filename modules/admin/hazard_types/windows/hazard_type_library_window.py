"""Split-pane admin window for the Hazard Type Library."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from notifications.models import Notification
from notifications.services import get_notifier

from ..data.hazard_type_repository import ApiHazardTypeRepository
from ..models.hazard_type_models import HAZARD_CATEGORIES, HazardType
from .hazard_type_editor_window import HazardTypeDetailForm


class HazardTypeLibraryWindow(QWidget):
    """Master hazard library manager with browser + inline editor."""

    def __init__(
        self,
        repository: Optional[ApiHazardTypeRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self._hazard_repo = repository or ApiHazardTypeRepository()
        self._notifier = get_notifier()
        self._records: list[dict] = []
        self._current_hazard_id: Optional[int] = None
        self._current_hazard: Optional[HazardType] = None
        self._dirty = False
        self._loading = False

        self.setWindowTitle("Hazard Type Library")
        self.resize(1440, 920)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        root.addLayout(self._build_toolbar())
        root.addWidget(self._build_splitter(), 1)

        self._update_button_states()
        self.refresh_hazard_types()

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.new_button = QPushButton("New Hazard")
        self.duplicate_button = QPushButton("Duplicate")
        self.archive_button = QPushButton("Archive")
        self.save_button = QPushButton("Save")
        self.discard_button = QPushButton("Discard Changes")
        self.refresh_button = QPushButton("Refresh")

        for button in (
            self.new_button,
            self.duplicate_button,
            self.archive_button,
            self.save_button,
            self.discard_button,
            self.refresh_button,
        ):
            toolbar.addWidget(button)

        toolbar.addStretch(1)

        self.new_button.clicked.connect(self._new_hazard)
        self.duplicate_button.clicked.connect(self._duplicate_selected)
        self.archive_button.clicked.connect(self._toggle_active)
        self.save_button.clicked.connect(self._save_current)
        self.discard_button.clicked.connect(self._discard_changes)
        self.refresh_button.clicked.connect(self._refresh_with_prompt)
        return toolbar

    def _build_splitter(self) -> QSplitter:
        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_browser_pane())
        splitter.addWidget(self._build_editor_pane())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 980])
        return splitter

    def _build_browser_pane(self) -> QWidget:
        pane = QFrame()
        pane.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search hazards...")
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.addItems(HAZARD_CATEGORIES)
        self.active_filter = QComboBox()
        self.active_filter.addItem("Active Only", "active")
        self.active_filter.addItem("Archived Only", "archived")
        self.active_filter.addItem("All Statuses", "all")
        self.clear_filters_button = QPushButton("Clear Filters")

        filters = QHBoxLayout()
        filters.addWidget(self.category_filter, 1)
        filters.addWidget(self.active_filter, 1)
        filters.addWidget(self.clear_filters_button)

        self.count_label = QLabel("0 hazards")
        self.list_widget = QListWidget()

        layout.addWidget(self.search_edit)
        layout.addLayout(filters)
        layout.addWidget(self.count_label)
        layout.addWidget(self.list_widget, 1)

        self.search_edit.textChanged.connect(self._apply_filters)
        self.category_filter.currentIndexChanged.connect(self._apply_filters)
        self.active_filter.currentIndexChanged.connect(self._apply_filters)
        self.clear_filters_button.clicked.connect(self._clear_filters)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        return pane

    def _build_editor_pane(self) -> QWidget:
        pane = QFrame()
        pane.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.editor_title = QLabel("Hazard Details")
        self.editor_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.editor_status = QLabel("Create a new hazard or select one from the library.")
        self.editor_status.setWordWrap(True)
        self.detail_form = HazardTypeDetailForm(self)
        self.detail_form.changed.connect(self._on_form_changed)

        layout.addWidget(self.editor_title)
        layout.addWidget(self.editor_status)
        layout.addWidget(self.detail_form, 1)
        return pane

    def refresh_hazard_types(self) -> None:
        self._loading = True
        try:
            self._records = self._hazard_repo.list_hazard_types({"include_inactive": True})
        except Exception as exc:
            self._loading = False
            QMessageBox.warning(self, "Hazard Type Library", f"Unable to load hazard types.\n{exc}")
            return
        self._loading = False
        self._apply_filters()
        self._restore_selection()

    def _clear_filters(self) -> None:
        self.search_edit.clear()
        self.category_filter.setCurrentIndex(0)
        self.active_filter.setCurrentIndex(0)
        self._apply_filters()

    def _apply_filters(self) -> None:
        selected_id = self._current_hazard_id
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        search_text = self.search_edit.text().strip().lower()
        category = self.category_filter.currentText()
        active_mode = str(self.active_filter.currentData())

        filtered = []
        for record in self._records:
            active = bool(record.get("active", True))
            if active_mode == "active" and not active:
                continue
            if active_mode == "archived" and active:
                continue
            if category != "All Categories" and (record.get("category") or "") != category:
                continue
            haystack = " ".join(
                [
                    str(record.get("name") or ""),
                    str(record.get("category") or ""),
                    str(record.get("description") or ""),
                    " ".join(record.get("aliases") or []),
                    " ".join(record.get("controls") or []),
                    " ".join(record.get("ppe") or []),
                    str(record.get("standard_safety_language") or ""),
                ]
            ).lower()
            if search_text and search_text not in haystack:
                continue
            filtered.append(record)

        for record in filtered:
            item = QListWidgetItem()
            title = str(record.get("name") or "Untitled Hazard").strip()
            category_label = str(record.get("category") or "Uncategorized").strip()
            status_label = "Active" if record.get("active", True) else "Archived"
            item.setText(f"{title}\n{category_label}   {status_label}")
            item.setData(Qt.ItemDataRole.UserRole, record.get("id"))
            self.list_widget.addItem(item)
            if selected_id is not None and record.get("id") == selected_id:
                self.list_widget.setCurrentItem(item)

        self.list_widget.blockSignals(False)
        count = len(filtered)
        self.count_label.setText(f"{count} hazard" if count == 1 else f"{count} hazards")
        if self.list_widget.currentItem() is None and self.list_widget.count() > 0 and self._current_hazard_id is not None:
            self.list_widget.setCurrentRow(0)
        self._update_button_states()

    def _restore_selection(self) -> None:
        if self._current_hazard_id is None:
            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(0)
            else:
                self._set_current_hazard(None)
            return
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == self._current_hazard_id:
                self.list_widget.setCurrentItem(item)
                return
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        else:
            self._set_current_hazard(None)

    def _set_current_hazard(self, hazard_type: Optional[HazardType]) -> None:
        self._loading = True
        self._current_hazard = hazard_type
        self._current_hazard_id = hazard_type.id if hazard_type else None
        self.detail_form.set_hazard_type(hazard_type)
        self._dirty = False
        self._loading = False

        if hazard_type is None:
            self.editor_title.setText("Hazard Details")
            self.editor_status.setText("Create a new hazard or select one from the library.")
        else:
            self.editor_title.setText(hazard_type.name or "Hazard Details")
            if hazard_type.active:
                self.editor_status.setText("This master hazard is active and available for incident use.")
            else:
                self.editor_status.setText("This master hazard is archived and hidden from active-only pickers.")
        self._update_button_states()

    def _load_selected_hazard(self, hazard_id: int) -> None:
        try:
            hazard_type = self._hazard_repo.get_hazard_type(hazard_id)
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", f"Unable to load the selected hazard.\n{exc}")
            self.refresh_hazard_types()
            return
        if hazard_type is None:
            QMessageBox.warning(self, "Hazard Type Library", "The selected hazard no longer exists.")
            self.refresh_hazard_types()
            return
        self._set_current_hazard(hazard_type)

    def _on_selection_changed(
        self,
        current: Optional[QListWidgetItem],
        previous: Optional[QListWidgetItem],
    ) -> None:
        if self._loading:
            return
        if current is None:
            return
        if not self._confirm_navigation():
            self.list_widget.blockSignals(True)
            if previous is not None:
                self.list_widget.setCurrentItem(previous)
            else:
                self.list_widget.clearSelection()
            self.list_widget.blockSignals(False)
            return
        hazard_id = current.data(Qt.ItemDataRole.UserRole)
        if hazard_id is None:
            return
        self._load_selected_hazard(int(hazard_id))

    def _confirm_navigation(self) -> bool:
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Discard them and continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _on_form_changed(self) -> None:
        if self._loading:
            return
        self._dirty = True
        self._update_button_states()

    def _update_button_states(self) -> None:
        has_selection = self._current_hazard_id is not None
        active = self._current_hazard.active if self._current_hazard is not None else True
        self.duplicate_button.setEnabled(has_selection)
        self.archive_button.setEnabled(has_selection)
        self.archive_button.setText("Archive" if active else "Reactivate")
        self.save_button.setEnabled(self._dirty or self._current_hazard_id is None)
        self.discard_button.setEnabled(self._dirty)

    def _new_hazard(self) -> None:
        if not self._confirm_navigation():
            return
        self.list_widget.clearSelection()
        self._set_current_hazard(None)
        self._dirty = False
        self.editor_status.setText("New hazard. Fill in the fields, then save it to the master library.")
        self._update_button_states()

    def _save_current(self) -> None:
        if not self.detail_form.validate():
            return
        model = self.detail_form.to_model()
        try:
            if self._current_hazard_id is None:
                new_id = self._hazard_repo.create_hazard_type(model)
                self._show_toast("Hazard saved", f"'{model.name}' was added to the master library.")
                self._current_hazard_id = new_id
            else:
                self._hazard_repo.update_hazard_type(self._current_hazard_id, model)
                self._show_toast("Hazard saved", f"'{model.name}' was updated.")
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))
            return
        self._dirty = False
        self.refresh_hazard_types()
        if self._current_hazard_id is not None:
            self._load_selected_hazard(self._current_hazard_id)

    def _discard_changes(self) -> None:
        if not self._dirty:
            return
        if self._current_hazard_id is None:
            self._set_current_hazard(None)
            return
        self._load_selected_hazard(self._current_hazard_id)

    def _refresh_with_prompt(self) -> None:
        if not self._confirm_navigation():
            return
        self.refresh_hazard_types()

    def _duplicate_selected(self) -> None:
        if self._current_hazard_id is None:
            return
        if not self._confirm_navigation():
            return
        try:
            new_id = self._hazard_repo.clone_hazard_type(self._current_hazard_id)
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))
            return
        self._current_hazard_id = new_id
        self.refresh_hazard_types()
        self._load_selected_hazard(new_id)
        self._show_toast("Hazard duplicated", "Created a duplicate hazard type for editing.")

    def _toggle_active(self) -> None:
        if self._current_hazard_id is None or self._current_hazard is None:
            return
        try:
            if self._current_hazard.active:
                self._hazard_repo.deactivate_hazard_type(self._current_hazard_id)
                message = f"'{self._current_hazard.name}' was archived."
            else:
                self._hazard_repo.reactivate_hazard_type(self._current_hazard_id)
                message = f"'{self._current_hazard.name}' was reactivated."
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))
            return
        self.refresh_hazard_types()
        if self._current_hazard_id is not None:
            self._load_selected_hazard(self._current_hazard_id)
        self._show_toast("Hazard status updated", message)

    def show_templates_tab(self) -> None:
        """Compatibility no-op while the template window is redesigned separately."""
        self.raise_()
        self.activateWindow()

    def show_hazard_types_tab(self) -> None:
        self.raise_()
        self.activateWindow()

    def _show_toast(self, title: str, message: str, *, severity: str = "success") -> None:
        try:
            self._notifier.notify(
                Notification(
                    title=title,
                    message=message,
                    severity=severity if severity in {"info", "success", "warning", "error"} else "info",
                    source="Hazard Type Library",
                )
            )
        except Exception:
            pass


def open_hazard_type_library(
    parent: Optional[QWidget] = None,
    tab: int = 0,
) -> HazardTypeLibraryWindow:
    """Open or raise the Hazard Type Library window."""
    existing = getattr(parent, "_hazard_type_library_window", None) if parent is not None else None
    if isinstance(existing, HazardTypeLibraryWindow) and existing.isVisible():
        if tab == 0:
            existing.show_hazard_types_tab()
        else:
            existing.show_templates_tab()
        existing.raise_()
        existing.activateWindow()
        return existing

    window = HazardTypeLibraryWindow(parent=parent)
    if parent is not None:
        setattr(parent, "_hazard_type_library_window", window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window
