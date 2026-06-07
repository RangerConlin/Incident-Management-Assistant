from __future__ import annotations

from modules.forms.services import MigrationService


def dry_run_migration() -> dict:
    return MigrationService().dry_run()


def migrate_legacy_forms(*, dry_run: bool = True) -> dict:
    return MigrationService().migrate(dry_run=dry_run)
