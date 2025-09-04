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
)
from PySide6.QtCore import Qt, QTimer
from utils.styles import team_status_colors, subscribe_theme
from utils.audit import write_audit
from datetime import datetime, timezone

# Use incident DB only (no sample fallback)
try:
    from modules.operations.data.repository import fetch_team_assignment_rows, set_team_assignment_status  # type: ignore
except Exception:
    fetch_team_assignment_rows = None  # type: ignore[assignment]
    set_team_assignment_status = None  # type: ignore[assignment]



class TeamStatusPanel(QWidget):
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
        btn_open = QPushButton("Open Detail")
        btn_new = QPushButton("New Team")
        btn_open.clicked.connect(lambda: self._on_open_detail())
        btn_new.clicked.connect(lambda: self._on_new_team())
        hb.addWidget(btn_open)
        hb.addWidget(btn_new)

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
            # On double click, open Team Detail placeholder
            self.table.itemDoubleClicked.connect(lambda item: self.view_team_detail(item.row()))
        except Exception:
            pass
        layout.addWidget(header_bar)
        layout.addWidget(self.table)

        # Set column headers: Needs Attention at far left; Last Update at far right
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Needs Attention", "Sortie #", "Team Name", "Team Leader", "Contact #",
            "Status", "Assignment", "Location", "Last Update"
        ])
        try:
            hdr = self.table.horizontalHeader()
            hdr.setSectionsMovable(True)
            hdr.setStretchLastSection(False)
        except Exception:
            pass
        # Initial load
        self.reload()
        # Start a 1s timer to refresh the Last Update column
        try:
            self._last_update_timer = QTimer(self)
            self._last_update_timer.setInterval(1000)
            self._last_update_timer.timeout.connect(self._refresh_last_update_column)
            self._last_update_timer.start()
        except Exception:
            pass
        # React to incident changes
        try:
            from utils.app_signals import app_signals
            app_signals.incidentChanged.connect(lambda *_: self.reload())
            # Listen for comms messages and external team status updates
            try:
                app_signals.messageLogged.connect(self._on_message_logged)
            except Exception:
                pass
            try:
                app_signals.teamStatusChanged.connect(self._on_team_status_changed)
            except Exception:
                pass
        except Exception:
            pass
        # Theme changes recolor rows
        try:
            subscribe_theme(self, lambda *_: self._recolor_all())
        except Exception:
            pass

    def add_team(self, team):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Set all column values
        items = [
            QTableWidgetItem(team.sortie),
            QTableWidgetItem(team.name),
            QTableWidgetItem(team.leader),
            QTableWidgetItem(team.contact),
            QTableWidgetItem(team.status),
            QTableWidgetItem(team.assignment),
            QTableWidgetItem(team.location)
        ]

        for col, item in enumerate(items):
            self.table.setItem(row, col, item)

        self.set_row_color_by_status(row, team.status)  # <- calls class-level method below

    def _format_elapsed(self, iso_ts: str | None) -> str:
        if not iso_ts:
            return ""
        try:
            # Accept naive UTC ISO or with tz
            try:
                dt = datetime.fromisoformat(str(iso_ts))
            except Exception:
                return str(iso_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - dt
            seconds = int(max(delta.total_seconds(), 0))
            # Format as HH:MM:SS (elapsed). Cap at 99:59:59 for very long durations.
            hours = min(seconds // 3600, 99)
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        except Exception:
            return ""

    def _add_team_row(self, data: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        status_key = str(data.get("status", ""))
        status_display = status_key.title() if status_key else ""
        needs = "Yes" if bool(data.get("needs_attention", False)) else "No"
        last_up = self._format_elapsed(data.get("last_updated"))
        vals = [
            needs,
            str(data.get("sortie", "")),
            str(data.get("name", "")),
            str(data.get("leader", "")),
            str(data.get("contact", "")),
            status_display,
            str(data.get("assignment", "")),
            str(data.get("location", "")),
            last_up,
        ]
        for col, text in enumerate(vals):
            item = QTableWidgetItem(text)
            if col == 0:
                # store ids individually so one missing value doesn't block others
                v = data.get("tt_id")
                if v is not None:
                    try:
                        item.setData(Qt.UserRole, int(v))
                    except Exception:
                        pass
                v = data.get("task_id")
                if v is not None:
                    try:
                        item.setData(Qt.UserRole + 1, int(v))
                    except Exception:
                        pass
                v = data.get("team_id")
                if v is not None:
                    try:
                        item.setData(Qt.UserRole + 2, int(v))
                    except Exception:
                        pass
            # For the Last Update column (index 8), store the ISO timestamp in item data
            if col == 8:
                try:
                    item.setData(Qt.UserRole, str(data.get("last_updated") or ""))
                except Exception:
                    pass
            self.table.setItem(row, col, item)
        # color by key to match palette
        self.set_row_color_by_status(row, status_key)

    def _refresh_last_update_column(self) -> None:
        try:
            col = 8  # Last Update is rightmost
            rows = self.table.rowCount()
            for r in range(rows):
                item = self.table.item(r, col)
                if not item:
                    continue
                iso_ts = item.data(Qt.UserRole)
                text = self._format_elapsed(iso_ts)
                if text != item.text():
                    item.setText(text)
        except Exception:
            pass

    def _on_message_logged(self, sender: str, recipient: str) -> None:
        """Reset Last Update baseline for rows matching sender or recipient label.

        Matches against the displayed team label in columns 1 (Sortie #) and 2 (Team Name),
        case-insensitive.
        """
        try:
            if sender is None and recipient is None:
                return
            labels = {str(sender or "").strip().lower(), str(recipient or "").strip().lower()}
            if not any(labels):
                return
            rows = self.table.rowCount()
            for r in range(rows):
                name_item = self.table.item(r, 2)
                sortie_item = self.table.item(r, 1)
                name = (name_item.text().strip().lower() if name_item else "")
                sortie = (sortie_item.text().strip().lower() if sortie_item else "")
                if name in labels or sortie in labels:
                    self._reset_last_update_row(r)
        except Exception:
            pass

    def _on_team_status_changed(self, team_id: int) -> None:
        """Reset Last Update baseline for the row with the given team_id."""
        try:
            rows = self.table.rowCount()
            for r in range(rows):
                # team_id is stored on first column (Needs Attention) item, UserRole+2
                item0 = self.table.item(r, 0)
                val = None
                if item0 is not None:
                    try:
                        val = int(item0.data(Qt.UserRole + 2))
                    except Exception:
                        val = None
                if val is not None and int(val) == int(team_id):
                    self._reset_last_update_row(r)
                    break
        except Exception:
            pass

    def set_row_color_by_status(self, row, status):  # ✅ Now correctly placed
        style = team_status_colors().get(status.lower())
        if not style:
            return

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(style["bg"])
                item.setForeground(style["fg"])

    def _recolor_all(self) -> None:
        try:
            status_col = 5
            rows = self.table.rowCount()
            for r in range(rows):
                item = self.table.item(r, status_col)
                status = (item.text() if item else "").strip().lower()
                self.set_row_color_by_status(r, status)
        except Exception:
            pass

    def show_context_menu(self, position):
        row = self.table.indexAt(position).row()
        if row < 0:
            return

        menu = QMenu(self)

        # Top-level actions
        menu.addAction("View Team Detail", lambda: self.view_team_detail(row))
        menu.addAction("View Task Detail", lambda: self.view_task_detail(row))

        # Add separator
        menu.addSeparator()

        # Flat list of status options
        for status in team_status_colors():
            menu.addAction(status.title(), lambda s=status: self.change_status(row, s))

        # Timer utilities
        menu.addSeparator()
        menu.addAction("Reset Timer", lambda: self._reset_last_update_row(row))

        # Show the menu
        menu.exec(self.table.viewport().mapToGlobal(position))

    def view_team_detail(self, row):
        try:
            item = self.table.item(row, 0)
            team_id = int(item.data(Qt.UserRole + 2)) if item and item.data(Qt.UserRole + 2) is not None else None
            from modules.operations.teams.windows import open_team_detail_window
            open_team_detail_window(team_id)
        except Exception as e:
            print(f"Failed to open Team Detail Window: {e}")

    def view_task_detail(self, row):
        try:
            # Use stored linked task id from first column
            item = self.table.item(row, 0)
            task_id = int(item.data(Qt.UserRole + 1)) if item and item.data(Qt.UserRole + 1) is not None else None
            if task_id is None:
                raise RuntimeError("No linked task id for this team assignment")
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(task_id)
        except Exception as e:
            print(f"Failed to open Task Detail Window: {e}")

    def change_status(self, row, new_status):
        try:
            # Persist to DB using team_id; also stamps audit if currently assigned
            item = self.table.item(row, 0)
            team_id = int(item.data(Qt.UserRole + 2)) if item and item.data(Qt.UserRole + 2) is not None else None
            if not team_id:
                raise RuntimeError("No team id associated with row")
            item_status = self.table.item(row, 5)
            old_status = (item_status.text() if item_status else "").strip().lower()
            try:
                from modules.operations.data.repository import set_team_status  # local import to avoid cycles
            except Exception:
                set_team_status = None  # type: ignore[assignment]
            if not set_team_status:
                raise RuntimeError("DB repository not available")
            set_team_status(team_id, str(new_status))
            # Update UI
            display = str(new_status).title()
            # Status column index is 5 after adding Needs Attention at 0
            self.table.item(row, 5).setText(display)
            self.set_row_color_by_status(row, str(new_status))
            write_audit("status.change", {"panel": "team", "id": team_id, "old": old_status, "new": str(new_status)})
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView, QMessageBox
            QMessageBox.critical(self, "Update Failed", f"Unable to update team status in DB:\n{e}")
        else:
            # Any status change resets the Last Update timer baseline
            self._reset_last_update_row(row)

    def _reset_last_update_row(self, row: int) -> None:
        """Reset the Last Update timer baseline for a given row to now."""
        try:
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            item_last = self.table.item(row, 8)
            if item_last:
                item_last.setData(Qt.UserRole, now_iso)
                item_last.setText(self._format_elapsed(now_iso))
        except Exception:
            pass

    def _on_open_detail(self) -> None:
        row = self.table.currentRow()
        if row < 0 and self.table.selectedIndexes():
            row = self.table.selectedIndexes()[0].row()
        if row < 0:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView, QMessageBox
            QMessageBox.information(self, "Open Detail", "Select a team row first.")
            return
        self.view_team_detail(row)

    def _on_new_team(self) -> None:
        try:
            from modules.operations.taskings.repository import create_team
            new_id = create_team(None)
            # Reload and open team detail placeholder
            self.reload()
            from modules.operations.teams.windows import open_team_detail_window
            open_team_detail_window(new_id)
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView, QMessageBox
            QMessageBox.critical(self, "New Team", f"Failed to create new team:\n{e}")

    def reload(self) -> None:
        # Clear and load fresh data from incident DB
        try:
            self.table.setRowCount(0)
            if not fetch_team_assignment_rows:
                raise RuntimeError("DB repository not available")
            rows = fetch_team_assignment_rows()
            for data in rows:
                self._add_team_row(data)
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView, QMessageBox
            QMessageBox.critical(self, "Team Board Error", f"Failed to load team assignments from incident DB:\n{e}")



