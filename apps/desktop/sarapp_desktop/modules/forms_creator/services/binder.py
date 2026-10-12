"""Binding utilities used by the form creator module.

Bindings allow authors to connect a field to structured data that is available
elsewhere in the application.  The implementation below purposefully keeps the
resolver tiny yet expressive: dotted paths are expanded against regular Python
mappings and attribute-bearing objects.  Additional providers can be registered
at runtime to support dynamic keys (for example, computed summaries).  Authors
can also define their own bindings which are persisted to disk so the options
reappear the next time the designer is opened.
"""

from __future__ import annotations

import json
from pathlib import Path
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

    def __init__(
        self,
        *,
        system_keys: tuple[SystemBinding, ...] | None = None,
        custom_bindings_path: Path | str | None = None,
    ) -> None:
        self._system_keys = system_keys or self.DEFAULT_SYSTEM_KEYS
        self._custom_bindings_path = Path(custom_bindings_path) if custom_bindings_path else None
        self._custom_keys: list[SystemBinding] = []
        self._load_custom_bindings()
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

        return [*self._system_keys, *self._custom_keys]

    # ------------------------------------------------------------------
    def custom_bindings(self) -> list[SystemBinding]:
        """Return the list of persisted custom bindings."""

        return list(self._custom_keys)

    # ------------------------------------------------------------------
    def built_in_keys(self) -> set[str]:
        """Return the immutable set of built-in system binding keys."""

        return {binding.key for binding in self._system_keys}

    # ------------------------------------------------------------------
    def add_custom_binding(self, *, key: str, label: str, description: str | None = None) -> SystemBinding:
        """Persist a user-defined binding and return the stored descriptor."""

        key = key.strip()
        label = label.strip()
        description = description.strip() if description else None

        if not key or not label:
            raise ValueError("Both key and label are required for custom bindings.")

        if key in self.built_in_keys():
            raise ValueError("The specified key matches a built-in binding and cannot be overridden.")

        binding = SystemBinding(key=key, label=label, description=description)

        for index, existing in enumerate(self._custom_keys):
            if existing.key == key:
                self._custom_keys[index] = binding
                break
        else:
            self._custom_keys.append(binding)

        self._save_custom_bindings()
        return binding

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

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load_custom_bindings(self) -> None:
        if self._custom_bindings_path is None:
            return
        path = self._custom_bindings_path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(payload, list):
            return
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key", "")).strip()
            label = str(entry.get("label", "")).strip()
            description = entry.get("description")
            if not key or not label:
                continue
            if key in self.built_in_keys():
                # Built-in keys take precedence; skip invalid overrides silently.
                continue
            if description is not None:
                description = str(description)
            self._custom_keys.append(SystemBinding(key=key, label=label, description=description))

    def _save_custom_bindings(self) -> None:
        if self._custom_bindings_path is None:
            return
        path = self._custom_bindings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "key": binding.key,
                "label": binding.label,
                "description": binding.description,
            }
            for binding in self._custom_keys
        ]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# Convenience singleton for modules that prefer a simple functional interface.
_default_binder = Binder()


def resolve(context: Mapping[str, Any], dotted_key: str) -> Any:
    """Resolve a dotted key using the default binder instance."""

    return _default_binder.resolve(context, dotted_key)
