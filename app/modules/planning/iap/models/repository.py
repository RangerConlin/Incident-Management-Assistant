"""Persistence layer scaffolding for the IAP Builder.

The repository will eventually manage SQLite persistence for incident action
plans.  At this stage we expose the public API and document the expected
behaviour; each method raises :class:`NotImplementedError` so that downstream
callers are reminded that the implementation is pending.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .iap_models import FormInstance, IAPPackage

__all__ = ["IAPRepository"]


class IAPRepository:
    """Encapsulates read/write operations for IAP packages and forms."""

    def __init__(self, incident_db: Path, master_db: Path | None = None):
        self.incident_db = Path(incident_db)
        self.master_db = Path(master_db) if master_db else None

    # -- lifecycle -----------------------------------------------------------------
    def initialize(self) -> None:
        """Ensure the required SQLite tables exist."""

        raise NotImplementedError("Database initialisation has not been implemented yet.")

    # -- package operations ---------------------------------------------------------
    def list_packages(self, incident_id: str) -> List[IAPPackage]:
        """Return all packages for ``incident_id`` ordered by operational period."""

        raise NotImplementedError

    def get_package(self, incident_id: str, op_number: int) -> IAPPackage:
        """Fetch a single package for ``incident_id`` and ``op_number``."""

        raise NotImplementedError

    def save_package(self, package: IAPPackage) -> IAPPackage:
        """Insert or update ``package`` in the database."""

        raise NotImplementedError

    # -- form operations ------------------------------------------------------------
    def save_form(self, package: IAPPackage, form: FormInstance) -> FormInstance:
        """Persist ``form`` as part of ``package``."""

        raise NotImplementedError

    def save_forms(self, package: IAPPackage, forms: Iterable[FormInstance]) -> None:
        """Bulk persist forms."""

        raise NotImplementedError

    def changelog_for_form(self, form_id: int) -> List[dict]:
        """Return change log entries for the database row ``form_id``."""

        raise NotImplementedError
