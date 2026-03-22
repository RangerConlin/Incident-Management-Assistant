import io,re
s=io.open(r"modules/operations/teams/panels/team_detail_window.py","r",encoding="utf-8").read()
# Insert AddVehicleDialog and AddEquipmentDialog after AddTeamMemberDialog if not present
insert_point = s.find('class AddTeamMemberDialog(')
if insert_point!=-1 and 'class AddVehicleDialog(' not in s:
    dialogs='''
class AddVehicleDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Vehicle to Team")
        self.resize(640, 520)
        self.selected_id: str | None = None
        layout = QVBoxLayout(self)
        row = QHBoxLayout(); layout.addLayout(row)
        row.addWidget(QLabel("Search:"))
        self._txt = QLineEdit(self); row.addWidget(self._txt, 1)
        self._tbl = QTableWidget(self); self._tbl.setColumnCount(5)
        self._tbl.setHorizontalHeaderLabels(["ID","Name","Callsign","Type","Team"])
        try:
            self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
            self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
            self._tbl.verticalHeader().setVisible(False)
            self._tbl.horizontalHeader().setStretchLastSection(True)
        except Exception: pass
        layout.addWidget(self._tbl, 1)
        bar = QHBoxLayout(); layout.addLayout(bar)
        self._btn_checkin = QPushButton("Check In From Master...", self)
        bar.addWidget(self._btn_checkin); bar.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        layout.addWidget(btns)
        self._txt.textChanged.connect(self._reload)
        btns.accepted.connect(self._accept); btns.rejected.connect(self.reject)
        self._btn_checkin.clicked.connect(self._open_checkin)
        self._win = None
        self._reload()
    def _open_checkin(self) -> None:
        try:
            from modules.logistics.checkin.widgets.checkin_window import CheckInWindow
            if self._win is None:
                self._win = CheckInWindow(self)
                try: self._win.destroyed.connect(lambda *_: (setattr(self,'_win',None), self._reload()))
                except Exception: pass
            self._win.show()
        except Exception:
            try: QMessageBox.information(self, "Check-In", "Open Logistics -> Check-In to add vehicles.")
            except Exception: pass
    def _rows(self) -> list:
        try:
            from models.queries import list_incident_vehicles
            return list_incident_vehicles()
        except Exception: return []
    def _reload(self) -> None:
        q = (self._txt.text() or '').lower().strip()
        data = self._rows()
        rows = []
        for r in data:
            name = str(r.get('name') or '')
            callsign = str(r.get('callsign') or '')
            typ = str(r.get('type') or '')
            team = str(r.get('team_name') or r.get('team_id') or '').strip() or 'Unassigned'
            rid = str(r.get('id'))
            hay = ' '.join([rid,name,callsign,typ,team]).lower()
            if not q or q in hay:
                rows.append((rid,name,callsign,typ,team))
        self._tbl.setRowCount(len(rows))
        for i,(rid,name,callsign,typ,team) in enumerate(rows):
            for c,val in enumerate([rid,name,callsign,typ,team]):
                it = QTableWidgetItem(val)
                if c==0: it.setData(Qt.UserRole, rid)
                self._tbl.setItem(i,c,it)
    def _accept(self) -> None:
        try:
            sel = self._tbl.selectionModel().selectedRows()
            if not sel: return
            idx = sel[0].row(); it = self._tbl.item(idx,0)
            self.selected_id = None if it is None else it.data(Qt.UserRole)
            if not self.selected_id: return
            self.accept()
        except Exception: pass

class AddEquipmentDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Equipment to Team")
        self.resize(640, 520)
        self.selected_id: str | None = None
        layout = QVBoxLayout(self)
        row = QHBoxLayout(); layout.addLayout(row)
        row.addWidget(QLabel("Search:"))
        self._txt = QLineEdit(self); row.addWidget(self._txt, 1)
        self._tbl = QTableWidget(self); self._tbl.setColumnCount(4)
        self._tbl.setHorizontalHeaderLabels(["ID","Name","Type","Team"])
        try:
            self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
            self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
            self._tbl.verticalHeader().setVisible(False)
            self._tbl.horizontalHeader().setStretchLastSection(True)
        except Exception: pass
        layout.addWidget(self._tbl, 1)
        bar = QHBoxLayout(); layout.addLayout(bar)
        self._btn_checkin = QPushButton("Check In From Master...", self)
        bar.addWidget(self._btn_checkin); bar.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        layout.addWidget(btns)
        self._txt.textChanged.connect(self._reload)
        btns.accepted.connect(self._accept); btns.rejected.connect(self.reject)
        self._btn_checkin.clicked.connect(self._open_checkin)
        self._win = None
        self._reload()
    def _open_checkin(self) -> None:
        try:
            from modules.logistics.checkin.widgets.checkin_window import CheckInWindow
            if self._win is None:
                self._win = CheckInWindow(self)
                try: self._win.destroyed.connect(lambda *_: (setattr(self,'_win',None), self._reload()))
                except Exception: pass
            self._win.show()
        except Exception:
            try: QMessageBox.information(self, "Check-In", "Open Logistics -> Check-In to add equipment.")
            except Exception: pass
    def _rows(self) -> list:
        try:
            from models.queries import list_incident_equipment
            return list_incident_equipment()
        except Exception: return []
    def _reload(self) -> None:
        q = (self._txt.text() or '').lower().strip()
        data = self._rows()
        rows = []
        for r in data:
            name = str(r.get('name') or '')
            typ = str(r.get('type') or '')
            team = str(r.get('team_name') or r.get('team_id') or '').strip() or 'Unassigned'
            rid = str(r.get('id'))
            hay = ' '.join([rid,name,typ,team]).lower()
            if not q or q in hay:
                rows.append((rid,name,typ,team))
        self._tbl.setRowCount(len(rows))
        for i,(rid,name,typ,team) in enumerate(rows):
            for c,val in enumerate([rid,name,typ,team]):
                it = QTableWidgetItem(val)
                if c==0: it.setData(Qt.UserRole, rid)
                self._tbl.setItem(i,c,it)
    def _accept(self) -> None:
        try:
            sel = self._tbl.selectionModel().selectedRows()
            if not sel: return
            idx = sel[0].row(); it = self._tbl.item(idx,0)
            self.selected_id = None if it is None else it.data(Qt.UserRole)
            if not self.selected_id: return
            self.accept()
        except Exception: pass
'''
    s = s[:insert_point] + dialogs + s[insert_point:]
# Wire handlers to open dialogs
s = re.sub(r"def _handle_add_asset\(self\) -> None:[\s\S]*?def _handle_add_equipment\(self\) -> None:",
           "def _handle_add_asset(self) -> None:\n        try:\n            dlg = AddVehicleDialog(self)\n            from PySide6.QtWidgets import QDialog\n            if dlg.exec() == QDialog.Accepted and getattr(dlg,'selected_id',None):\n                vid = dlg.selected_id\n                handler = getattr(self._bridge, 'addVehicle', None)\n                if callable(handler): handler(int(vid))\n        except Exception:\n            handler = getattr(self._bridge, 'addAsset', None)\n            if callable(handler): handler()\n\n    def _handle_add_equipment(self) -> None:\n        try:\n            dlg = AddEquipmentDialog(self)\n            from PySide6.QtWidgets import QDialog\n            if dlg.exec() == QDialog.Accepted and getattr(dlg,'selected_id',None):\n                eid = dlg.selected_id\n                handler = getattr(self._bridge, 'addEquipment', None)\n                if callable(handler): handler(int(eid))\n        except Exception:\n            handler = getattr(self._bridge, 'addEquipment', None)\n            if callable(handler): handler()\n", s, flags=re.S)
# Update addVehicle/addEquipment to append to team JSON lists and persist
s = re.sub(r"@Slot\('QVariant'\)\s*def addVehicle\([\s\S]*?@Slot\('QVariant'\)\s*def removeVehicle",
           "@Slot('QVariant')\n    def addVehicle(self, vehicle_id: Any) -> None:\n        try:\n            if not self._team.team_id:\n                raise RuntimeError('No team id')\n            if vehicle_id is not None and str(vehicle_id) != '':\n                vid = int(vehicle_id)\n                lst = list(getattr(self._team,'vehicles',[]) or [])\n                if str(vid) not in [str(x) for x in lst]:\n                    lst.append(str(vid)); self._team.vehicles = lst\n                    try: team_repo.save_team(self._team)\n                    except Exception: pass\n                try:\n                    set_vehicle_team(vid, int(self._team.team_id))\n                except Exception: pass\n                app_signals.teamAssetsChanged.emit(int(self._team.team_id))\n        except Exception as e:\n            self.error.emit(f'Failed to add vehicle: {e}')\n\n    @Slot('QVariant')\n    def removeVehicle", s, flags=re.S)

s = re.sub(r"@Slot\('QVariant'\)\s*def addEquipment\([\s\S]*?@Slot\('QVariant'\)\s*def removeEquipment",
           "@Slot('QVariant')\n    def addEquipment(self, eq_id: Any) -> None:\n        try:\n            if not self._team.team_id:\n                raise RuntimeError('No team id')\n            if eq_id is not None and str(eq_id) != '':\n                eid = int(eq_id)\n                lst = list(getattr(self._team,'equipment',[]) or [])\n                if str(eid) not in [str(x) for x in lst]:\n                    lst.append(str(eid)); self._team.equipment = lst\n                    try: team_repo.save_team(self._team)\n                    except Exception: pass\n                try:\n                    set_equipment_team(eid, int(self._team.team_id))\n                except Exception: pass\n                app_signals.teamAssetsChanged.emit(int(self._team.team_id))\n        except Exception as e:\n            self.error.emit(f'Failed to add equipment: {e}')\n\n    @Slot('QVariant')\n    def removeEquipment", s, flags=re.S)

io.open(r"modules/operations/teams/panels/team_detail_window.py","w",encoding="utf-8",newline="").write(s)
print('DIALOGS_WIRED_VEH_EQUIP')
