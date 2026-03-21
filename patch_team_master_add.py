import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
# 1) Insert new button
btn_anchor='self._add_member_button = QPushButton("Add Personnel")'
if btn_anchor in s:
    s=s.replace(btn_anchor, btn_anchor+'\n        self._add_from_master_button = QPushButton("Add From Master")\n        member_buttons.addWidget(self._add_from_master_button)')
# 2) Insert connection
conn_anchor='self._add_member_button.clicked.connect(self._handle_add_member)'
if conn_anchor in s and 'self._add_from_master_button.clicked.connect(self._handle_add_member_from_master)' not in s:
    s=s.replace(conn_anchor, conn_anchor+'\n        self._add_from_master_button.clicked.connect(self._handle_add_member_from_master)')
# 3) Add handler before _handle_member_detail
member_detail_def='def _handle_member_detail(self) -> None:'
if member_detail_def in s and 'def _handle_add_member_from_master(self) -> None:' not in s:
    insert_code='''
    def _handle_add_member_from_master(self) -> None:
        try:
            from modules.command.ics203.panels.dialogs import AssignPersonDialog
        except Exception:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Add From Master", "Search dialog not available.")
            except Exception:
                pass
            return
        dlg = AssignPersonDialog(parent=self)
        try:
            from PySide6.QtWidgets import QDialog
            result = dlg.exec()
        except Exception:
            result = 0
        if result != 1:
            return
        try:
            values = dlg.values() or {}
        except Exception:
            values = {}
        pid = values.get("person_id") if isinstance(values, dict) else None
        if pid in (None, ""):
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Add From Master", "Please select a person from the master roster.")
            except Exception:
                pass
            return
        handler = getattr(self._bridge, "addMemberFromMaster", None)
        if callable(handler):
            try:
                handler(int(pid))
            except Exception:
                pass

'''
    s=s.replace(member_detail_def, insert_code+member_detail_def)
# 4) Add bridge slot addMemberFromMaster
anchor_err='self.error.emit(f"Failed to add member: {e}")'
remove_member_def='@Slot(int)\n    def removeMember(self, person_id: int) -> None:'
if anchor_err in s and 'def addMemberFromMaster' not in s:
    add_code='''

    @Slot('QVariant')
    def addMemberFromMaster(self, person_id: Any = None) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if person_id in (None, ""):
                raise ValueError("person_id required")
            try:
                from modules.logistics.checkin.services import get_service
                svc = get_service()
                svc.check_in("personnel", int(person_id))
            except Exception:
                pass
            try:
                set_person_team(int(person_id), int(self._team.team_id))
            except Exception:
                pass
            try:
                from modules.logistics.checkin import repository as ci_repo
                from modules.logistics.checkin.models import CheckInRecord, CIStatus, PersonnelStatus, Location
                ident = None
                try:
                    ident = ci_repo.get_person_identity(str(person_id))
                except Exception:
                    ident = None
                now_iso = datetime.now().astimezone().isoformat()
                rec = CheckInRecord(
                    person_id=str(person_id),
                    ci_status=CIStatus.CHECKED_IN,
                    personnel_status=PersonnelStatus.ASSIGNED,
                    arrival_time=now_iso,
                    location=Location.ICP,
                    incident_callsign=(getattr(ident, 'callsign', None) if ident else None),
                    incident_phone=(getattr(ident, 'phone', None) if ident else None),
                    team_id=str(self._team.team_id),
                    role_on_team=(getattr(ident, 'primary_role', None) if ident else None),
                )
                ci_repo.save_checkin(rec)
            except Exception:
                pass
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add from master: {e}")
'''
    s=s.replace(anchor_err, anchor_err+add_code)
io.open(p,'w',encoding='utf-8',newline='').write(s)
print('PATCHED')
