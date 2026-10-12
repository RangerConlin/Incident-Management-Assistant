"""NiceGUI theme adapter deriving colors from :mod:`styles.styles`."""
from __future__ import annotations

try:  # optional dependency
    from nicegui import ui
except Exception:  # pragma: no cover - when NiceGUI not installed
    ui = None  # type: ignore

from . import qcolor_to_hex, qbrush_to_hex, ensure_contrast
from styles import styles as core


def _palette_css(p: dict[str, object]) -> str:
    """Return CSS variables for the palette."""
    bg = qcolor_to_hex(p['bg'])
    fg = qcolor_to_hex(p['fg'])
    muted = qcolor_to_hex(p['muted'])
    accent = qcolor_to_hex(p['accent'])
    border = "color-mix(in oklab, var(--text), transparent 85%)"
    return (
        f"--bg:{bg};--surface:{bg};--text:{fg};--muted:{muted};--accent:{accent};"
        f"--border:{border};"
    )


def _status_css(p: dict[str, object]) -> str:
    base_fg = qcolor_to_hex(p['fg'])
    rules = []
    for kind, mapping in (
        ('team', core.team_status_colors()),
        ('task', core.task_status_colors()),
    ):
        for key, colors in mapping.items():
            bg = qbrush_to_hex(colors['bg'])
            fg = ensure_contrast(qbrush_to_hex(colors['fg']), bg, base_fg)
            cls = f"status-{kind}-{key.replace(' ', '_').upper()}"
            rules.append(f".{cls}{{background:{bg};color:{fg};border:1px solid var(--border);}}")
    return "\n".join(rules)


def _apply_theme(mode: str) -> None:
    if ui is None:
        return
    p = core.get_palette()
    ui.colors(
        primary=qcolor_to_hex(p['accent']),
        secondary=qcolor_to_hex(p['muted']),
        accent=qcolor_to_hex(p['accent']),
        info=qcolor_to_hex(p['accent']),
        warning=qcolor_to_hex(p['warning']),
        positive=qcolor_to_hex(p['success']),
        negative=qcolor_to_hex(p['error']),
    )
    light = _palette_css(core._LIGHT_PALETTE)  # type: ignore[attr-defined]
    dark = _palette_css(core._DARK_PALETTE)  # type: ignore[attr-defined]
    css = (
        f":root{{{light}}}\n"
        f".dark{{{dark}}}\n"
        f".ui-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;}}\n"
        f".ui-btn.primary{{background:var(--accent);color:white;border-radius:8px;}}\n"
        f"{_status_css(p)}"
    )
    ui.add_css(css)


def init_theme(mode: str = 'light') -> None:
    """Initialise NiceGUI with the given mode."""
    if ui is None:
        raise ImportError('NiceGUI is required for init_theme')
    core.set_theme(mode)
    _apply_theme(mode)
    core.style_bus.THEME_CHANGED.connect(lambda m: (_apply_theme(m),
                                                   ui.dark_mode().enable() if m == 'dark' else ui.dark_mode().disable()))


def set_mode(mode: str) -> None:
    """Switch theme mode."""
    if ui is None:
        raise ImportError('NiceGUI is required for set_mode')
    ui.dark_mode().enable() if mode == 'dark' else ui.dark_mode().disable()
    core.set_theme(mode)


def status_css_class(kind: str, key: str) -> str:
    """Return the CSS class for a status token."""
    return f"status-{kind}-{key.replace(' ', '_').upper()}"


__all__ = ['init_theme', 'set_mode', 'status_css_class']
