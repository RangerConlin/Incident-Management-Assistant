"""Shared helper for populating organization-name dropdowns from the
Units & Organizations master list (modules/personnel/units_organizations).

Used anywhere an "Organization"/"Agency" free-text field exists today
(personnel, vehicle, aircraft, check-in) so the master org list actually
drives data entry without requiring a schema migration: the underlying
field stays a plain string.
"""
from __future__ import annotations

import logging

from PySide6.QtWidgets import QComboBox

logger = logging.getLogger(__name__)


def list_organization_names() -> list[str]:
    """Return sorted, de-duplicated organization names from the master list.

    Never raises - callers are building UI forms and should degrade to an
    empty list (still-editable combo) rather than fail to open.
    """
    try:
        from modules.personnel.units_organizations.models.repository import (
            UnitsOrganizationsRepository,
        )

        rows = UnitsOrganizationsRepository().list_organizations(include_inactive=False)
        names = {str(row.get("name") or "").strip() for row in rows}
        names.discard("")
        return sorted(names, key=str.lower)
    except Exception:
        logger.exception("Failed to load organization names for combo population")
        return []


def make_org_combo(current_value: str = "") -> QComboBox:
    """Build an editable QComboBox populated from Units & Organizations.

    `current_value` is preserved as the current text even if it isn't in
    the master list yet, so existing free-text data round-trips untouched
    and ad hoc entry for organizations not yet in the master list still
    works.
    """
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    names = list_organization_names()
    combo.addItems(names)
    current_value = (current_value or "").strip()
    if current_value:
        combo.setCurrentText(current_value)
    else:
        combo.setCurrentIndex(-1)
        combo.clearEditText()
    return combo
