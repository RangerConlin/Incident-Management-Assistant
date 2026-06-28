# New UI Panel

Scaffold a new UI panel or widget following design standards.

## Usage

```
/new-ui-panel operations DashboardPanel
/new-ui-panel logistics TeamTablePanel --with-table
/new-ui-panel reports ExportDialog --dialog
```

## What It Creates

```
modules/mymodule/panels/dashboard.py

class DashboardPanel(QWidget):
    """Operations dashboard panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        # Widgets here
        self.setLayout(layout)
        self.apply_styles()
    
    def apply_styles(self):
        """Apply shared palette and styles"""
        from utils.styles import get_palette
        palette = get_palette()
```

## Panel Types

- **Dashboard** — Main data view with summary info
- **Table** — Sortable, resizable table (with `--with-table`)
- **Dialog** — Modal dialog for forms (with `--dialog`)
- **Widget** — Reusable component

## Options

- `--with-table` — Include table design (follows `tabledesign.md`)
- `--dialog` — Create modal dialog instead of panel
- `--with-forms` — Add form fields and validation
- `--with-buttons` — Add action buttons

## What It Includes

- ✅ Correct PySide6 structure
- ✅ Shared palette integration (`utils.styles`)
- ✅ Table support with resizable columns
- ✅ ADS dock integration
- ✅ Theme-aware styling
- ✅ Logging for UI events
- ✅ Test stubs with Qt fixtures

## Table Features (if `--with-table`)

- ✅ User-resizable columns (per `tabledesign.md`)
- ✅ Clear outer border on selected row
- ✅ Sortable headers
- ✅ Context menus
- ✅ Copy/export support

## Design Standards

All UI follows:
- **Palette** — Use `get_palette()` from `utils.styles`
- **Spacing** — Consistent margins (8px default)
- **Tables** — See `Design Documents/Instructions/tabledesign.md`
- **Dialogs** — Modal, centered, proper buttons
- **Accessibility** — Clear labels, keyboard navigation

## Next Steps

1. Connect to data source (API or repository)
2. Add user interactions (clicks, edits)
3. Wire into module's `__init__.py`
4. Test with `/quick-start`
5. Validate styling with `/check-architecture`

## Common Patterns

**Connect to API:**
```python
from utils.api_client import APIClient
client = APIClient()
data = client.get("/api/operations")
```

**Update from signals:**
```python
def on_data_changed(self, new_data):
    self.table.setRowCount(len(new_data))
    # Populate table
```

**Apply theme:**
```python
self.apply_styles()  # Auto-applies current theme
```
