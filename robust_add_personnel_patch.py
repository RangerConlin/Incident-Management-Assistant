import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
start='    def _handle_add_member(self) -> None:'
end='    def _handle_member_detail(self) -> None:'
si=s.find(start)
ei=s.find(end,si)
if si!=-1 and ei!=-1:
    new='''    def _handle_add_member(self) -> None:
        try:
            from PySide6.QtWidgets import QDialog, QMessageBox
            dlg = AddTeamMemberDialog(self)
            result = dlg.exec()
            if result == QDialog.Accepted and getattr(dlg, 'selected_person_id', None):
                pid = dlg.selected_person_id
                handler = getattr(self._bridge, "addMember", None)
                if callable(handler) and pid not in (None, ""):
                    try:
                        handler(int(pid))
                    except Exception:
                        QMessageBox.warning(self, "Add Personnel", "Could not assign selected person to the team.")
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Add Personnel", f"Could not open selector: {e}")
            except Exception:
                pass

'''
    s=s[:si]+new+s[ei:]
    io.open(p,'w',encoding='utf-8',newline='').write(s)
    print('PATCHED')
else:
    print('RANGE_NOT_FOUND')
