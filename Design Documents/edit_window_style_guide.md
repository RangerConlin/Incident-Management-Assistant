# Edit-Menu Window Style Guide

## Status

Draft standard. `vehicle_inventory_panel.py` was the starting reference point, not a verbatim template — this document is
the actual spec; deviate from the Vehicle Inventory source where it conflicts with what's written below.

## Scope

This is a single tier, applied identically to every window opened from the **Edit** menu, regardless of how few rows or
fields the underlying data has. Task Types, Team Types, Hazard Types, etc. get the same card shell, filter bar, table
delegate, pagination, import wizard, and async export as Vehicles/Personnel/Aircraft — no "simple lookup table" exception.
There is no detail pane: selecting a row does not open a side panel. Opening a record for editing/viewing is exclusively
the job of the Add/Edit dialog, launched by the header "Add" button or by activating a row (double-click/Enter).

## Window shell

- Modeless top-level window: `QWidget(parent, Qt.Window)`, not `QMainWindow` or `QDialog`. No menu bar, no status bar.
- Fixed initial size via `resize(w, h)`; window is otherwise resizable.
- All content lives inside a single rounded "card" `QFrame`:
  ```python
  card.setStyleSheet("""
      #cardObjectName {
          border-radius: 16px;
          background: palette(Base);
          border: 1px solid palette(Midlight);
      }
  """)
  ```
  Card margins: 20px. Outer window margins: 12px. Card layout spacing: 16px.

## Header row

- `QHBoxLayout`: title label (`font-size: 22px; font-weight: 700;`) on the left, stretch, then action buttons on the right.
- Header buttons are `QPushButton` with a standard Qt icon (`self.style().standardIcon(...)`) plus text, `PointingHandCursor`,
  and a tooltip. Order, left to right: **Add → Import → Export**. Add edit-specific actions (e.g. Delete, Duplicate) between
  Add and Import if needed, but never re-order Add/Import/Export relative to each other.
- Labels are the short verb only: "Add", not "Add Vehicle"; "Import"/"Export", not "Import CSV". Use the tooltip for detail.

## Filter bar

- Directly below the header inside the card: a `QHBoxLayout` with a debounced search `QLineEdit` (placeholder
  `"Search <items>…"`, clear button enabled) at `stretch=2`, then filter `QComboBox`es, then a "Reset filters" link-style
  `QToolButton` that only appears once a filter is active.
- Debounce search input ~250ms before re-querying.

## Error banner

- A collapsible `QFrame` (hidden by default) directly under the filter bar for load/save failures: light red background
  (`#fdecea`), red border (`#f5c6cb`), red text (`#b71c1c`), with a "Retry" button. Show only on error; hide otherwise. Don't
  use blocking `QMessageBox` for recoverable load failures — reserve message boxes for one-off action results (e.g. export
  complete) and destructive confirmations.

## Table

- `QTableView` + `QAbstractTableModel`, never `QTableWidget`, for any list of records.
- `setAlternatingRowColors(False)`; selection styling comes from the shared `RowOutlineSelectionDelegate`
  (`utils/itemview_delegates.py`) — reuse it, don't re-implement row highlighting per window.
- `setEditTriggers(NoEditTriggers)` — editing happens in a separate Add/Edit dialog, never inline.
- Vertical header hidden; row height fixed via `setDefaultSectionSize(44)`.
- Horizontal header: `setStretchLastSection(True)`, `setSectionsClickable(True)`, `setSortIndicatorShown(True)`; clicking a
  header sorts (toggle asc/desc), don't add separate sort dropdowns.
- Status-like columns render via a `QStyledItemDelegate` pill (rounded colored background, bold centered text) — model
  `STATUS_COLORS` after `VehicleInventoryPanel.STATUS_COLORS`. Tag/category columns render as wrapping chip delegates.
- Empty states: distinguish "no rows ever" (first-run, with an inline "Add" CTA) from "no rows matching filters" (with a
  "Clear filters" CTA) via a `QStackedLayout`.

## No detail pane

- There is no split-view detail panel anywhere in this standard. The table is the only view of the record list; clicking a
  row just selects it (for row-scoped actions and Export "Selected rows only"). To see or change a record's fields, the
  user opens the Add/Edit dialog.

## Pagination

- Every window's table is paginated, including small lookup tables. Footer row under the table: status label
  (`"{start}–{end} of {total}"`), stretch, page-size `QComboBox` (e.g. 20/50/100), prev/next `QToolButton`s with standard
  arrow icons. A table with fewer rows than one page just shows page 1 of 1 with both nav buttons disabled — that's fine,
  don't special-case small datasets out of the pagination footer.

## Add / Edit flow

- Add and Edit both open the same modal record editor dialog (e.g. `VehicleEditDialog`), launched via the header "Add"
  button or by activating (double-click/Enter) a row. Don't have separate "Add" and "Edit" buttons unless the record type
  genuinely needs a distinct edit entry point beyond row activation.
- On save, reselect and scroll to the saved row, then show a toast (see below) — don't pop a blocking "Saved" dialog.

## Import / Export

Both are part of the baseline for every Edit-menu window, not just large datasets.

- Import: multi-step `QWizard` (Upload file → Map columns → Preview with invalid-row highlighting → Run with progress bar
  and error CSV download). Use this shape even for small lookup tables — a 5-row Task Types import still goes through the
  same four pages, just finishes instantly.
- Export: a small `QDialog` to choose scope (All / Current filters / Selected rows), format (CSV/XLSX), field selection,
  and sort order, then run the export off the UI thread (`QtConcurrent.run` + `QFutureWatcher`, falling back to a
  `QThread` worker when `QFutureWatcher` isn't available) — always off-thread, even when the dataset is small enough that
  it wouldn't visibly block. The point is one consistent code path everywhere, not performance-justified-per-window.
- A shared `BaseRecordEditorPanel` (or equivalent) should own this plumbing (wizard pages, export dialog, thread/future
  handling) so individual windows configure field lists/labels rather than re-implementing the wizard and worker thread
  per module — see Migration notes.

## Feedback

- Use the shared notifier (`notifications.services.get_notifier()` + `Notification`) for success/info/warning toasts on
  background-thread results (saves, imports, exports). Reserve `QMessageBox` for: destructive confirmations, and the final
  result of a user-initiated modal action (e.g. "Export ready" with the file path).

## Naming conventions

- Soft-delete / lifecycle actions: use **Deactivate** + **Activate**, not Delete/Restore/Archive/Toggle Active — pick one
  vocabulary across all editors. Use **Delete** only for genuinely permanent removal of a record with no other references.
- Use **Duplicate**, not "Clone".

## Migration notes

- This guide describes the target state; no current window (including Vehicle Inventory) fully matches it yet — Vehicle
  Inventory needs its detail pane removed to conform.
- Because every window now needs the same wizard/export/pagination/delegate plumbing, build the shared base
  (table+model wrapper, header/filter-bar widget, import wizard, export dialog, async export runner) once before
  migrating individual windows, rather than copy-pasting Vehicle Inventory's version into each module. Reuse
  `RowOutlineSelectionDelegate` and `notifications.services.get_notifier()` as-is; they're already shared.
- Migrate windows one at a time once the shared base exists; this is a larger effort tracked outside this document.
