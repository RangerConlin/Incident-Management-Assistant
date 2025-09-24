"""Core data models for the IAP Builder module.

The goal of this module is to provide light-weight dataclasses that mirror the
storage representation of the Incident Action Plan (IAP) domain.  They are used
throughout the UI, repository layer, and service orchestration code.  Only
Python standard-library types are used so that the objects are portable across
threads and process boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

__all__ = ["FormInstance", "IAPPackage"]


@dataclass(slots=True)
class FormInstance:
    """Represents a single filled ICS form within an IAP package.

    The dataclass mirrors the structure described in the specification.  Slots
    are enabled to reduce memory footprint and to make instances hashable by
    ``id`` should the UI need to track them in models later on.
    """

    form_id: str
    title: str
    op_number: int
    revision: int = 0
    fields: Dict[str, object] = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)
    status: str = "draft"
    last_updated: datetime = field(default_factory=datetime.utcnow)
    display_order: int = 0

    def mark_updated(self) -> None:
        """Update the ``last_updated`` timestamp to *now*.

        This helper keeps the timestamp update logic in one place so callers do
        not have to replicate ``datetime.utcnow`` usage throughout the module.
        """

        self.last_updated = datetime.utcnow()

    @property
    def is_started(self) -> bool:
        """Return ``True`` when the form has any captured data.

        Started forms are surfaced differently in the dashboard UI.  The logic
        is intentionally conservative—any field value or attachment marks the
        form as started.
        """

        return bool(self.fields or self.attachments)


@dataclass(slots=True)
class IAPPackage:
    """Container for all forms associated with a single operational period."""

    incident_id: str
    op_number: int
    op_start: datetime
    op_end: datetime
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "draft"
    forms: List[FormInstance] = field(default_factory=list)
    notes: str = ""
    version_tag: Optional[str] = None
    published_pdf_path: Optional[str] = None

    def add_form(self, form: FormInstance) -> None:
        """Attach a new :class:`FormInstance` to this package.

        Forms are kept unique by ``form_id``—if a form already exists the
        original instance is replaced.  This mirrors the behaviour expected in
        the dashboard where each ICS form appears only once per operational
        period.
        """

        existing_index = next(
            (index for index, item in enumerate(self.forms) if item.form_id == form.form_id),
            None,
        )
        if existing_index is None:
            self.forms.append(form)
        else:
            self.forms[existing_index] = form
        self.forms.sort(key=lambda item: item.display_order)

    def get_form(self, form_id: str) -> Optional[FormInstance]:
        """Return the form matching ``form_id`` if present."""

        return next((form for form in self.forms if form.form_id == form_id), None)

    def remove_form(self, form_id: str) -> None:
        """Remove the form with ``form_id`` from ``forms`` if it exists."""

        self.forms = [form for form in self.forms if form.form_id != form_id]
        for index, form in enumerate(self.forms):
            form.display_order = index

    @property
    def is_published(self) -> bool:
        """Convenience flag used by the UI to toggle behaviour."""

        return self.status == "published"
