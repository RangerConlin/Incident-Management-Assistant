# Apps

User-facing clients live here.

- `desktop/` is the target home for the PySide desktop application.
- `mobile/` is the target home for the Flutter mobile application.
- `web/` is the target home for the browser client.

During migration, existing runtime code may still live in legacy top-level
folders. Move one client at a time and update `docs/architecture/repo_file_inventory.md`
as work completes.
