"""Binding utilities used by the form creator module.

Bindings allow authors to connect a field to structured data that is available
elsewhere in the application.  The implementation below purposefully keeps the
resolver tiny yet expressive: dotted paths are expanded against regular Python
mappings and attribute-bearing objects.  Additional providers can be registered
at runtime to support dynamic keys (for example, computed summaries).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SystemBinding:
    """Simple descriptor used to populate UI widgets."""

    key: str
    label: str
    description: str | None = None


class Binder:
    """Resolve dotted keys against context dictionaries."""

    #: Minimal catalogue of useful keys.  Additional items may be registered at
    #: runtime by instantiating :class:`Binder` with custom ``system_keys``.
    DEFAULT_SYSTEM_KEYS: tuple[SystemBinding, ...] = (
        SystemBinding("incident.ic_name", "Incident Commander", "Primary incident commander name"),
        SystemBinding("incident.number", "Incident Number", "Official incident identifier"),
        SystemBinding("incident.op_period", "Operational Period", None),
        SystemBinding("incident.location", "Incident Location", None),
        SystemBinding("planning.scribe", "Planning Scribe", None),
        SystemBinding("teams.current.team_id", "Current Team ID", None),
        SystemBinding(
            "operations.ics204.team_leader",
            "ICS 204 Team Leader",
            "Leader name for the active ICS 204 assignment",
        ),
        SystemBinding(
            "operations.ics204.team_leader_contact",
            "ICS 204 Team Leader Contact",
            "Primary contact information for the ICS 204 team leader",
        ),
        SystemBinding(
            "operations.ics204.assignment",
            "ICS 204 Assignment Summary",
            "Narrative assignment details for the ICS 204",
        ),
        SystemBinding(
            "operations.ics204.resources",
            "ICS 204 Assigned Resources",
            "List of resources associated with the selected ICS 204",
        ),
    )

    def __init__(self, *, system_keys: tuple[SystemBinding, ...] | None = None):
        self._system_keys = system_keys or self.DEFAULT_SYSTEM_KEYS
        self._providers: dict[str, Callable[[Mapping[str, Any]], Any]] = {}

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def register_provider(self, prefix: str, provider: Callable[[Mapping[str, Any]], Any]) -> None:
        """Register a callable that resolves dotted keys with the given prefix."""

        self._providers[prefix] = provider

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def available_keys(self) -> list[SystemBinding]:
        """Return the list of known system binding keys."""

        return list(self._system_keys)

    # ------------------------------------------------------------------
    def resolve(self, context: Mapping[str, Any], dotted_key: str) -> Any:
        """Resolve ``dotted_key`` using ``context`` and registered providers."""

        dotted_key = dotted_key.strip()
        if not dotted_key:
            raise ValueError("binding key cannot be blank")

        # Provider lookup
        for prefix, provider in self._providers.items():
            if dotted_key == prefix or dotted_key.startswith(prefix + "."):
                return provider(context)

        parts = dotted_key.split(".")
        current: Any = context
        for part in parts:
            if isinstance(current, Mapping):
                if part not in current:
                    raise KeyError(f"Unable to resolve '{dotted_key}' (missing key '{part}')")
                current = current[part]
            else:
                if not hasattr(current, part):
                    raise KeyError(
                        f"Unable to resolve '{dotted_key}' (object {current!r} has no attribute '{part}')"
                    )
                current = getattr(current, part)
                if callable(current):
                    current = current()
        return current


# Convenience singleton for modules that prefer a simple functional interface.
_default_binder = Binder()


def resolve(context: Mapping[str, Any], dotted_key: str) -> Any:
    """Resolve a dotted key using the default binder instance."""

    return _default_binder.resolve(context, dotted_key)
