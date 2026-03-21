import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
start=re.escape('    def _handle_add_member(self) -> None:')
end_marker='    def _handle_member_detail(self) -> None:'
start_idx=s.find(start)
if start_idx!=-1:
    # find next def _handle_member_detail
    end_idx=s.find('\n'+end_marker)
    if end_idx!=-1 and end_idx>start_idx:
        new='''    def _handle_add_member(self) -> None:\n        try:\n            dlg = AddTeamMemberDialog(self)\n        except Exception:\n            handler = getattr(self._bridge, "addMember", None)\n            if callable(handler):\n                handler()\n            return\n        try:\n            from PySide6.QtWidgets import QDialog\n            result = dlg.exec()\n        except Exception:\n            result = 0\n        if result == 1 and getattr(dlg, 'selected_person_id', None):\n            pid = dlg.selected_person_id\n            handler = getattr(self._bridge, "addMember", None)\n            if callable(handler) and pid not in (None, ""):\n                try:\n                    handler(int(pid))\n                except Exception:\n                    pass\n\n'''
        s=s[:start_idx]+new+s[end_idx:]
        io.open(p,'w',encoding='utf-8',newline='').write(s)
        print('REPLACED')
    else:
        print('END_MARKER_NOT_FOUND')
else:
    print('START_NOT_FOUND')
