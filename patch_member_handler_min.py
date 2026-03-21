# -*- coding: utf-8 -*-
import io
p='modules/operations/teams/panels/team_detail_window.py'
text=io.open(p,'r',encoding='utf-8').read()
start_token='def _handle_add_member(self) -> None:'
end_token='def _handle_member_detail(self) -> None:'
s_idx=text.find(start_token)
e_idx=text.find(end_token, s_idx)
if s_idx==-1 or e_idx==-1:
    print('TOKENS_NOT_FOUND')
else:
    new_block='''def _handle_add_member(self) -> None:
        # Simple chooser for unassigned personnel; passes selection to the bridge.
        try:
            options = self._bridge.availableMembers() if hasattr(self._bridge, "availableMembers") else []
        except Exception:
            options = []
        opts = [o for o in (options or []) if isinstance(o, dict)]
        if not opts:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Add Personnel", "No unassigned personnel. Use Logistics -> Check-In to add or unassign people.")
            except Exception:
                pass
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox, QComboBox, QLabel
        dlg = QDialog(self); dlg.setWindowTitle("Add Personnel")
        v = QVBoxLayout(dlg)
        row = QHBoxLayout(); v.addLayout(row)
        row.addWidget(QLabel("Select person:"))
        cmb = QComboBox(dlg); row.addWidget(cmb, 1)
        for rec in opts:
            pid = rec.get("id")
            name = str(rec.get("name") or "Unknown")
            callsign = str(rec.get("callsign") or "").strip()
            role = str(rec.get("role") or "").strip()
            phone = str(rec.get("phone") or "").strip()
            parts = [name]
            if callsign:
                parts.append("[" + callsign + "]")
            if role:
                parts.append(role)
            if phone:
                parts.append(phone)
            label = " - ".join(parts)
            cmb.addItem(label, pid)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg)
        v.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        sel_id = cmb.currentData()
        handler = getattr(self._bridge, "addMember", None)
        if callable(handler) and sel_id not in (None, ""):
            try:
                handler(int(sel_id))
            except Exception:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Add Personnel", "Could not assign selected person to the team.")
'''
    new_text = text[:s_idx] + new_block + text[e_idx:]
    io.open(p,'w',encoding='utf-8',newline='').write(new_text)
    print('PATCHED_ADD_HANDLER')
