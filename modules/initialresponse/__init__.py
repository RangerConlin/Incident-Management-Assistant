try:  # pragma: no cover - exercised when PySide6 is available
    from . import windows as initial
    from .windows import get_hasty_panel, get_reflex_panel
except Exception:  # pragma: no cover - headless test fallback
    initial = None  # type: ignore

    def get_hasty_panel(*_args, **_kwargs):  # type: ignore[override]
        raise RuntimeError("Initial response UI requires PySide6")

    def get_reflex_panel(*_args, **_kwargs):  # type: ignore[override]
        raise RuntimeError("Initial response UI requires PySide6")

__all__ = ["initial", "get_hasty_panel", "get_reflex_panel"]
