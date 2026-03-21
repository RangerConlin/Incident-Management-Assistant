import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
pattern=r"def _handle_add_member\(self\) -> None:\n\s*handler = getattr\(self\._bridge, \"addMember\", None\)\n\s*if callable\(handler\):\n\s*\s*handler\(\)"
replacement='''def _handle_add_member(self) -> None:
        try:
            dlg = AddTeamMemberDialog(self)
        except Exception:
            handler = getattr(self._bridge, "addMember", None)
            if callable(handler):
                handler()
            return
        try:
            from PySide6.QtWidgets import QDialog
            result = dlg.exec()
        except Exception:
            result = 0
        if result == 1 and getattr(dlg, 'selected_person_id', None):
            pid = dlg.selected_person_id
            handler = getattr(self._bridge, "addMember", None)
            if callable(handler) and pid not in (None, ""):
                try:
                    handler(int(pid))
                except Exception:
                    pass
'''
ns=re.sub(pattern,replacement,s,flags=re.S)
if ns==s:
    print('PATTERN_NOT_FOUND')
else:
    io.open(p,'w',encoding='utf-8',newline='').write(ns)
    print('PATCHED')
