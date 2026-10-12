# Repository File Inventory

Editable migration tracker generated from `repo_file_inventory.xlsx`. Use `Actual status` and `Decision notes` as the working columns while files are moved, kept, archived, excluded, or deleted.

## Working Rule

When a file's migration decision has been completed and no further action is needed, delete that file's row from this inventory. The tracker should shrink over time and represent only remaining work.

## Summary

- Files inventoried: 0
- Migration rows completed and removed.
- Desktop source, assets, forms, styles, profiles, modules, panels, utilities, and bridge code now live under `apps/desktop/sarapp_desktop/`.
- Root entry/config files (`main.py`, `sarapp_server.py`, `conftest.py`, `pyproject.toml`, `pytest.ini`, `requirements.txt`, `settings.json`, `Start SARApp Desktop.bat`, `.claude/settings.json`, `.vscode/settings.json`) are intentionally kept at repository root for the staged migration because current launch/test tooling and cwd-relative runtime config still depend on them.
- Root `settings/` is intentionally kept at repository root for now because desktop and server-side code still read those files via cwd-relative `settings/...` paths, including shared geocoding config.

### Suggested disposition

| Suggested disposition | Files |
| --- | ---: |

### Migration phase

| Migration phase | Files |
| --- | ---: |

### Repository

| Repository | Files |
| --- | ---: |

## Legend

- `Exclude from migration` means generated/local content such as caches, build outputs, virtualenvs, compiled files, IDE metadata, or local tool artifacts. It does not mean source code should be deleted.
- `Actual status` is the live working field. Suggested values: `Not started`, `Kept`, `Moved`, `Deleted`, `Archived`, `Excluded`, `Needs review`, `Blocked`.
- `Decision notes` is intentionally blank for human migration notes.
- `Legacy import refs` counts Python import lines from old top-level roots in that file.
- `Path assumption refs` counts likely path coupling such as `sys.path`, `Path(__file__)`, or old directory names.

## Inventory

| Actual status | Repository | Relative path | Suggested disposition | Suggested new location | Category | Migration phase | Confidence | Legacy import refs | Path assumption refs | Decision notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
