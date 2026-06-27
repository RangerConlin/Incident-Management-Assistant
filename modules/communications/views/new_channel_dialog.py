from __future__ import annotations

"""Dialog for creating a brand-new channel in the master catalog.

This always creates a master channel definition (the channel becomes
available to every incident, not just this one) - there is no such thing as
an incident-only channel. The caller is responsible for then referencing the
new master channel in the active incident's plan.
"""

from typing import Any, Dict

from .channel_dialog import ChannelDialog


class NewChannelDialog(ChannelDialog):
    def __init__(self, master_repo, parent=None):
        super().__init__(row=None, title="New Channel", parent=parent)
        self._master_repo = master_repo

        # Wire duplicate check against the master catalog (creating a
        # near-identical master channel is the mistake to flag here, not a
        # second incident reference to an existing one).
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
        for r in self._master_repo.list_channels({}):
            same_name = name and (r.get("name") or "").strip().lower() == name.lower()
            same_freq = (rx is not None and r.get("rx_freq") == rx) and (
                (tx or 0) == (r.get("tx_freq") or 0)
            )
            if same_name or same_freq:
                dups.append(r)
        if dups:
            self.set_dup_warning(f"• Potential duplicate: {len(dups)} similar channel(s) already exist in the library")
        else:
            self.set_dup_warning("")

    def get_channel_data(self) -> Dict[str, Any]:
        return self.get_patch()


__all__ = ["NewChannelDialog"]
