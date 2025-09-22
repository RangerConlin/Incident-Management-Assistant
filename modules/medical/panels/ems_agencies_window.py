"""Modeless management window for EMS agencies."""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

from PySide6.QtCore import QByteArray, QModelIndex, QPoint, Qt, QTimer, QObject, QItemSelectionModel, QItemSelection
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QTableView,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QDialog,
    QVBoxLayout,
    QWidget,
    QDateEdit,
    QAbstractItemView,
    QHeaderView,
)
from PySide6.QtCore import QAbstractTableModel
from PySide6.QtCore import QDate
from PySide6.QtCore import QSettings

from styles import styles as app_styles
from styles import tokens
from utils.state import AppState
from utils.app_signals import app_signals
from models.database import get_incident_by_number

from ..data.ems_agencies_schema import (
    EMSAgencyRepository,
    DuplicateGroup,
    import_to_ics206,
)
from ..widgets.ems_agency_dialog import EMSAgencyDialog

logger = logging.getLogger(__name__)


@dataclass
class Column:
    key: str
    title: str
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


class ChipDelegate(QStyledItemDelegate):
    """Paint a pill style background for certain table values."""

    def __init__(self, resolver: Callable[[Any], tuple[QColor | None, QColor | None]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._resolver = resolver

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        display_value = index.data(Qt.DisplayRole)
        raw_value = index.data(Qt.UserRole)
        bg, fg = self._resolver(raw_value if raw_value is not None else display_value)
        if not bg or not fg:
            super().paint(painter, option, index)
            return
        painter.save()
        rect = option.rect.adjusted(6, 6, -6, -6)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = rect.height() / 2
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(QPen(fg))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(display_value))
        painter.restore()


class EMSAgencyTableModel(QAbstractTableModel):
    columns: Sequence[Column] = (
        Column("name", "Name"),
        Column("type", "Type"),
        Column("phone", "Phone"),
        Column("radio_channel", "Radio/Channel"),
        Column("address", "Address"),
        Column("city", "City"),
        Column("state", "State"),
        Column("zip", "ZIP"),
        Column("lat", "Lat", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
        Column("lon", "Lon", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
        Column("default_on_206", "Default on 206"),
        Column("is_active", "Active"),
        Column("updated_at", "Updated"),
    )

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._sort_column = 0
        self._sort_order = Qt.SortOrder.AscendingOrder

    # Qt model API ------------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: D401 - Qt API
        return 0 if parent and parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: D401 - Qt API
        return len(self.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: D401
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = self.columns[index.column()]
        value = row.get(column.key)
        if role == Qt.DisplayRole:
            if column.key in {"lat", "lon"}:
                return "" if value in (None, "") else f"{float(value):.5f}"
            if column.key in {"default_on_206", "is_active"}:
                return "Yes" if bool(value) else "No"
            return "" if value is None else str(value)
        if role == Qt.UserRole:
            if column.key in {"default_on_206", "is_active"}:
                return bool(value)
            return value
        if role == Qt.TextAlignmentRole:
            return int(column.alignment)
        if role == Qt.FontRole and not bool(row.get("is_active", True)):
            font = QFont()
            font.setStrikeOut(True)
            return font
        if role == Qt.ForegroundRole and not bool(row.get("is_active", True)):
            palette = app_styles.get_palette()
            return QColor(palette["muted"])
        if role == Qt.ToolTipRole and not bool(row.get("is_active", True)):
            return "Inactive — use Restore to reactivate."
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # noqa: D401
        if orientation == Qt.Orientation.Horizontal and role == Qt.DisplayRole:
            return self.columns[section].title
        return super().headerData(section, orientation, role)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:  # noqa: D401
        if column < 0 or column >= len(self.columns):
            return
        key = self.columns[column].key
        reverse = order == Qt.SortOrder.DescendingOrder
        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=lambda row: (self._sort_value(row.get(key)), str(row.get(key) or "")), reverse=reverse)
        self.layoutChanged.emit()
        self._sort_column = column
        self._sort_order = order

    # Helpers -----------------------------------------------------------
    def update_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = [dict(row) for row in rows]
        self.endResetModel()
        self.sort(self._sort_column, self._sort_order)

    def row_data(self, row: int) -> dict[str, Any]:
        return self._rows[row]

    def _sort_value(self, value: Any) -> Any:
        if value is None:
            return ""
        return value


class AuditLogModel(QAbstractTableModel):
    columns: Sequence[Column] = (
        Column("ts_utc", "Timestamp"),
        Column("action", "Action"),
        Column("target", "Target"),
        Column("details", "Old → New"),
        Column("user", "User"),
    )

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: D401
        return 0 if parent and parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: D401
        return len(self.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: D401
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = self.columns[index.column()]
        if role == Qt.DisplayRole:
            return row.get(column.key, "")
        if role == Qt.TextAlignmentRole:
            return int(column.alignment)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # noqa: D401
        if orientation == Qt.Orientation.Horizontal and role == Qt.DisplayRole:
            return self.columns[section].title
        return super().headerData(section, orientation, role)

    def update_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = [dict(row) for row in rows]
        self.endResetModel()


class EMSAgenciesWindow(QMainWindow):
    """Floating catalogue manager for EMS agencies."""

    settings_group = "windows/ems_agencies"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.repository = EMSAgencyRepository()
        self.model = EMSAgencyTableModel(self)
        self.audit_model = AuditLogModel(self)
        self._search_timer = QTimer(self)
        self._search_timer.setInterval(250)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._refresh_table)
        self._search_text = ""
        self._include_inactive = True
        self._build_ui()
        self._restore_geometry()
        self._refresh_all()
        self._register_signals()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(self._compose_title())

        toolbar = QToolBar("EMS Agencies Toolbar", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.act_new = QAction("New", self)
        self.act_new.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key_N))
        self.act_edit = QAction("Edit", self)
        self.act_edit.setShortcut(QKeySequence(Qt.Key_Return))
        self.act_delete = QAction("Delete", self)
        self.act_delete.setShortcut(QKeySequence(Qt.Key_Delete))
        self.act_refresh = QAction("Refresh", self)
        self.act_refresh.setShortcut(QKeySequence(Qt.Key_F5))

        toolbar.addAction(self.act_new)
        toolbar.addAction(self.act_edit)
        toolbar.addAction(self.act_delete)

        self.import_button = QToolButton(self)
        self.import_button.setText("Import to ICS-206")
        self.import_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        import_menu = QMenu(self)
        self.act_import_append = import_menu.addAction("Add selected to current ICS-206…")
        self.act_import_create = import_menu.addAction("Create new ICS-206 from selected…")
        self.import_button.setMenu(import_menu)
        toolbar.addWidget(self.import_button)

        self.export_button = QToolButton(self)
        self.export_button.setText("Export")
        self.export_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        export_menu = QMenu(self)
        self.act_export_csv = export_menu.addAction("Export CSV…")
        self.act_export_print = export_menu.addAction("Print…")
        self.export_button.setMenu(export_menu)
        toolbar.addWidget(self.export_button)

        toolbar.addAction(self.act_refresh)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search name, type, phone, city…")
        self.search_edit.setClearButtonEnabled(True)
        toolbar.addWidget(self.search_edit)

        # Tabs -----------------------------------------------------------
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)

        # Directory tab
        directory = QWidget()
        dir_layout = QVBoxLayout(directory)
        dir_layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING)
        dir_layout.setSpacing(tokens.DEFAULT_PADDING)
        self.table = QTableView(directory)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        dir_layout.addWidget(self.table)
        self.status_label = QLabel()
        dir_layout.addWidget(self.status_label)
        self.tabs.addTab(directory, "Directory")

        # Duplicates tab
        dupes = QWidget()
        dup_layout = QVBoxLayout(dupes)
        dup_layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING)
        dup_layout.setSpacing(tokens.DEFAULT_PADDING)
        hint = QLabel("Potential duplicates detected by matching names/phones.")
        pal = app_styles.get_palette()
        hint.setStyleSheet(f"color: {pal['muted'].name()};")
        dup_layout.addWidget(hint)
        self.duplicate_tree = QTreeWidget()
        self.duplicate_tree.setHeaderLabels(["Agency", "Type", "Phone", "City", "Active"])
        self.duplicate_tree.setUniformRowHeights(True)
        dup_layout.addWidget(self.duplicate_tree)
        dup_buttons = QHBoxLayout()
        dup_buttons.addStretch(1)
        self.merge_button = QPushButton("Merge selected…")
        dup_buttons.addWidget(self.merge_button)
        dup_layout.addLayout(dup_buttons)
        self.tabs.addTab(dupes, "Duplicates")

        # Audit tab
        audit = QWidget()
        audit_layout = QVBoxLayout(audit)
        audit_layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING)
        audit_layout.setSpacing(tokens.DEFAULT_PADDING)
        filter_row = QHBoxLayout()
        self.audit_start = QDateEdit()
        self.audit_start.setCalendarPopup(True)
        self.audit_start.setDisplayFormat("yyyy-MM-dd")
        self.audit_start.setSpecialValueText("Any")
        self.audit_start.setDateRange(QDate(1970, 1, 1), QDate(7999, 12, 31))
        self.audit_start.setDate(self.audit_start.minimumDate())
        self.audit_end = QDateEdit()
        self.audit_end.setCalendarPopup(True)
        self.audit_end.setDisplayFormat("yyyy-MM-dd")
        self.audit_end.setSpecialValueText("Any")
        self.audit_end.setDateRange(QDate(1970, 1, 1), QDate(7999, 12, 31))
        self.audit_end.setDate(self.audit_end.minimumDate())
        self.audit_user = QLineEdit()
        self.audit_user.setPlaceholderText("User")
        filter_row.addWidget(QLabel("Start:"))
        filter_row.addWidget(self.audit_start)
        filter_row.addWidget(QLabel("End:"))
        filter_row.addWidget(self.audit_end)
        filter_row.addWidget(QLabel("User:"))
        filter_row.addWidget(self.audit_user)
        self.audit_action_combo = QLineEdit()
        self.audit_action_combo.setPlaceholderText("Action (create/update/deactivate…)")
        filter_row.addWidget(self.audit_action_combo)
        self.audit_apply = QPushButton("Apply")
        filter_row.addWidget(self.audit_apply)
        self.audit_export = QPushButton("Export CSV…")
        filter_row.addWidget(self.audit_export)
        filter_row.addStretch(1)
        audit_layout.addLayout(filter_row)
        self.audit_table = QTableView()
        self.audit_table.setModel(self.audit_model)
        self.audit_table.horizontalHeader().setStretchLastSection(True)
        self.audit_table.verticalHeader().setVisible(False)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.audit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        audit_layout.addWidget(self.audit_table)
        self.tabs.addTab(audit, "Audit Log")

        central = QWidget(self)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        # Delegates
        self.table.setItemDelegateForColumn(1, ChipDelegate(self._type_chip_colors, self.table))
        default_idx = self._column_index("default_on_206")
        active_idx = self._column_index("is_active")
        if default_idx >= 0:
            self.table.setItemDelegateForColumn(default_idx, ChipDelegate(self._default_chip_colors, self.table))
        if active_idx >= 0:
            self.table.setItemDelegateForColumn(active_idx, ChipDelegate(self._active_chip_colors, self.table))

        # Actions
        self.act_new.triggered.connect(self._new_agency)
        self.act_edit.triggered.connect(self._edit_selected)
        self.act_delete.triggered.connect(self._toggle_selected)
        self.act_refresh.triggered.connect(self._refresh_all)
        self.act_import_append.triggered.connect(lambda: self._import_selected("append"))
        self.act_import_create.triggered.connect(lambda: self._import_selected("create"))
        self.act_export_csv.triggered.connect(self._export_csv)
        self.act_export_print.triggered.connect(self._print_placeholder)
        self.import_button.clicked.connect(lambda: self._import_selected("append"))
        self.export_button.clicked.connect(self._export_csv)
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.table.doubleClicked.connect(lambda _: self._edit_selected())
        sel_model = self.table.selectionModel()
        if sel_model:
            sel_model.selectionChanged.connect(lambda *_: self._update_action_state())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._open_context_menu)
        self.merge_button.clicked.connect(self._merge_selected_group)
        self.audit_apply.clicked.connect(self._refresh_audit)
        self.audit_export.clicked.connect(self._export_audit_csv)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Shortcuts
        QShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key_F), self, activated=self.search_edit.setFocus)

        self._update_action_state()

    # ------------------------------------------------------------------
    def _register_signals(self) -> None:
        try:
            app_signals.incidentChanged.connect(lambda _number: self._handle_context_change())
            app_signals.opPeriodChanged.connect(lambda _op: self._handle_context_change())
            app_signals.userChanged.connect(lambda *_: self._handle_context_change())
        except Exception:
            logger.exception("Failed to subscribe to app signals")

    # ------------------------------------------------------------------
    def _handle_context_change(self) -> None:
        self.setWindowTitle(self._compose_title())

    # ------------------------------------------------------------------
    def _refresh_all(self) -> None:
        self._refresh_table()
        self._refresh_duplicates()
        self._refresh_audit()

    def _refresh_table(self) -> None:
        rows = self.repository.list_agencies(search=self._search_text, include_inactive=self._include_inactive)
        selected_ids = set(self._selected_ids())
        self.model.update_rows(rows)
        self._reselect_ids(selected_ids)
        self.table.resizeColumnsToContents()
        self.status_label.setText(f"{len(rows)} agencies")
        self._update_action_state()

    def _refresh_duplicates(self) -> None:
        self.duplicate_tree.clear()
        groups = self.repository.duplicate_groups()
        for group, members in groups:
            top = QTreeWidgetItem([f"Group ({group.reason})", "", "", "", ""])
            top.setData(0, Qt.ItemDataRole.UserRole, group)
            self.duplicate_tree.addTopLevelItem(top)
            for row in members:
                child = QTreeWidgetItem([
                    str(row.get("name", "")),
                    str(row.get("type", "")),
                    str(row.get("phone", "")),
                    str(row.get("city", "")),
                    "Active" if row.get("is_active") else "Inactive",
                ])
                child.setData(0, Qt.ItemDataRole.UserRole, int(row.get("id")))
                top.addChild(child)
            top.setExpanded(True)
        self.merge_button.setEnabled(bool(groups))

    def _refresh_audit(self) -> None:
        start = self._date_to_iso(self.audit_start.date(), minimum=self.audit_start.minimumDate())
        end = self._date_to_iso(self.audit_end.date(), minimum=self.audit_end.minimumDate(), end_of_day=True)
        action_filter = self.audit_action_combo.text().strip() or None
        user = self.audit_user.text().strip() or None
        rows_raw = self.repository.list_audit_entries(start=start, end=end, user_filter=user, action_filter=_map_action_filter(action_filter))
        rows = [self._format_audit_row(entry) for entry in rows_raw]
        self.audit_model.update_rows(rows)
        self.audit_table.resizeColumnsToContents()

    def _compose_title(self) -> str:
        incident_number = AppState.get_active_incident()
        if incident_number:
            record = get_incident_by_number(incident_number)
            name = record.get("name") if record else None
            if name:
                return f"EMS Agencies — {name}"
            return f"EMS Agencies — Incident {incident_number}"
        return "EMS Agencies — No Active Incident"

    def _type_chip_colors(self, value: Any) -> tuple[QColor | None, QColor | None]:
        palette = app_styles.get_palette()
        base = palette["accent"]
        if str(value) == "Hospital":
            base = palette["success"]
        elif str(value) == "Medical Aid":
            base = palette["warning"]
        fg = palette["bg"]
        return QColor(base), QColor(fg)

    def _default_chip_colors(self, value: Any) -> tuple[QColor | None, QColor | None]:
        palette = app_styles.get_palette()
        if not bool(value):
            return QColor(palette["muted"]), QColor(palette["bg"])
        return QColor(palette["success"]), QColor(palette["bg"])

    def _active_chip_colors(self, value: Any) -> tuple[QColor | None, QColor | None]:
        palette = app_styles.get_palette()
        if bool(value):
            return QColor(palette["success"]), QColor(palette["bg"])
        return QColor(palette["muted"]), QColor(palette["bg"])

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self._search_timer.start()

    def _selected_ids(self) -> list[int]:
        selection = self.table.selectionModel()
        if not selection:
            return []
        ids = []
        for idx in selection.selectedRows():
            row = self.model.row_data(idx.row())
            if row.get("id") is not None:
                ids.append(int(row["id"]))
        return ids

    def _reselect_ids(self, ids: Iterable[int]) -> None:
        id_set = {int(i) for i in ids}
        if not id_set:
            return
        selection = self.table.selectionModel()
        if not selection:
            return
        selection.clearSelection()
        for row_index in range(self.model.rowCount()):
            row = self.model.row_data(row_index)
            if int(row.get("id", -1)) in id_set:
                top_left = self.model.index(row_index, 0)
                bottom_right = self.model.index(row_index, self.model.columnCount() - 1)
                selection.select(QItemSelection(top_left, bottom_right), QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def _update_action_state(self) -> None:
        ids = self._selected_ids()
        self.act_edit.setEnabled(len(ids) == 1)
        self.act_delete.setEnabled(bool(ids))
        if not ids:
            self.act_delete.setText("Delete")
            return
        rows = [self.repository.get(i) for i in ids]
        actives = [row for row in rows if row and row.get("is_active")]
        if actives and len(actives) == len(rows):
            self.act_delete.setText("Delete")
        elif not actives:
            self.act_delete.setText("Restore")
        else:
            self.act_delete.setText("Toggle Active")

    def _new_agency(self) -> None:
        dialog = EMSAgencyDialog(self.repository, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.result_data()
            self._refresh_table()
            if result:
                self._reselect_ids([result.agency_id])

    def _edit_selected(self) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            return
        data = self.repository.get(ids[0])
        if not data:
            QMessageBox.warning(self, "Missing", "Unable to load the selected agency.")
            return
        dialog = EMSAgencyDialog(self.repository, parent=self, agency=data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_table()
            self._reselect_ids(ids)

    def _toggle_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        rows = [self.repository.get(i) for i in ids]
        if any(row is None for row in rows):
            QMessageBox.warning(self, "Selection", "One or more selected rows could not be loaded.")
            return
        active_count = sum(1 for row in rows if row and row.get("is_active"))
        if active_count and active_count != len(rows):
            QMessageBox.warning(self, "Mixed selection", "Select only active or inactive agencies to toggle.")
            return
        if active_count:
            message = f"Deactivate {active_count} agencies?"
            if QMessageBox.question(self, "Confirm", message) != QMessageBox.StandardButton.Yes:
                return
            for row in rows:
                self.repository.set_active(int(row["id"]), False)
        else:
            message = f"Restore {len(rows)} agencies?"
            if QMessageBox.question(self, "Confirm", message) != QMessageBox.StandardButton.Yes:
                return
            for row in rows:
                self.repository.set_active(int(row["id"]), True)
        self._refresh_table()

    def _import_selected(self, mode: str) -> None:
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "Import", "Select one or more agencies first.")
            return
        if not AppState.get_active_incident():
            QMessageBox.warning(self, "No incident", "Select an active incident before importing to ICS-206.")
            return
        summary = import_to_ics206(self.repository, ids, mode=mode)
        if not summary:
            QMessageBox.information(self, "ICS-206", "No agencies were imported.")
            return
        lines = [f"{section}: {count}" for section, count in summary.items()]
        QMessageBox.information(self, "ICS-206", "Imported agencies:\n" + "\n".join(lines))

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "ems_agencies.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow([col.title for col in self.model.columns])
                for row in self.model._rows:
                    writer.writerow([row.get(col.key, "") for col in self.model.columns])
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Export failed", str(exc))
        else:
            QMessageBox.information(self, "Export", f"Exported {len(self.model._rows)} rows to {path}.")

    def _print_placeholder(self) -> None:
        QMessageBox.information(self, "Print", "Print support coming soon.")

    def _open_context_menu(self, point: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction(self.act_edit)
        menu.addAction(self.act_delete)
        menu.addSeparator()
        add_to_206 = menu.addAction("Add to ICS-206 (append)")
        add_to_206.triggered.connect(lambda: self._import_selected("append"))
        menu.exec(self.table.viewport().mapToGlobal(point))

    def _merge_selected_group(self) -> None:
        item = self.duplicate_tree.currentItem()
        if not item:
            return
        group_item = item if item.parent() is None else item.parent()
        group = group_item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(group, DuplicateGroup):
            QMessageBox.information(self, "Merge", "Select the record you want to keep within a group.")
            return
        if item.parent() is None:
            QMessageBox.information(self, "Merge", "Select the agency to keep before merging.")
            return
        survivor_id = item.data(0, Qt.ItemDataRole.UserRole)
        if survivor_id is None:
            return
        duplicates = [cid for cid in group.candidate_ids if cid != survivor_id]
        if not duplicates:
            QMessageBox.information(self, "Merge", "Nothing to merge for this selection.")
            return
        survivor_row = self.repository.get(int(survivor_id))
        if not survivor_row:
            QMessageBox.warning(self, "Merge", "Unable to load the survivor record.")
            return
        lines = []
        for cid in duplicates:
            data = self.repository.get(cid)
            lines.append(str(data.get('name') if data else cid))
        msg = "\n".join(lines)
        prompt = f"Merge the following into {survivor_row.get('name', survivor_id)}?\n\n{msg}"
        if QMessageBox.question(self, "Confirm merge", prompt) != QMessageBox.StandardButton.Yes:
            return
        self.repository.merge(int(survivor_id), duplicates)
        self._refresh_all()

    def _format_audit_row(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        detail = entry.get("detail")
        target = ""
        details_text = ""
        if isinstance(detail, Mapping):
            target = str(detail.get("id") or detail.get("survivor") or "")
            if detail.get("data"):
                name = detail["data"].get("name") if isinstance(detail.get("data"), Mapping) else None
                details_text = f"Created {name or target}"
            elif detail.get("changes"):
                parts = []
                for key, change in detail["changes"].items():
                    old = change.get("old") if isinstance(change, Mapping) else None
                    new = change.get("new") if isinstance(change, Mapping) else None
                    parts.append(f"{key}: {old or '—'} → {new or '—'}")
                details_text = "; ".join(parts)
            elif detail.get("merged"):
                merged_list = ", ".join(map(str, detail.get("merged", [])))
                details_text = f"Merged {merged_list}" if merged_list else ""
        action = str(entry.get("action", ""))
        return {
            "ts_utc": entry.get("ts_utc", ""),
            "action": action,
            "target": target,
            "details": details_text,
            "user": entry.get("user_id", ""),
        }

    def _export_audit_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Audit CSV", "ems_agencies_audit.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow([col.title for col in self.audit_model.columns])
                for row in self.audit_model._rows:
                    writer.writerow([row.get(col.key, "") for col in self.audit_model.columns])
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Export failed", str(exc))
        else:
            QMessageBox.information(self, "Export", f"Exported {len(self.audit_model._rows)} audit rows to {path}.")

    def _column_index(self, key: str) -> int:
        for idx, column in enumerate(self.model.columns):
            if column.key == key:
                return idx
        return -1

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self._refresh_duplicates()
        elif index == 2:
            self._refresh_audit()

    def _date_to_iso(self, date: QDate, *, minimum: QDate | None = None, end_of_day: bool = False) -> str | None:
        if not date.isValid():
            return None
        if minimum and date <= minimum:
            return None
        if end_of_day:
            return f"{date.toString('yyyy-MM-dd')}T23:59:59"
        return f"{date.toString('yyyy-MM-dd')}T00:00:00"

    def closeEvent(self, event) -> None:  # noqa: D401 - Qt API
        self._save_geometry()
        super().closeEvent(event)

    def _restore_geometry(self) -> None:
        settings = QSettings()
        geometry = settings.value(f"{self.settings_group}/geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)

    def _save_geometry(self) -> None:
        settings = QSettings()
        settings.setValue(f"{self.settings_group}/geometry", self.saveGeometry())


def _map_action_filter(text: str | None) -> str | None:
    if not text:
        return None
    lookup = {
        "create": "ems_agency.create",
        "update": "ems_agency.update",
        "deactivate": "ems_agency.deactivate",
        "restore": "ems_agency.restore",
        "merge": "ems_agency.merge",
    }
    key = text.strip().lower()
    return lookup.get(key, text)


__all__ = ["EMSAgenciesWindow"]
