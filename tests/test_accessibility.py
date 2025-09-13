import pytest

from styles import styles as core
from styles.adapters import qcolor_to_hex, qbrush_to_hex, contrast_ratio, ensure_contrast


def test_palette_contrast():
    for mode in ['light', 'dark']:
        core.set_theme(mode)
        p = core.get_palette()
        fg = qcolor_to_hex(p['fg'])
        bg = qcolor_to_hex(p['bg'])
        assert contrast_ratio(fg, bg) >= 4.5


def test_status_contrast():
    for mode in ['light', 'dark']:
        core.set_theme(mode)
        p = core.get_palette()
        base_fg = qcolor_to_hex(p['fg'])
        for colors in list(core.team_status_colors().values()) + list(core.task_status_colors().values()):
            bg = qbrush_to_hex(colors['bg'])
            fg = qbrush_to_hex(colors['fg'])
            if contrast_ratio(fg, bg) < 4.5:
                fg = ensure_contrast(fg, bg, base_fg)
            assert contrast_ratio(fg, bg) >= 4.5
