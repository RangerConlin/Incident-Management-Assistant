import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
# 1) Patch _handle_add_member
start_pat=r"\n\s*def _handle_add_member\(self\) -> None:\n[\s\S]*?\n\s*def _handle_member_detail\(self\) -> None:" 
new_handle='''

    def _handle_add_member(self) -> None:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QDialogButtonBox
        # Build lightweight selector dialog for checked-in personnel
        dlg = QDialog(self); dlg.setWindowTitle("Add Personnel")
        v = QVBoxLayout(dlg)
        row = QHBoxLayout(); v.addLayout(row)
        row.addWidget(QLabel("Search:"))
        txt = QLineEdit(dlg); txt.setPlaceholderText("Filter name, callsign, phone…"); row.addWidget(txt, 1)
        tbl = QTableWidget(dlg); tbl.setColumnCount(4); tbl.setHorizontalHeaderLabels(["Name","Role","Team","Phone"]); v.addWidget(tbl)
        try:
            tbl.setSelectionBehavior(QAbstractItemView.SelectRows); tbl.setSelectionMode(QAbstractItemView.SingleSelection); tbl.verticalHeader().setVisible(False)
        except Exception:
            pass
        bar = QHBoxLayout(); v.addLayout(bar)
        btn_checkin = QPushButton("Check In New Person…", dlg); bar.addWidget(btn_checkin); bar.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg); v.addWidget(btns)
        # Data helpers
        def load_rows(q: str = ""):
            try:
                from modules.logistics.checkin.repository import fetch_roster
                from modules.logistics.checkin.models import RosterFilters
                f = RosterFilters(q=(q.strip() or None))
                return fetch_roster(f)
            except Exception:
                return []
        def populate(q: str = ""):
            rows = load_rows(q)
            try: tbl.blockSignals(True)
            except Exception: pass
            tbl.setRowCount(len(rows))
            for r, item in enumerate(rows):
                name = getattr(item, 'name', '')
                role = getattr(item, 'role', '')
                team = getattr(item, 'team', '')
                phone = getattr(item, 'phone', '')
                pid = getattr(item, 'person_id', '')
                for c, val in enumerate([name, role or '', team or '', phone or '']):
                    it = QTableWidgetItem(str(val) if val is not None else '')
                    if c == 0:
                        it.setData(Qt.UserRole, str(pid))
                    tbl.setItem(r, c, it)
            try: tbl.blockSignals(False)
            except Exception: pass
        def selected_pid():
            try:
                sel = tbl.selectionModel().selectedRows()
                if not sel: return None
                idx = sel[0].row(); it = tbl.item(idx, 0)
                return None if it is None else it.data(Qt.UserRole)
            except Exception:
                return None
        # Wire
        txt.textChanged.connect(lambda t: populate(t))
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        def open_checkin():
            try:
                from modules.logistics.checkin.widgets.checkin_window import CheckInWindow
                w = CheckInWindow(self); w.setWindowModality(Qt.ApplicationModal); w.show()
            except Exception:
                try: QMessageBox.information(self, "Check-In", "Open Logistics ? Check-In to add people.")
                except Exception: pass
        btn_checkin.clicked.connect(open_checkin)
        populate("")
        if dlg.exec() == QDialog.Accepted:
            pid = selected_pid()
            if pid not in (None, ""):
                handler = getattr(self._bridge, "addMember", None)
                if callable(handler):
                    try: handler(int(pid))
                    except Exception: QMessageBox.warning(self, "Add Personnel", "Could not assign selected person to the team.")

    def _handle_member_detail(self) -> None:
'''
ns=re.sub(start_pat,new_handle,s,flags=re.S)
# 2) Remove role validation branch in addMember (keep function otherwise)
ns=re.sub(r"\n\s*if not self\._is_member_role_valid\(int\(person_id\)\):[\s\S]*?\n\s*return\n","\n",ns)
io.open(p,'w',encoding='utf-8',newline='').write(ns)
print('PATCHED')
