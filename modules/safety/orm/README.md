# Safety ORM Module

The Safety ORM submodule provides a per-operational period CAPF 160 editor for
incidents. It stores the single form for each incident + operational period
inside the incident SQLite database under `data/incidents/<incident>.db`.

## Features

* Singleton CAPF 160 record per incident/operational period.
* Hazard table with risk calculations and policy enforcement.
* Automatic highest residual risk evaluation with approval blocking when any
  hazard is High or Extremely High.
* Offline PDF export with watermark when approval is blocked.
* Full audit logging for form and hazard edits.

## Data Storage

The ORM tables live in the active incident database and are created on first
use:

* `orm_form` – one row per incident/op pair.
* `orm_hazards` – hazard entries for a form.
* `audit_logs` – shared audit table extended with ORM-specific fields.

## Development

Run the ORM tests with:

```bash
pytest modules/safety/orm/tests --import-mode=importlib
```

To view the desktop UI, launch the main application and open **Safety → CAP ORM
(Per OP)** from the menu. The widget is implemented with PySide6 widgets and
works fully offline.
