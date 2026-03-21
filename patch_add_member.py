import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
pattern=r"def _handle_add_member\(self\) -> None:\n\s*handler = getattr\(self\._bridge, \"addMember\", None\)\n\s*if callable\(handler\):\n\s*\s*handler\(\)"
replacement='''def _handle_add_member(self) -> None:
        # Open a simple chooser for unassigned personnel and pass the selection to the bridge.
        try:
            options = self._bridge.availableMembers() if hasattr(self._bridge, "availableMembers") else []
        except Exception:
            options = []
        # Normalize and guard
        opts = [o for o in (options or []) if isinstance(o, dict)]
        if not opts:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Add Personnel", "No unassigned personnel available.")
            except Exception:
                pass
            return
        # Build dialog inline to avoid new dependencies
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox, QComboBox, QLabel
        dlg = QDialog(self); dlg.setWindowTitle("Add Personnel")
        v = QVBoxLayout(dlg)
        row = QHBoxLayout(); v.addLayout(row)
        row.addWidget(QLabel("Select person:"))
        cmb = QComboBox(dlg); row.addWidget(cmb, 1)
        # Fill combo and keep mapping to ids
        for rec in opts:
            pid = rec.get("id")
            name = str(rec.get("name") or "Unknown")
            callsign = str(rec.get("callsign") or "").strip()
            role = str(rec.get("role") or "").strip()
            phone = str(rec.get("phone") or "").strip()
            parts = [name]
            if callsign: parts.append(f"[{callsign}]")
            if role: parts.append(role)
            if phone: parts.append(phone)
            label = "  ".join(parts)
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
                pass
'''
ns=re.sub(pattern,replacement,s,flags=re.S)
if ns==s:
    print('PATTERN_NOT_FOUND')
else:
    io.open(p,'w',encoding='utf-8',newline='').write(ns)
    print('PATCHED')
