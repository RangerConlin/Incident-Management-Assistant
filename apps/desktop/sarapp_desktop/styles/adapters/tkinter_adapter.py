"""Tkinter/ttk theme adapter using :mod:`styles.styles` palettes."""
from __future__ import annotations

try:  # optional dependency
    import tkinter as tk
    from tkinter import ttk
except Exception:  # pragma: no cover - when Tkinter not available
    tk = None  # type: ignore
    ttk = None  # type: ignore

from typing import Dict, Set

from . import qcolor_to_hex, qbrush_to_hex, ensure_contrast
from styles import styles as core

_STYLE: ttk.Style | None = None
_TREEVIEWS: Set[ttk.Treeview] = set()


def _apply_style() -> None:
    """Configure ttk styles from the current palette."""
    if ttk is None:
        return
    global _STYLE
    p = core.get_palette()
    fg = qcolor_to_hex(p['fg'])
    bg = qcolor_to_hex(p['bg'])
    accent = qcolor_to_hex(p['accent'])
    muted = qcolor_to_hex(p['muted'])
    if _STYLE is None:
        _STYLE = ttk.Style()
        try:
            _STYLE.theme_create('sarapp', parent='clam')
        except Exception:
            pass
    _STYLE.theme_use('sarapp')
    _STYLE.configure('TButton', foreground=fg, background=accent, padding=6)
    _STYLE.map('TButton', background=[('active', accent)], foreground=[('disabled', muted)])
    _STYLE.configure('TEntry', foreground=fg, fieldbackground=bg, bordercolor=accent)
    _STYLE.configure('TNotebook.Tab', padding=[6, 4], foreground=fg)
    _STYLE.map('TNotebook.Tab', foreground=[('selected', fg)], background=[('selected', bg)])
    _STYLE.configure('Treeview', background=bg, fieldbackground=bg, foreground=fg)
    alt = qcolor_to_hex(core.get_palette()['muted'])
    _STYLE.map('Treeview', background=[('alternate', alt)])
    for tree in list(_TREEVIEWS):
        _configure_tree_tags(tree)


def _configure_tree_tags(tree: ttk.Treeview) -> None:
    if ttk is None:
        return
    p = core.get_palette()
    base_fg = qcolor_to_hex(p['fg'])
    for k, v in core.team_status_colors().items():
        bg = qbrush_to_hex(v['bg'])
        fg = ensure_contrast(qbrush_to_hex(v['fg']), bg, base_fg)
        tree.tag_configure(f'TEAM_{k.replace(" ", "_").upper()}', background=bg, foreground=fg)
    for k, v in core.task_status_colors().items():
        bg = qbrush_to_hex(v['bg'])
        fg = ensure_contrast(qbrush_to_hex(v['fg']), bg, base_fg)
        tree.tag_configure(f'TASK_{k.replace(" ", "_").upper()}', background=bg, foreground=fg)


def apply_theme(root, mode: str = 'light') -> None:
    """Apply theme to a Tk root window."""
    if tk is None:
        raise ImportError('Tkinter is required for apply_theme')
    core.set_theme(mode)
    _apply_style()
    core.style_bus.THEME_CHANGED.connect(lambda m: _apply_style())


def set_mode(mode: str) -> None:
    """Switch theme mode."""
    core.set_theme(mode)
    _apply_style()


def apply_treeview_status(tree: ttk.Treeview, item_id: str, kind: str, key: str) -> None:
    """Apply a status tag to a Treeview row."""
    if ttk is None:
        raise ImportError('Tkinter is required for apply_treeview_status')
    _TREEVIEWS.add(tree)
    _configure_tree_tags(tree)
    tag = f'{kind.upper()}_{key.replace(" ", "_").upper()}'
    tree.item(item_id, tags=(tag,))


__all__ = ['apply_theme', 'set_mode', 'apply_treeview_status']
