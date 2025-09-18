"""Dotted-key binding resolver used by the form services."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable


class Binder:
    """Resolve dotted keys (``foo.bar``) against a context mapping.

    The binder is intentionally light-weight.  It exposes a plug-in style
    registry where callables can be registered for specific keys.  When a
    key is not explicitly registered, the binder walks the supplied
    context treating dictionaries, dataclasses and regular objects in a
    uniform way.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable[[dict[str, Any]], Any]] = {}

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def register(self, key: str, resolver: Callable[[dict[str, Any]], Any]) -> None:
        """Register a callable resolver for a specific dotted key."""

        self._registry[key] = resolver

    def available_keys(self) -> list[str]:
        """Return the list of keys that have explicit resolvers."""

        return sorted(self._registry)

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------
    def resolve(self, context: dict[str, Any], key: str, *, default: Any | None = None) -> Any:
        """Resolve ``key`` using the provided ``context``.

        Parameters
        ----------
        context:
            Arbitrary dictionary-like object containing incident and user
            supplied data.
        key:
            Dotted key expression, for example ``"incident.ic_name"`` or
            ``"planning.branches.ops"``.
        default:
            Value returned when the key cannot be resolved.
        """

        key = key.strip()
        if not key:
            return default

        if key in self._registry:
            try:
                return self._registry[key](context)
            except Exception:  # pragma: no cover - defensive; logged elsewhere
                return default

        current: Any = context
        for part in key.split("."):
            if current is None:
                return default
            current = _resolve_single(current, part)
            if current is _MISSING:
                return default
        return current


class _Missing:
    pass


_MISSING = _Missing()


def _resolve_single(data: Any, key: str) -> Any:
    """Resolve a single level of indirection."""

    if isinstance(data, dict):
        return data.get(key, _MISSING)
    if is_dataclass(data):
        return asdict(data).get(key, _MISSING)
    if hasattr(data, key):
        return getattr(data, key)
    if isinstance(data, (list, tuple)):
        try:
            index = int(key)
        except ValueError:
            return _MISSING
        if 0 <= index < len(data):
            return data[index]
        return _MISSING
    return _MISSING


# Singleton binder used across the module.
GLOBAL_BINDER = Binder()

