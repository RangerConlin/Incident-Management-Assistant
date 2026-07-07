"""Legacy import surface for the Public Information release workflow."""
from __future__ import annotations

from modules.public_information.dialogs.release_editor_dialog import ReleaseEditorDialog as MessageEditor
from modules.public_information.panels.release_manager import ReleaseManagerPanel as MessageManagerPanel
from modules.public_information.widgets.release_lifecycle_panel import ReleaseLifecyclePanel as ApprovalWorkflowPanel
from modules.public_information.widgets.release_preview import ReleasePreviewWidget as ReleasePreviewPanel

__all__ = [
    "ApprovalWorkflowPanel",
    "MessageEditor",
    "MessageManagerPanel",
    "ReleasePreviewPanel",
]

