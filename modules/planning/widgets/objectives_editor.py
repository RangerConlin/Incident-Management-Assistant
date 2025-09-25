"""Modeless objectives editor built with QtWidgets."""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path
import re
from typing import Iterable, List, Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    QSettings,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QBrush,
    QCloseEvent,
    QKeySequence,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)

from modules.planning.models.objectives_dao import (
    PRIORITY_VALUES,
    ObjectiveTemplate,
    ObjectivesDAO,
)


TAG_SEPARATOR = ", "
SETTINGS_GROUP = "Modules/Planning/ObjectivesEditor"


class FlowLayout(QLayout):
    """Simple flow layout that wraps child widgets."""

    def __init__(self, parent: Optional[QWidget] = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._spacing = spacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:  # type: ignore[override]
        self._items.append(item)

    def addWidget(self, widget: QWidget) -> None:
        self.addItem(QWidgetItem(widget))

    def count(self) -> int:  # type: ignore[override]
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:  # type: ignore[override]
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        return True

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:  # type: ignore[override]
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize()

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            if widget is not None and not widget.isVisible():
                continue
            size_hint = item.sizeHint()
            if size_hint.width() > rect.width() and x == rect.x():
                size_hint.setWidth(rect.width())
            next_x = x + size_hint.width() + self._spacing
            if next_x - self._spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + self._spacing
                next_x = x + size_hint.width() + self._spacing
                line_height = size_hint.height()
            else:
                line_height = max(line_height, size_hint.height())

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), size_hint))
            x = next_x

        return y + line_height - rect.y()

    def clear(self) -> None:
        while self._items:
            item = self.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()


class TagChip(QFrame):
    """Simple closable tag indicator."""

    removed = Signal(str)

    def __init__(self, tag_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tag_name = tag_name
        self.setObjectName("TagChip")
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(4)
        label = QLabel(tag_name)
        layout.addWidget(label)
        button = QToolButton()
        button.setText("✕")
        button.setCursor(Qt.PointingHandCursor)
        button.setToolTip("Remove tag")
        button.setAutoRaise(True)
        button.clicked.connect(self._on_remove_clicked)
        layout.addWidget(button)
        self.setStyleSheet(
            "#TagChip { border-radius: 12px; border: 1px solid palette(mid); }"
        )

    def tag_name(self) -> str:
        return self._tag_name

    def _on_remove_clicked(self) -> None:
        self.removed.emit(self._tag_name)


class ObjectivesTableModel(QAbstractTableModel):
    """Model presenting objective templates in a table view."""

    headers = ["Code", "Title", "Default Section", "Priority", "Tags", "Updated"]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._templates: list[ObjectiveTemplate] = []
        self._sort_column = 5
        self._sort_order = Qt.DescendingOrder

    # Qt model overrides ------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._templates)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self.headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            try:
                return self.headers[section]
            except IndexError:
                return None
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        template = self._templates[index.row()]
        column = index.column()
        if role == Qt.DisplayRole:
            if column == 0:
                return template.code or ""
            if column == 1:
                return template.title
            if column == 2:
                return template.default_section or ""
            if column == 3:
                return template.priority
            if column == 4:
                return TAG_SEPARATOR.join(template.tags)
            if column == 5:
                return template.updated_at
        if role == Qt.ToolTipRole:
            if column in (1, 2):
                return getattr(template, self._field_for_column(column)) or ""
            if column == 4:
                return TAG_SEPARATOR.join(template.tags)
        if role == Qt.ForegroundRole and not template.active:
            palette = QApplication.palette()
            disabled_color = palette.color(QPalette.Disabled, QPalette.Text)
            return QBrush(disabled_color)
        if role == Qt.BackgroundRole and column == 3:
            return self._priority_brush(template.priority)
        if role == Qt.UserRole:
            return template.id
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore[override]
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:  # type: ignore[override]
        if column < 0 or column >= len(self.headers):
            return
        self.layoutAboutToBeChanged.emit()
        reverse = order == Qt.DescendingOrder
        key_map = {
            0: lambda tpl: tpl.code or "",
            1: lambda tpl: tpl.title.lower(),
            2: lambda tpl: (tpl.default_section or "").lower(),
            3: lambda tpl: PRIORITY_VALUES.index(tpl.priority) if tpl.priority in PRIORITY_VALUES else 0,
            4: lambda tpl: TAG_SEPARATOR.join(tpl.tags).lower(),
            5: lambda tpl: tpl.updated_at,
        }
        key = key_map.get(column, lambda tpl: tpl.updated_at)
        self._templates.sort(key=key, reverse=reverse)
        self._sort_column = column
        self._sort_order = order
        self.layoutChanged.emit()

    # Public API --------------------------------------------------------
    def set_templates(self, templates: Iterable[ObjectiveTemplate]) -> None:
        self.beginResetModel()
        self._templates = list(templates)
        self.endResetModel()
        self.sort(self._sort_column, self._sort_order)

    def template_at(self, row: int) -> Optional[ObjectiveTemplate]:
        if 0 <= row < len(self._templates):
            return self._templates[row]
        return None

    def templates(self) -> List[ObjectiveTemplate]:
        return list(self._templates)

    def _field_for_column(self, column: int) -> str:
        mapping = {
            1: "title",
            2: "default_section",
        }
        return mapping.get(column, "")

    def _priority_brush(self, priority: str) -> Optional[QBrush]:
        palette = QApplication.palette()
        color: Optional[QColor]
        if priority == "Low":
            color = palette.color(QPalette.AlternateBase)
        elif priority == "High":
            color = palette.color(QPalette.Highlight).lighter(130)
        elif priority == "Urgent":
            color = palette.color(QPalette.Highlight).lighter(110)
        else:
            color = None
        if color is None:
            return None
        return QBrush(color)


class ObjectivesEditor(QDialog):
    """Modeless editor window for managing objective templates."""

    window_closed = Signal()

    def __init__(self, dao: ObjectivesDAO, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Objective Templates")
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self._dao = dao
        self._current_template: Optional[ObjectiveTemplate] = None
        self._all_templates: List[ObjectiveTemplate] = []
        self._updating_tag_list = False

        self._model = ObjectivesTableModel(self)
        self._settings = QSettings()

        self._build_ui()
        self._restore_state()
        self._load_filters(preserve_selection=False)
        self._refresh_table()
        self._register_shortcuts()

    # UI construction ---------------------------------------------------
    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        self._filter_panel = self._build_filter_panel()
        splitter.addWidget(self._filter_panel)

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.setEditTriggers(QTableView.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        table_layout.addWidget(self._table)

        splitter.addWidget(table_container)

        self._detail_panel = self._build_detail_panel()
        splitter.addWidget(self._detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)

        self._splitter = splitter

        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._focus_detail)

    def _build_filter_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        search_label = QLabel("Search")
        layout.addWidget(search_label)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search title/description/code…")
        self._search_input.returnPressed.connect(self._refresh_table)
        layout.addWidget(self._search_input)

        tags_label = QLabel("Tags")
        layout.addWidget(tags_label)
        self._tag_list = QListWidget()
        self._tag_list.setSelectionMode(QListWidget.NoSelection)
        self._tag_list.itemChanged.connect(self._refresh_table)
        layout.addWidget(self._tag_list)

        self._active_only_checkbox = QCheckBox("Active only")
        self._active_only_checkbox.setChecked(True)
        self._active_only_checkbox.toggled.connect(self._refresh_table)
        layout.addWidget(self._active_only_checkbox)

        priority_label = QLabel("Priority")
        layout.addWidget(priority_label)
        self._priority_filter = QComboBox()
        self._priority_filter.addItem("All")
        for value in PRIORITY_VALUES:
            self._priority_filter.addItem(value)
        self._priority_filter.currentIndexChanged.connect(self._apply_priority_filter)
        layout.addWidget(self._priority_filter)

        layout.addStretch()

        self._new_button = QPushButton("New")
        self._new_button.clicked.connect(self._on_new_clicked)
        layout.addWidget(self._new_button)

        self._archive_button = QPushButton("Archive")
        self._archive_button.clicked.connect(lambda: self._bulk_archive(True))
        layout.addWidget(self._archive_button)

        self._unarchive_button = QPushButton("Unarchive")
        self._unarchive_button.clicked.connect(lambda: self._bulk_archive(False))
        layout.addWidget(self._unarchive_button)

        self._delete_button = QPushButton("Delete")
        self._delete_button.clicked.connect(self._delete_selected)
        layout.addWidget(self._delete_button)

        self._export_button = QPushButton("Export CSV")
        self._export_button.clicked.connect(self._export_csv)
        layout.addWidget(self._export_button)

        return widget

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(6)

        form_group = QGroupBox("Objective Details")
        form_layout = QGridLayout(form_group)
        form_layout.setHorizontalSpacing(8)
        form_layout.setVerticalSpacing(6)

        row = 0
        form_layout.addWidget(QLabel("Code"), row, 0)
        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("Optional code (e.g., OBJ-OPS-01)")
        self._code_input.setMaxLength(40)
        form_layout.addWidget(self._code_input, row, 1)

        row += 1
        form_layout.addWidget(QLabel("Title"), row, 0)
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Objective title")
        form_layout.addWidget(self._title_input, row, 1)

        row += 1
        form_layout.addWidget(QLabel("Default Section"), row, 0)
        self._section_combo = QComboBox()
        self._section_combo.setEditable(True)
        form_layout.addWidget(self._section_combo, row, 1)

        row += 1
        form_layout.addWidget(QLabel("Priority"), row, 0)
        self._priority_combo = QComboBox()
        for priority in PRIORITY_VALUES:
            self._priority_combo.addItem(priority)
        form_layout.addWidget(self._priority_combo, row, 1)

        row += 1
        form_layout.addWidget(QLabel("Tags"), row, 0)
        tag_editor_container = QWidget()
        tag_editor_layout = QVBoxLayout(tag_editor_container)
        tag_editor_layout.setContentsMargins(0, 0, 0, 0)
        tag_editor_layout.setSpacing(4)

        tag_entry_row = QHBoxLayout()
        self._tag_input = QLineEdit()
        self._tag_input.setPlaceholderText("Add tag…")
        self._tag_input.returnPressed.connect(self._add_tag_from_input)
        tag_entry_row.addWidget(self._tag_input)
        self._tag_add_button = QPushButton("Add Tag")
        self._tag_add_button.clicked.connect(self._add_tag_from_input)
        tag_entry_row.addWidget(self._tag_add_button)
        tag_editor_layout.addLayout(tag_entry_row)

        self._tag_chip_container = QWidget()
        self._tag_chip_layout = FlowLayout(self._tag_chip_container)
        tag_editor_layout.addWidget(self._tag_chip_container)

        form_layout.addWidget(tag_editor_container, row, 1)

        row += 1
        form_layout.addWidget(QLabel("Description"), row, 0, Qt.AlignTop)
        self._description_edit = QTextEdit()
        self._description_edit.setAcceptRichText(True)
        self._description_edit.setTabChangesFocus(True)
        form_layout.addWidget(self._description_edit, row, 1)

        panel_layout.addWidget(form_group)

        self._error_label = QLabel()
        self._error_label.setObjectName("errorLabel")
        self._error_label.setStyleSheet("color: #D14343;")
        panel_layout.addWidget(self._error_label)

        button_row = QHBoxLayout()
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._on_save_clicked)
        button_row.addWidget(self._save_button)

        self._save_new_button = QPushButton("Save && New")
        self._save_new_button.clicked.connect(lambda: self._on_save_clicked(save_and_new=True))
        button_row.addWidget(self._save_new_button)

        self._revert_button = QPushButton("Revert")
        self._revert_button.clicked.connect(self._revert_changes)
        button_row.addWidget(self._revert_button)

        self._archive_toggle_button = QPushButton("Archive")
        self._archive_toggle_button.clicked.connect(self._toggle_archive_state)
        button_row.addWidget(self._archive_toggle_button)

        self._close_button = QPushButton("Close")
        self._close_button.clicked.connect(self.close)
        button_row.addWidget(self._close_button)

        button_row.addStretch()
        panel_layout.addLayout(button_row)

        self._meta_label = QLabel()
        self._meta_label.setWordWrap(True)
        panel_layout.addWidget(self._meta_label)

        panel_layout.addStretch()
        return panel

    # State persistence -------------------------------------------------
    def _restore_state(self) -> None:
        self._settings.beginGroup(SETTINGS_GROUP)
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        splitter_state = self._settings.value("splitter")
        if splitter_state:
            self._splitter.restoreState(splitter_state)
        header_state = self._settings.value("table_header")
        if header_state:
            self._table.horizontalHeader().restoreState(header_state)
        self._settings.endGroup()

    def _save_state(self) -> None:
        self._settings.beginGroup(SETTINGS_GROUP)
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter", self._splitter.saveState())
        self._settings.setValue(
            "table_header", self._table.horizontalHeader().saveState()
        )
        self._settings.endGroup()

    # Shortcuts ---------------------------------------------------------
    def _register_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._on_new_clicked)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._on_save_clicked)
        QShortcut(QKeySequence(Qt.Key_Delete), self, activated=self._delete_selected)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)

    # Filters -----------------------------------------------------------
    def _load_filters(self, preserve_selection: bool = True) -> None:
        try:
            tags = self._dao.list_tags()
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Database Error", str(exc))
            tags = []
        previous = set(self._selected_tags()) if preserve_selection else set()
        self._updating_tag_list = True
        self._tag_list.clear()
        for tag in tags:
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if tag in previous else Qt.Unchecked)
            self._tag_list.addItem(item)
        self._updating_tag_list = False

    def _selected_tags(self) -> List[str]:
        tags: list[str] = []
        for index in range(self._tag_list.count()):
            item = self._tag_list.item(index)
            if item.checkState() == Qt.Checked:
                tags.append(item.text())
        return tags

    # Data refresh ------------------------------------------------------
    def _refresh_table(self) -> None:
        if self._updating_tag_list:
            return
        include_archived = not self._active_only_checkbox.isChecked()
        search = self._search_input.text().strip() or None
        tags = self._selected_tags()
        try:
            templates = self._dao.list_templates(
                search=search,
                include_archived=include_archived,
                tag_filter=tags or None,
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Database Error", str(exc))
            return

        self._all_templates = templates
        self._apply_priority_filter()
        self._populate_section_choices()

    def _apply_priority_filter(self) -> None:
        priority = self._priority_filter.currentText()
        if priority == "All":
            filtered = self._all_templates
        else:
            filtered = [tpl for tpl in self._all_templates if tpl.priority == priority]

        selected_id = self._current_template.id if self._current_template else None
        self._model.set_templates(filtered)

        if selected_id is not None:
            if not self._select_by_id(selected_id):
                self._clear_editor()
        elif filtered:
            self._table.selectRow(0)
        else:
            self._clear_editor()

    def _populate_section_choices(self) -> None:
        sections = sorted(
            {tpl.default_section for tpl in self._all_templates if tpl.default_section}
        )
        current = self._section_combo.currentText()
        self._section_combo.blockSignals(True)
        self._section_combo.clear()
        self._section_combo.addItem("")
        for section in sections:
            self._section_combo.addItem(section)
        if current:
            index = self._section_combo.findText(current)
            if index >= 0:
                self._section_combo.setCurrentIndex(index)
            else:
                self._section_combo.setEditText(current)
        self._section_combo.blockSignals(False)

    def _select_by_id(self, template_id: int) -> bool:
        for row, template in enumerate(self._model.templates()):
            if template.id == template_id:
                index = self._model.index(row, 0)
                self._table.selectionModel().select(
                    index, QTableView.Select | QTableView.Rows
                )
                self._table.scrollTo(index)
                return True
        return False

    # Selection handling ------------------------------------------------
    def _on_selection_changed(self, *_args) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            self._clear_editor()
            return
        row = indexes[0].row()
        template = self._model.template_at(row)
        if template is None:
            self._clear_editor()
            return
        fresh = self._dao.get_template(template.id) if template.id else template
        if fresh:
            self._set_current_template(fresh)

    def _focus_detail(self, *_args) -> None:
        self._title_input.setFocus()

    # Editor state ------------------------------------------------------
    def _set_current_template(self, template: ObjectiveTemplate) -> None:
        self._current_template = replace(template)
        self._error_label.clear()

        self._code_input.setText(template.code or "")
        self._title_input.setText(template.title)
        section_text = template.default_section or ""
        index = self._section_combo.findText(section_text)
        if index >= 0:
            self._section_combo.setCurrentIndex(index)
        else:
            self._section_combo.setEditText(section_text)
        self._priority_combo.setCurrentText(template.priority)
        self._description_edit.setPlainText(template.description)
        self._refresh_tag_chips(template.tags)
        self._update_meta(template)
        self._update_archive_button(template.active)

    def _update_meta(self, template: ObjectiveTemplate) -> None:
        created = template.created_at or "—"
        updated = template.updated_at or "—"
        status = "Active" if template.active else "Archived"
        self._meta_label.setText(
            f"Status: {status}\nCreated: {created}\nUpdated: {updated}"
        )

    def _update_archive_button(self, active: bool) -> None:
        self._archive_toggle_button.setText("Archive" if active else "Unarchive")

    def _refresh_tag_chips(self, tags: Iterable[str]) -> None:
        self._tag_chip_layout.clear()
        for tag in tags:
            chip = TagChip(tag)
            chip.removed.connect(self._remove_tag)
            self._tag_chip_layout.addWidget(chip)

    def _clear_editor(self) -> None:
        self._current_template = None
        self._code_input.clear()
        self._title_input.clear()
        self._section_combo.setCurrentIndex(0)
        self._priority_combo.setCurrentIndex(1)
        self._description_edit.clear()
        self._tag_chip_layout.clear()
        self._meta_label.clear()
        self._error_label.clear()
        self._update_archive_button(True)

    # Tag editing -------------------------------------------------------
    def _current_tags(self) -> List[str]:
        return [chip.tag_name() for chip in self._iter_tag_chips()]

    def _add_tag_from_input(self) -> None:
        text = self._tag_input.text().strip()
        if not text:
            return
        existing = {chip.tag_name().lower() for chip in self._iter_tag_chips()}
        if text.lower() in existing:
            self._tag_input.clear()
            return
        chip = TagChip(text)
        chip.removed.connect(self._remove_tag)
        self._tag_chip_layout.addWidget(chip)
        self._tag_input.clear()

    def _remove_tag(self, tag_name: str) -> None:
        for chip in list(self._iter_tag_chips()):
            if chip.tag_name() == tag_name:
                chip.setParent(None)
                chip.deleteLater()
                break

    def _iter_tag_chips(self) -> Iterable[TagChip]:
        for i in range(self._tag_chip_layout.count()):
            item = self._tag_chip_layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, TagChip):
                yield widget

    # Actions -----------------------------------------------------------
    def _on_new_clicked(self) -> None:
        template = ObjectiveTemplate(priority="Normal", active=True)
        self._set_current_template(template)
        self._title_input.setFocus()

    def _on_save_clicked(self, save_and_new: bool = False) -> None:
        if not self._validate_inputs():
            return

        template = self._collect_template_from_fields()
        try:
            if template.id is None:
                new_id = self._dao.create_template(template)
                template = self._dao.get_template(new_id) or template
            else:
                self._dao.update_template(template)
                template = self._dao.get_template(template.id) or template
        except ValueError as err:
            self._error_label.setText(str(err))
            return
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Database Error", str(exc))
            return

        self._set_current_template(template)
        self._refresh_table()
        self._load_filters()
        if save_and_new:
            self._on_new_clicked()

    def _collect_template_from_fields(self) -> ObjectiveTemplate:
        template = self._current_template or ObjectiveTemplate()
        template.code = self._code_input.text().strip() or None
        template.title = self._title_input.text().strip()
        section = self._section_combo.currentText().strip()
        template.default_section = section or None
        template.priority = self._priority_combo.currentText()
        template.description = self._description_edit.toPlainText()
        template.tags = self._current_tags()
        return template

    def _validate_inputs(self) -> bool:
        title = self._title_input.text().strip()
        if not (3 <= len(title) <= 200):
            self._error_label.setText("Title must be between 3 and 200 characters.")
            self._title_input.setFocus()
            return False

        code = self._code_input.text().strip()
        if code:
            code_upper = code.upper()
            if code != code_upper:
                self._code_input.setText(code_upper)
                code = code_upper
            if not re.fullmatch(r"[A-Z0-9-]{2,40}", code):
                self._error_label.setText(
                    "Code must be 2-40 chars using A-Z, 0-9, or hyphen."
                )
                self._code_input.setFocus()
                return False

        priority = self._priority_combo.currentText()
        if priority not in PRIORITY_VALUES:
            self._error_label.setText("Priority selection is invalid.")
            self._priority_combo.setFocus()
            return False

        self._error_label.clear()
        return True

    def _revert_changes(self) -> None:
        if not self._current_template or self._current_template.id is None:
            self._on_new_clicked()
            return
        template = self._dao.get_template(self._current_template.id)
        if template:
            self._set_current_template(template)

    def _toggle_archive_state(self) -> None:
        if not self._current_template or self._current_template.id is None:
            return
        target_state = not self._current_template.active
        self._apply_archive_state(self._current_template.id, target_state)

    def _bulk_archive(self, archive: bool) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        template = self._model.template_at(indexes[0].row())
        if template and template.id is not None:
            self._apply_archive_state(template.id, archive)

    def _apply_archive_state(self, template_id: int, archive: bool) -> None:
        try:
            self._dao.set_active(template_id, not archive)
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Database Error", str(exc))
            return
        refreshed = self._dao.get_template(template_id)
        if refreshed:
            self._set_current_template(refreshed)
        self._refresh_table()

    def _delete_selected(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        template = self._model.template_at(indexes[0].row())
        if not template or template.id is None:
            return
        if template.active:
            QMessageBox.information(
                self,
                "Archive First",
                "Please archive the template before deleting it.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Delete Template",
            "Delete this template permanently?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self._dao.delete_template(template.id)
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Database Error", str(exc))
            return
        self._current_template = None
        self._refresh_table()

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Objectives", "objectives.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(self._model.headers)
                for template in self._model.templates():
                    writer.writerow(
                        [
                            template.code or "",
                            template.title,
                            template.default_section or "",
                            template.priority,
                            TAG_SEPARATOR.join(template.tags),
                            template.updated_at,
                        ]
                    )
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Export Failed", str(exc))

    # Qt events ---------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._save_state()
        self.window_closed.emit()
        super().closeEvent(event)


_open_editor: Optional[ObjectivesEditor] = None


def show_objectives_editor(app_state) -> ObjectivesEditor:
    """Create (or focus) the modeless objectives editor window."""

    global _open_editor
    if _open_editor is not None:
        _open_editor.raise_()
        _open_editor.activateWindow()
        return _open_editor

    data_dir = getattr(app_state, "data_dir", None)
    if not data_dir:
        raise RuntimeError("App state is missing data_dir")
    db_path = Path(data_dir) / "master.db"
    dao = ObjectivesDAO(db_path)
    editor = ObjectivesEditor(dao)

    def _clear_reference() -> None:
        global _open_editor
        _open_editor = None

    editor.window_closed.connect(_clear_reference)
    editor.show()
    _open_editor = editor
    return editor


if __name__ == "__main__":
    import sys
    import tempfile

    from PySide6.QtWidgets import QApplication

    class DummyState:
        def __init__(self, data_dir: str) -> None:
            self.data_dir = data_dir

    temp_dir = Path(tempfile.mkdtemp())
    db_file = temp_dir / "master.db"
    dao = ObjectivesDAO(db_file)
    # Seed sample data
    if not dao.list_templates():
        sample = ObjectiveTemplate(
            code="OBJ-OPS-01",
            title="Maintain operational communications",
            description="Ensure radios and satellite phones remain operational",
            default_section="Operations",
            priority="High",
            active=True,
            tags=["Communications", "Ops"],
        )
        dao.create_template(sample)

    app = QApplication(sys.argv)
    state = DummyState(str(temp_dir))
    editor = show_objectives_editor(state)
    editor.raise_()
    sys.exit(app.exec())

