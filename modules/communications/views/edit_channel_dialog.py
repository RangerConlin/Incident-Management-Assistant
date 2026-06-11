from __future__ import annotations

"""Dialog for editing an existing ICS-205 plan row."""

from typing import Any, Dict

from .channel_dialog import ChannelDialog


class EditChannelDialog(ChannelDialog):
    def __init__(self, row: Dict[str, Any], parent=None):
        super().__init__(row=row, title="Edit Channel", parent=parent)


__all__ = ["EditChannelDialog"]
