"""Desktop frontend for SARApp's shared, program-wide Checklist system.

This package is intentionally not under `modules/plannedtoolkit/` even
though the Planned Events Toolkit is its first consumer (Phase 4C) — the
backend (`server/sarapp_db/sarapp_db/api/routers/checklists.py` /
`checklist_templates.py`, Phases 4A/4B) is explicitly program-wide, and
`widgets/checklist_execution_widget.py` / `widgets/checklist_list_widget.py`
are written to depend only on checklist identity/context, never on
Planned-Events-specific models, so another module can later embed the same
widgets. `modules/plannedtoolkit/windows.py` imports and places them; it
owns none of the checklist logic itself.
"""
