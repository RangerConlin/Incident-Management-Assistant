import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from PySide6.QtCore import (
    Qt,
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    QTimer,
)
from PySide6.QtGui import QColor, QPainter, QPen, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QShortcut,
    QTableView,
    QVBoxLayout,
    QWidget,
    QMainWindow,
    QAbstractItemView,
    QFrame,
)

# --- Styling ---------------------------------------------------------------
STYLES = """
QTableView {
    alternate-background-color: palette(alternate-base);
    gridline-color: transparent;
}
QHeaderView::section {
    padding: 4px;
}
QTableView::item {
    padding: 4px 8px;
}
QTableView::item:hover {
    background-color: rgba(100,149,237,80);
}
QTableView::item:selected {
    background-color: rgba(100,149,237,160);
    color: white;
}
"""

# --- Data layer ------------------------------------------------------------
class MissionStore:
    """Provides mission rows. In real use, backed by SQLite."""

    def list_missions(self) -> List[Dict]:
        now = datetime.now()
        missions = [
            {
                "id": i,
                "name": f"Mission {i}",
                "type": t,
                "status": s,
                "description": f"Detailed description for mission {i}. " * 3,
                "created_at": now - timedelta(days=30 + i),
                "last_opened_at": (now - timedelta(days=i)) if i % 2 == 0 else None,
            }
            for i, (t, s) in enumerate(
                [
                    ("SAR", "Active"),
                    ("Training", "Standby"),
                    ("Planned Event", "Archived"),
                    ("SAR", "Active"),
                    ("Training", "Standby"),
                    ("Planned Event", "Active"),
                    ("SAR", "Archived"),
                    ("Training", "Active"),
                    ("Planned Event", "Standby"),
                    ("SAR", "Active"),
                ],
                start=1,
            )
        ]
        missions.sort(key=lambda m: m["last_opened_at"] or datetime.min, reverse=True)
        return missions

# --- Model -----------------------------------------------------------------
class MissionTableModel(QAbstractTableModel):
    headers = ["Name", "Type", "Status", "Created", "Last Opened"]

    def __init__(self, missions: List[Dict]):
        super().__init__()
        self._missions = missions

    # Required model implementations
    def rowCount(self, parent=QModelIndex()):
        return len(self._missions)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        mission = self._missions[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return mission["name"]
            if col == 1:
                return mission["type"]
            if col == 2:
                return mission["status"]
            if col == 3:
                return mission["created_at"].strftime("%Y-%m-%d")
            if col == 4:
                return (
                    mission["last_opened_at"].strftime("%Y-%m-%d")
                    if mission["last_opened_at"]
                    else "-"
                )
        if role == Qt.ToolTipRole:
            return mission["description"]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return super().headerData(section, orientation, role)

    def sort(self, column, order=Qt.AscendingOrder):
        key_funcs = {
            0: lambda m: m["name"],
            1: lambda m: m["type"],
            2: lambda m: m["status"],
            3: lambda m: m["created_at"],
            4: lambda m: m["last_opened_at"] or datetime.min,
        }
        self.layoutAboutToBeChanged.emit()
        self._missions.sort(key=key_funcs[column], reverse=order == Qt.DescendingOrder)
        self.layoutChanged.emit()

    def mission_at(self, row: int) -> Dict:
        return self._missions[row]

# --- Filtering --------------------------------------------------------------
class MissionFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def filterAcceptsRow(self, source_row, source_parent):
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True
        model = self.sourceModel()
        mission = model.mission_at(source_row)
        for key in ("name", "type", "status"):
            if pattern in mission[key].lower():
                return True
        return False

# --- Loading overlay -------------------------------------------------------
class Spinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.setFixedSize(32, 32)

    def start(self):
        self._timer.start(100)

    def stop(self):
        self._timer.stop()

    def _rotate(self):
        self.angle = (self.angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#448aff"), 3)
        painter.setPen(pen)
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.drawArc(rect, int(self.angle * 16), 120 * 16)

class LoadingOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background-color: rgba(0,0,0,128);")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.spinner = Spinner()
        layout.addWidget(self.spinner)
        label = QLabel("Loading mission...")
        label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(label)
        self.hide()

    def showEvent(self, event):
        self.setGeometry(self.parent().rect())
        self.spinner.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.spinner.stop()
        super().hideEvent(event)

# --- Main window -----------------------------------------------------------
class MissionSelectWindow(QMainWindow):
    def __init__(self, store: MissionStore):
        super().__init__()
        self.setWindowTitle("Select Mission")
        self.store = store
        self.missions = store.list_missions()
        self.resize(900, 500)
        self.last_index: Optional[QModelIndex] = None

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)

        # Left side: search + table or empty state
        left_container = QVBoxLayout()
        h.addLayout(left_container, 3)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search...")
        left_container.addWidget(self.search)

        if self.missions:
            self.model = MissionTableModel(self.missions)
            self.proxy = MissionFilterProxyModel()
            self.proxy.setSourceModel(self.model)

            self.table = QTableView()
            self.table.setModel(self.proxy)
            self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.table.setAlternatingRowColors(True)
            self.table.setShowGrid(False)
            self.table.horizontalHeader().setStretchLastSection(True)
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.table.setTextElideMode(Qt.ElideRight)
            left_container.addWidget(self.table)
            self.empty_label = None
            self.proxy.sort(4, Qt.DescendingOrder)
        else:
            self.table = None
            self.proxy = None
            self.empty_label = QLabel("No missions found")
            self.empty_label.setAlignment(Qt.AlignCenter)
            self.empty_label.setFrameShape(QFrame.StyledPanel)
            left_container.addWidget(self.empty_label)

        # Right detail panel
        detail_layout = QVBoxLayout()
        h.addLayout(detail_layout, 2)

        self.detail_name = QLabel("Select a mission…")
        self.detail_type = QLabel()
        self.detail_status = QLabel()
        self.detail_created = QLabel()
        self.detail_opened = QLabel()
        self.detail_desc = QLabel()
        self.detail_desc.setWordWrap(True)
        detail_layout.addWidget(self.detail_name)
        detail_layout.addWidget(self.detail_type)
        detail_layout.addWidget(self.detail_status)
        detail_layout.addWidget(self.detail_created)
        detail_layout.addWidget(self.detail_opened)
        detail_layout.addWidget(self.detail_desc, 1)
        detail_layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        detail_layout.addLayout(btn_layout)
        btn_layout.addStretch()
        self.load_btn = QPushButton("Load Mission")
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.cancel_btn)

        if not self.missions:
            self.load_btn.setEnabled(False)

        # Overlay
        self.overlay = LoadingOverlay(central)

    def _connect_signals(self):
        if self.table:
            self.table.doubleClicked.connect(self.load_selected)
            self.table.selectionModel().selectionChanged.connect(self._selection_changed)
            self.search.textChanged.connect(self.proxy.setFilterFixedString)
            # Enter key
            QShortcut(QKeySequence("Return"), self.table, activated=self.load_selected)
            QShortcut(QKeySequence("Enter"), self.table, activated=self.load_selected)
        QShortcut(QKeySequence("Escape"), self, activated=self.close)

        self.load_btn.clicked.connect(self.load_selected)
        self.cancel_btn.clicked.connect(self.close)

    # --- UI helpers -----------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        if self.table and self.table.model().rowCount() > 0:
            QTimer.singleShot(0, self._select_first)

    def _select_first(self):
        index = self.proxy.index(0, 0)
        self.table.setCurrentIndex(index)

    def _selection_changed(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self.load_btn.setEnabled(False)
            self.detail_name.setText("Select a mission…")
            self.detail_type.clear()
            self.detail_status.clear()
            self.detail_created.clear()
            self.detail_opened.clear()
            self.detail_desc.clear()
            return
        index = indexes[0]
        self.load_btn.setEnabled(True)
        mission = self.proxy.sourceModel().mission_at(self.proxy.mapToSource(index).row())
        self.detail_name.setText(f"Name: {mission['name']}")
        self.detail_type.setText(f"Type: {mission['type']}")
        self.detail_status.setText(f"Status: {mission['status']}")
        self.detail_created.setText(
            f"Created: {mission['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        self.detail_opened.setText(
            f"Last Opened: {mission['last_opened_at'].strftime('%Y-%m-%d %H:%M') if mission['last_opened_at'] else '-'}"
        )
        desc = mission['description']
        if len(desc) > 500:
            desc = desc[:500] + "…"
        self.detail_desc.setText(f"Description: {desc}")
        self.last_index = index

    # --- Loading flow ---------------------------------------------------
    def load_selected(self):
        if not self.table:
            return
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        index = indexes[0]
        mission = self.proxy.sourceModel().mission_at(self.proxy.mapToSource(index).row())
        self.centralWidget().setEnabled(False)
        self.overlay.show()
        QTimer.singleShot(1200, lambda: self._finish_load(mission))

    def _finish_load(self, mission: Dict):
        print({"mission_id": mission["id"], "name": mission["name"]})
        QApplication.instance().quit()

# --- Entry -----------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLES)
    store = MissionStore()
    win = MissionSelectWindow(store)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
