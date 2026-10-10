# Table UI Standards

Canonical rules for every `QTableWidget`/`QTableView` in the app. Required by
`agents.md`'s hard rules: user-resizable columns, and a clear outer border
around the selected row.

## Use the shared helper

`utils/table_view_styles.py::apply_statusboard_table_behavior(table, ...)`
is the one shared setup function for table behavior — despite the name
(historical; it started on the status boards), it is the general-purpose
helper and should be used for any new or edited table, not just status
boards. It currently wires up:

- Row selection (`SelectRows`, `SingleSelection`), no inline editing.
- Interactive (user-resizable) column headers — satisfies the hard rule.
- The row-outline selection delegate (`utils/itemview_delegates.py::RowOutlineSelectionDelegate`)
  — satisfies the "clear outer border around the selected row" hard rule.
  It paints a themed outline around the whole selected row instead of a
  filled highlight, so per-row status-color backgrounds (team/task/resource
  status tints, etc.) stay visible under the selection.

When building a table from scratch, call this helper after the model is set
instead of hand-rolling selection/header/delegate setup. When editing an
existing table that predates this helper, adopt it in the same change if the
table doesn't already have equivalent resizable-columns + outline-selection
behavior.

## Density — fit rows without scrolling

Row height is driven by the app-wide font (`main.py`, Segoe UI 9pt) and the
global `QAbstractItemView::item` padding in `styles/qss_helpers.py`
(`global_qss`) — both apply automatically, no per-table code needed. Don't
override padding/row height per-panel; if a table still needs more vertical
room than its dock gives it, fix the dock's default size/splitter
proportions rather than shrinking the table further.

## Colors

Never hardcode colors on a table (see `agents.md`'s color rule). Row/status
tint colors come from `styles/styles.py`'s `*_status_colors()` accessors
(`TEAM_STATUS`, `TASK_STATUS`, `RESOURCE_STATUS`, etc.), and the selection
outline color should come from `get_palette()["ctrl_focus"]` (what
`apply_statusboard_table_behavior` already uses) rather than a literal hex.
Widgets that recolor rows by domain status must call `subscribe_theme` so
they repaint on theme switch.

## Checklist for a new/edited table

- [ ] Columns are `QHeaderView.Interactive` (user-resizable).
- [ ] Selected row shows the outline delegate, not a filled selection block.
- [ ] No hardcoded hex colors; status tints and the selection color come
      from `styles/styles.py` / `get_palette()`.
- [ ] No per-table row-height/padding override fighting the global density
      settings.
- [ ] Theme switch (dark/light) re-colors the table via `subscribe_theme`.
