from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QMenu,
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QHeaderView,
    QMessageBox,
    QToolButton,
    QDialog,
)
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtCore import Qt
from utils.styles import task_status_colors, subscribe_theme
from utils.audit import write_audit
from utils.app_signals import app_signals

# Require incident DB repository (no sample fallback)
try:
    from modules.operations.data.repository import fetch_task_rows, set_task_status  # type: ignore
except Exception:
    fetch_task_rows = None  # type: ignore[assignment]

class TaskStatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        # Header actions
        header_bar = QWidget()
        hb = QHBoxLayout(header_bar)
        try:
            hb.setContentsMargins(0, 0, 0, 0)
            hb.setSpacing(6)
        except Exception:
            pass
        btn_filters = QToolButton(header_bar)
        try:
            btn_filters.setText("\u2699")  # gear
            btn_filters.setToolTip("Settings")
            btn_filters.setFixedSize(28, 28)
            btn_filters.setPopupMode(QToolButton.InstantPopup)
        except Exception:
            pass
        self._text_size: str = "medium"
        self._load_text_size()
        self._settings_btn = btn_filters
        hb.addWidget(btn_filters)

        btn_open = QPushButton("Open Detail")
        btn_open.setFixedSize(120, 28)
        btn_new = QPushButton("New Task")
        btn_new.setFixedSize(120, 28)
        btn_open.clicked.connect(self._on_open_detail)
        btn_new.clicked.connect(self._on_new_task)
        hb.addWidget(btn_open)
        hb.addWidget(btn_new)
        hb.addStretch(1)

        self.table = QTableWidget()
        # Make table read-only; edits go through context menus / detail windows
        try:
            self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        except Exception:
            pass
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        try:
            self.table.itemDoubleClicked.connect(lambda item: self.view_task_detail(item.row()))
        except Exception:
            pass
        layout.addWidget(header_bar)
        layout.addWidget(self.table)

        # Set column headers
        self.table.setColumnCount(6)
        headers = [
            "Task #", "Task Name", "Assigned Team(s)", "Status", "Priority", "Location"
        ]
        self.table.setHorizontalHeaderLabels(headers)
        # Column registry for visibility settings
        self._columns: list[tuple[int, str, str]] = [
            (0, "number", headers[0]),
            (1, "name", headers[1]),
            (2, "assigned_teams", headers[2]),
            (3, "status", headers[3]),
            (4, "priority", headers[4]),
            (5, "location", headers[5]),
        ]
        try:
            hdr = self.table.horizontalHeader()
            hdr.setSectionsMovable(True)
            hdr.setStretchLastSection(False)
        except Exception:
            pass
        # Apply any saved column visibility
        self._load_column_visibility()
        # Build settings menu now that columns exist
        try:
            self._build_settings_menu()
        except Exception:
            pass
        # Filter state
        self._filters: list[dict] = []
        self._match_all: bool = True
        self._load_filters()
        # Initial load
        self.reload()
        # React to incident changes
        try:
            app_signals.incidentChanged.connect(lambda *_: self.reload())
        except Exception:
            pass
        try:
            app_signals.taskHeaderChanged.connect(self._on_task_header_changed)
        except Exception:
            pass
        try:
            subscribe_theme(self, lambda *_: self._recolor_all())
        except Exception:
            pass

    def add_task(self, task):
        row = self.table.rowCount()
        self.table.insertRow(row)

        items = [
                QTableWidgetItem(task.number),
                QTableWidgetItem(task.name),
                QTableWidgetItem(", ".join(task.assigned_teams)),
                QTableWidgetItem(task.status),
                QTableWidgetItem(task.priority),
                QTableWidgetItem(task.location)
        ]

        for col, item in enumerate(items):
            self.table.setItem(row, col, item)

        self.set_row_color_by_status(row, task.status)

    def _add_task_row(self, data: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        teams = data.get("assigned_teams") or []
        teams_str = ", ".join(map(str, teams)) if isinstance(teams, (list, tuple)) else str(teams)
        status_key = str(data.get("status", ""))
        status_display = status_key.title() if status_key else ""
        vals = [
            str(data.get("number", "")),
            str(data.get("name", "")),
            teams_str,
            status_display,
            str(data.get("priority", "")),
            str(data.get("location", "")),
        ]
        for col, text in enumerate(vals):
            item = QTableWidgetItem(text)
            if col == 0:
                try:
                    item.setData(Qt.UserRole, int(data.get("id")))
                except Exception:
                    pass
            self.table.setItem(row, col, item)
        # Use the original key for color mapping (row-wide coloring)
        self.set_row_color_by_status(row, status_key)

    def reload(self) -> None:
        # Clear and load fresh data from incident DB
        try:
            self.table.setRowCount(0)
            if not fetch_task_rows:
                raise RuntimeError("DB repository not available")
            rows = fetch_task_rows()
            rows = self._apply_filters(rows)
            for data in rows:
                self._add_task_row(data)
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
            QMessageBox.critical(self, "Task Board Error", f"Failed to load tasks from incident DB:\n{e}")

    def set_row_color_by_status(self, row, status):
        style = task_status_colors().get(status.lower())
        if not style:
            return

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(style["bg"])
                item.setForeground(style["fg"])

    def _recolor_all(self) -> None:
        try:
            status_col = 3
            rows = self.table.rowCount()
            for r in range(rows):
                item = self.table.item(r, status_col)
                status = (item.text() if item else "").strip().lower()
                self.set_row_color_by_status(r, status)
        except Exception:
            pass

    def _on_task_header_changed(self, task_id: int, changed: dict) -> None:
        try:
            self.reload()
        except Exception:
            pass

    def show_context_menu(self, position):
        row = self.table.indexAt(position).row()
        if row < 0:
            return

        menu = QMenu(self)

        # Top-level actions
        menu.addAction("View Task Detail (Widget)", lambda: self.view_task_detail(row))

        # Add separator
        menu.addSeparator()

        # Flat list of status options
        for status in task_status_colors():
            menu.addAction(status.title(), lambda s=status: self.change_status(row, s))

        # Show the menu
        menu.exec(self.table.viewport().mapToGlobal(position))

    def view_team_detail(self, row):
        print(f"Viewing team detail for row {row}")

    def view_task_detail(self, row):
        try:
            # Prefer stored DB task id on first column
            item = self.table.item(row, 0)
            task_id = int(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) is not None else None
            if task_id is None:
                raise RuntimeError("No task id associated with row")
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(task_id)
        except Exception as e:
            print(f"Failed to open Task Detail Window: {e}")

    # QML variant removed

    def change_status(self, row, new_status):
        try:
            item_id = self.table.item(row, 0)
            task_id = int(item_id.data(Qt.UserRole)) if item_id and item_id.data(Qt.UserRole) is not None else None
            if not task_id:
                raise RuntimeError("No task id associated with row")
            if not set_task_status:
                raise RuntimeError("DB repository not available")
            item_status = self.table.item(row, 3)
            old_status = (item_status.text() if item_status else "").strip().lower()
            set_task_status(task_id, str(new_status))
            # Update UI
            display = str(new_status).title()
            self.table.item(row, 3).setText(display)
            self.set_row_color_by_status(row, str(new_status))
            write_audit("status.change", {"panel": "task", "id": task_id, "old": old_status, "new": str(new_status)})
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
            QMessageBox.critical(self, "Update Failed", f"Unable to update task status in DB:\n{e}")

    def _on_open_detail(self) -> None:
        row = self.table.currentRow()
        if row < 0 and self.table.selectedIndexes():
            row = self.table.selectedIndexes()[0].row()
        if row < 0:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
            QMessageBox.information(self, "Open Detail", "Select a task row first.")
            return
        self.view_task_detail(row)

    def _on_new_task(self) -> None:
        try:
            from modules.operations.taskings.repository import create_task
            new_id = create_task(title="<New Task>")
            # Reload table and open detail for the new task
            self.reload()
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(new_id)
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
            QMessageBox.critical(self, "New Task", f"Failed to create new task:\n{e}")

    # --------------------------- Filters / Presets --------------------------- #
    def _open_filters_dialog(self) -> None:
        try:
            from modules.common.widgets.custom_filter_dialog import CustomFilterDialog, FieldSpec
            fields = [
                FieldSpec(key="number", label="Task #", type="number"),
                FieldSpec(key="name", label="Task Name", type="string"),
                FieldSpec(key="assigned_teams", label="Assigned Teams", type="string"),
                FieldSpec(key="status", label="Status", type="string"),
                FieldSpec(key="priority", label="Priority", type="string"),
                FieldSpec(key="location", label="Location", type="string"),
            ]
            seed = {
                "High Priority": {"rules": [{"field": "priority", "op": "=", "value": "High"}], "matchAll": True},
                "In Progress": {"rules": [{"field": "status", "op": "=", "value": "In Progress"}], "matchAll": True},
            }
            dlg = CustomFilterDialog(
                fields,
                rules=self._filters,
                match_all=self._match_all,
                context_key="statusboard.task",
                seed_presets=seed,
                parent=self,
            )
            if dlg.exec() == QDialog.Accepted:
                self._filters = dlg.rules()
                self._match_all = dlg.match_all()
                self._persist_filters()
                self.reload()
        except Exception as e:
            QMessageBox.critical(self, "Filters", f"Failed to open filters dialog:\n{e}")

    def _apply_filters(self, rows: list[dict]) -> list[dict]:
        if not self._filters:
            return rows

        def value_for(row: dict, key: str):
            val = row.get(key)
            if key == "assigned_teams" and isinstance(val, (list, tuple)):
                return ", ".join(map(str, val))
            return val

        def match(rule: dict, row: dict) -> bool:
            key = rule.get("field")
            op = str(rule.get("op", "")).lower()
            needle = str(rule.get("value", ""))
            hay = value_for(row, key)
            if hay is None:
                hay_s = ""
            else:
                hay_s = str(hay)
            # Try numeric comparison
            if op in {"=", "!=", ">", ">=", "<", "<="}:
                try:
                    a = float(hay_s)
                    b = float(needle)
                    if op == "=":
                        return a == b
                    if op == "!=":
                        return a != b
                    if op == ">":
                        return a > b
                    if op == ">=":
                        return a >= b
                    if op == "<":
                        return a < b
                    if op == "<=":
                        return a <= b
                except Exception:
                    pass
            # Fallback to case-insensitive string comparisons
            a = hay_s.lower()
            b = needle.lower()
            if op in {"=", "equals"}:
                return a == b
            if op in {"!=", "not equals"}:
                return a != b
            if op in {"contains"}:
                return b in a
            if op in {"not contains"}:
                return b not in a
            if op in {"starts with"}:
                return a.startswith(b)
            if op in {"ends with"}:
                return a.endswith(b)
            return True

        out = []
        for row in rows:
            results = [match(rule, row) for rule in self._filters]
            ok = all(results) if self._match_all else any(results)
            if ok:
                out.append(row)
        return out

    def _persist_filters(self) -> None:
        try:
            from utils.settingsmanager import SettingsManager
            s = SettingsManager()
            s.set("statusboard.task.filters", {"rules": self._filters, "matchAll": self._match_all})
        except Exception:
            pass

    # ------------------------------ Settings menu --------------------------- #
    def _build_settings_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Filters...", self._open_filters_dialog)
        menu.addSeparator()
        # Columns submenu
        cols_menu = QMenu("Columns", menu)
        self._col_actions = {}
        for idx, key, label in self._columns:
            act = cols_menu.addAction(label, lambda i=idx: self._toggle_column(i))
            act.setCheckable(True)
            try:
                act.setChecked(not self.table.isColumnHidden(idx))
            except Exception:
                act.setChecked(True)
            self._col_actions[idx] = act
        menu.addMenu(cols_menu)
        # Text size submenu
        size_menu = QMenu("Text Size", menu)
        self._size_actions = {}
        for label in ("small", "medium", "large"):
            act = size_menu.addAction(label.title(), lambda l=label: self._set_text_size(l))
            act.setCheckable(True)
            self._size_actions[label] = act
        menu.addMenu(size_menu)
        self._settings_btn.setMenu(menu)
        self._update_text_size_checks()
        self._update_column_checks()

    def _update_text_size_checks(self) -> None:
        try:
            for k, a in getattr(self, "_size_actions", {}).items():
                a.setChecked(k == self._text_size)
        except Exception:
            pass

    def _update_column_checks(self) -> None:
        try:
            for idx, act in getattr(self, "_col_actions", {}).items():
                act.setChecked(not self.table.isColumnHidden(idx))
        except Exception:
            pass

    def _set_text_size(self, label: str) -> None:
        self._text_size = label if label in ("small", "medium", "large") else "medium"
        self._persist_text_size()
        self._apply_text_size()
        self._update_text_size_checks()

    def _persist_text_size(self) -> None:
        try:
            from utils.settingsmanager import SettingsManager
            SettingsManager().set("statusboard.task.textSize", self._text_size)
        except Exception:
            pass

    def _load_text_size(self) -> None:
        try:
            from utils.settingsmanager import SettingsManager
            self._text_size = SettingsManager().get("statusboard.task.textSize", "medium") or "medium"
            self._apply_text_size()
        except Exception:
            pass

    def _apply_text_size(self) -> None:
        size_map = {"small": 10, "medium": 12, "large": 14}
        pt = size_map.get(self._text_size, 12)
        try:
            f = QFont(self.table.font())
            f.setPointSize(pt)
            self.table.setFont(f)
            hdrf = QFont(f)
            self.table.horizontalHeader().setFont(hdrf)
            self.table.verticalHeader().setFont(hdrf)
            # Adjust row height to font metrics
            fm = QFontMetrics(f)
            self.table.verticalHeader().setDefaultSectionSize(fm.height() + 8)
        except Exception:
            pass

    # -------------------------- Column visibility -------------------------- #
    def _toggle_column(self, index: int) -> None:
        try:
            hidden = self.table.isColumnHidden(index)
            self.table.setColumnHidden(index, not hidden)
            self._persist_column_visibility()
            self._update_column_checks()
        except Exception:
            pass

    def _persist_column_visibility(self) -> None:
        try:
            from utils.settingsmanager import SettingsManager
            hidden_keys: list[str] = []
            for idx, key, _ in self._columns:
                if self.table.isColumnHidden(idx):
                    hidden_keys.append(key)
            SettingsManager().set("statusboard.task.columns.hidden", hidden_keys)
        except Exception:
            pass

    def _load_column_visibility(self) -> None:
        try:
            from utils.settingsmanager import SettingsManager
            hidden = SettingsManager().get("statusboard.task.columns.hidden", []) or []
            key_to_index = {key: idx for idx, key, _ in self._columns}
            for key in hidden:
                if key in key_to_index:
                    self.table.setColumnHidden(key_to_index[key], True)
        except Exception:
            pass

    def _load_filters(self) -> None:
        try:
            from utils.settingsmanager import SettingsManager
            s = SettingsManager()
            filt = s.get("statusboard.task.filters", None)
            if isinstance(filt, dict):
                self._filters = list(filt.get("rules", []))
                self._match_all = bool(filt.get("matchAll", True))
        except Exception:
            pass


