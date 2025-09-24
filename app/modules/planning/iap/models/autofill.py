"""Autofill scaffolding for the IAP Builder module.

The real implementation will fetch data from the incident and master databases
using mappings defined inside the ``ics_forms`` package.  For the scaffold we
provide light-weight placeholder objects that mimic the eventual API.  This
allows the UI and services to reason about autofill previews without needing the
full data plumbing in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

from .iap_models import FormInstance

__all__ = ["AutofillResult", "AutofillEngine", "AutofillRule"]


@dataclass(slots=True)
class AutofillRule:
    """Represents a single mapping from a data source into a form field."""

    target_field: str
    source: str
    description: str = ""


@dataclass(slots=True)
class AutofillResult:
    """Outcome of running autofill rules for a specific form."""

    form_id: str
    populated_fields: Dict[str, object] = field(default_factory=dict)
    sources: Dict[str, str] = field(default_factory=dict)

    def summary_lines(self) -> List[str]:
        """Return a list of human readable summary lines."""

        lines = []
        for field, value in self.populated_fields.items():
            source = self.sources.get(field, "unknown source")
            lines.append(f"{field}: {value} (from {source})")
        return lines


class AutofillEngine:
    """Minimal placeholder engine used by the UI scaffolding.

    Parameters
    ----------
    form_rules:
        Optional mapping of ``form_id`` to the rules that should be applied.  In
        the production implementation these rules will come from the
        ``ics_forms`` templates via the Profile Manager.
    """

    def __init__(self, form_rules: Optional[Mapping[str, Iterable[AutofillRule]]] = None):
        self._form_rules: Dict[str, List[AutofillRule]] = {
            form_id: list(rules) for form_id, rules in (form_rules or {}).items()
        }

    def preview_for_form(self, form: FormInstance) -> AutofillResult:
        """Generate a preview of autofilled values for ``form``.

        Until the backend plumbing is wired up the preview simply echoes the
        current ``FormInstance.fields`` and annotates them with any configured
        rules.  This still gives the UI meaningful data to display while the
        remainder of the system is built out.
        """

        rules = self._form_rules.get(form.form_id, [])
        populated_fields = dict(form.fields)
        sources = {rule.target_field: rule.source for rule in rules}

        # Ensure every populated field has at least a generic source label so
        # that the preview panel can render something informative.
        for field in populated_fields:
            sources.setdefault(field, "existing value")

        return AutofillResult(form_id=form.form_id, populated_fields=populated_fields, sources=sources)

    def describe_rules(self, form_id: str) -> List[str]:
        """Return short descriptions for the rules tied to ``form_id``."""

        return [rule.description or f"{rule.target_field} ← {rule.source}" for rule in self._form_rules.get(form_id, [])]
