from __future__ import annotations

"""Dialog for creating a new channel and adding it to the plan."""

from typing import Any, Dict

from .channel_dialog import ChannelDialog


class NewChannelDialog(ChannelDialog):
    def __init__(self, incident_repo, parent=None):
        super().__init__(row=None, title="New Channel", parent=parent)
        self._repo = incident_repo

        # Wire duplicate check
        for w in (self.ed_name, self.ed_rx, self.ed_tx):
            w.textChanged.connect(self._check_duplicate)

    def _check_duplicate(self):
        try:
            rx = float(self.ed_rx.text()) if self.ed_rx.text().strip() else None
            tx = float(self.ed_tx.text()) if self.ed_tx.text().strip() else None
        except ValueError:
            rx = tx = None
        name = self.ed_name.text().strip()
        dups = []
        for r in self._repo.list_plan():
            same_name = name and (r.get("channel") or "").strip().lower() == name.lower()
            same_freq = (rx is not None and r.get("rx_freq") == rx) and (
                (tx or 0) == (r.get("tx_freq") or 0)
            )
            if same_name or same_freq:
                dups.append(r)
        if dups:
            self.set_dup_warning(f"• Potential duplicate: {len(dups)} similar row(s) already exist")
        else:
            self.set_dup_warning("")

    def get_channel_data(self) -> Dict[str, Any]:
        return self.get_patch()


__all__ = ["NewChannelDialog"]
