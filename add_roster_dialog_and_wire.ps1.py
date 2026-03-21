# -*- coding: utf-8 -*-
import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
# 1) Ensure dialog class exists
if 'class AddTeamMemberDialog(' not in s:
    # Find end of PySide6.QtWidgets import block to insert after
    m=re.search(r"from PySide6\.QtWidgets import \([\s\S]*?\)\n", s)
    ins = m.end() if m else 0
    dialog='''
class AddTeamMemberDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Personnel to Team")
        self.resize(640, 520)
        self.selected_person_id: str | None = None
        layout = QVBoxLayout(self)
        # Search
        row = QHBoxLayout(); layout.addLayout(row)
        row.addWidget(QLabel("Search:"))
        self._txt = QLineEdit(self)
        self._txt.setPlaceholderText("Filter by name, callsign, phone")
        row.addWidget(self._txt, 1)
        # Table
        self._tbl = QTableWidget(self)
        self._tbl.setColumnCount(4)
        self._tbl.setHorizontalHeaderLabels(["Name","Role","Team","Phone"])
        try:
            self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
            self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
            self._tbl.verticalHeader().setVisible(False)
            self._tbl.horizontalHeader().setStretchLastSection(True)
        except Exception:
            pass
        layout.addWidget(self._tbl, 1)
        # Footer
        bar = QHBoxLayout(); layout.addLayout(bar)
        self._btn_checkin = QPushButton("Check In New Person...", self)
        bar.addWidget(self._btn_checkin); bar.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        layout.addWidget(btns)
        # Wire
        self._txt.textChanged.connect(self._reload)
        self._btn_checkin.clicked.connect(self._open_checkin)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        # Initial
        self._reload()

    def _open_checkin(self) -> None:
        try:
            from modules.logistics.checkin.widgets.checkin_window import CheckInWindow
            w = CheckInWindow(self)
            w.setWindowModality(Qt.ApplicationModal)
            w.show()
        except Exception:
            try:
                QMessageBox.information(self, "Check-In", "Open Logistics -> Check-In to add people.")
            except Exception:
                pass

    def _fetch(self, query: str) -> list:
        try:
            from modules.logistics.checkin import repository as ci_repo
            from modules.logistics.checkin.models import RosterFilters
            f = RosterFilters(q=(query.strip() or None))
            return ci_repo.fetch_roster(f)
        except Exception:
            return []

    def _reload(self) -> None:
        q = self._txt.text() or ""
        rows = self._fetch(q)
        self._tbl.setRowCount(len(rows))
        for r, item in enumerate(rows):
            name = getattr(item, 'name', '')
            role = getattr(item, 'role', '')
            team = getattr(item, 'team', '') or 'Unassigned'
            phone = getattr(item, 'phone', '')
            pid = getattr(item, 'person_id', '')
            vals = [name, role or '', team, phone or '']
            for c, val in enumerate(vals):
                it = QTableWidgetItem(str(val) if val is not None else '')
                if c == 0:
                    it.setData(Qt.UserRole, str(pid))
                self._tbl.setItem(r, c, it)

    def _selected_id(self) -> str | None:
        try:
            sels = self._tbl.selectionModel().selectedRows()
        except Exception:
            return None
        if not sels:
            return None
        idx = sels[0].row()
        it = self._tbl.item(idx, 0)
        return None if it is None else it.data(Qt.UserRole)

    def _accept(self) -> None:
        pid = self._selected_id()
        if not pid:
            try:
                QMessageBox.information(self, "Select", "Please select a person from the list.")
            except Exception:
                pass
            return
        self.selected_person_id = str(pid)
        self.accept()

'''
    s = s[:ins] + dialog + s[ins:]
# 2) Replace _handle_add_member body to open the dialog
s = re.sub(r"\n\s*def _handle_add_member\(self\) -> None:[\s\S]*?\n\s*def _handle_member_detail\(self\) -> None:",
           "\n    def _handle_add_member(self) -> None:\n        try:\n            dlg = AddTeamMemberDialog(self)\n            from PySide6.QtWidgets import QDialog\n            if dlg.exec() == QDialog.Accepted and getattr(dlg, 'selected_person_id', None):\n                pid = dlg.selected_person_id\n                handler = getattr(self._bridge, 'addMember', None)\n                if callable(handler) and pid not in (None, ''):\n                    handler(int(pid))\n        except Exception as e:\n            try:\n                QMessageBox.warning(self, 'Team Detail', f'Could not add member: {e}')\n            except Exception:\n                pass\n\n    def _handle_member_detail(self) -> None:\n", s, flags=re.S)
io.open(p,'w',encoding='utf-8',newline='').write(s)
print('DIALOG_ADDED_AND_HANDLER_WIRED')
