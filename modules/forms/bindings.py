from __future__ import annotations

from typing import Any, Dict

from utils.profile_manager import profile_manager


def _get_by_path(data: Dict[str, Any] | None, path: str | None) -> Any:
    if not data or not path:
        return None
    cur: Any = data
    for part in str(path).split('.'):
        if isinstance(cur, list):
            try:
                idx = int(part)
            except Exception:
                return None
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        elif isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur.get(part)
        else:
            return None
    return cur


def _call_computed(func, context: Dict[str, Any]) -> Any:
    try:
        # Prefer call with context; fall back to no-arg
        return func(context)
    except TypeError:
        try:
            return func()
        except Exception:
            return None
    except Exception:
        return None


def render_values(template: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Resolve field values for a v2 template using bindings.

    Context buckets:
      - constants: catalog data from active profile (default loaded)
      - mission: caller supplied incident/mission data
      - personnel, env: caller supplied; optional
      - computed: functions discovered via active profile; key -> callable
    """

    ctx: Dict[str, Any] = dict(context or {})
    # Seed defaults from active profile when not provided
    ctx.setdefault("constants", profile_manager.get_catalog())
    ctx.setdefault("computed", profile_manager.get_computed())

    out: Dict[str, Any] = {}
    for field in template.get("fields", []) or []:
        binding = field.get("binding") or {}
        source = binding.get("source")
        bkey = binding.get("key")

        key_name = field.get("key") or field.get("name") or bkey or ""
        if not key_name:
            continue

        val: Any = None
        if source == "constants":
            val = _get_by_path(ctx.get("constants"), bkey)
        elif source == "mission":
            val = _get_by_path(ctx.get("mission"), bkey)
        elif source == "personnel":
            val = _get_by_path(ctx.get("personnel"), bkey)
        elif source == "env":
            val = _get_by_path(ctx.get("env"), bkey)
        elif source == "computed":
            comp = (ctx.get("computed") or {}).get(bkey)
            if callable(comp):
                val = _call_computed(comp, ctx)
        else:
            # Unknown or None source: leave as default
            val = field.get("default")

        out[key_name] = val

    return out


__all__ = ["render_values"]

