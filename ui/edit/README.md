# QtWidgets Editors

This directory provides replacements for the historic QML-based edit dialogs.
The widgets are intentionally lightweight so they can be launched modelessly
from the main window.  `base_dialog.py` supplies the common CRUD framework.

Currently only the `RolesEditor` is fully wired to the master database.  The
other editors are placeholders that demonstrate how new editors can be added
and will be expanded in future work.

To create a new editor:

1. Derive a dialog from `BaseEditDialog`.
2. Define table columns via `set_columns`.
3. Provide an adapter with `list/create/update/delete` methods.
4. Implement `_populate_form` and `_collect_form` to map data to the form.
5. Wire the editor into the main window menu.
