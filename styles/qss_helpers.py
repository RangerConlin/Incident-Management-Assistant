from textwrap import dedent


def _rgba(hex_color: str, alpha: float) -> str:
    """Return an rgba() string from a hex color like #RRGGBB with given alpha.

    Falls back to a sensible blue if the input is malformed. Alpha is clamped
    into [0,1].
    """
    try:
        value = (hex_color or "").lstrip("#")
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
    except Exception:
        r, g, b = 47, 128, 237  # #2F80ED fallback
    a = max(0.0, min(1.0, float(alpha)))
    return f"rgba({r}, {g}, {b}, {a:.3f})"


def global_qss(tokens: dict) -> str:
    menu_bar_bg = tokens.get("menu_bar_bg", tokens.get("bg_panel"))
    # Selection: outline-only so row color remains fully visible.
    accent = tokens.get("accent", "#2F80ED")
    focus = tokens.get("ctrl_focus", accent)
    selection_overlay = "transparent"
    selection_border = focus
    return dedent(f"""
        QMainWindow {{
            background: {tokens['bg_window']};
            color: {tokens['fg_primary']};
        }}
        QMenuBar {{
            background: {menu_bar_bg};
            color: {tokens['fg_primary']};
            border-bottom: 1px solid {tokens['divider']};
        }}
        QMenuBar::item {{
            background: transparent;
            color: {tokens['fg_primary']};
            padding: 4px 8px;
        }}
        QMenuBar::item:selected {{
            background: {tokens['bg_raised']};
            color: {tokens['fg_primary']};
        }}
        QMenu {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
        }}
        QMenu::item {{
            background: transparent;
            color: {tokens['fg_primary']};
            padding: 4px 24px;
        }}
        QMenu::item:selected {{
            background: {tokens['bg_raised']};
            color: {tokens['fg_primary']};
        }}
        QDockWidget {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['divider']};
        }}
        QDockWidget::title {{
            background: {tokens['dock_tab_bg']};
            color: {tokens['fg_primary']};
            padding: 4px 8px;
        }}
        QPushButton,
        QToolButton,
        QCommandLinkButton {{
            background: {tokens['btn_bg']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
            border-radius: 4px;
            padding: 4px 12px;
        }}
        QPushButton:hover,
        QToolButton:hover,
        QCommandLinkButton:hover {{
            background: {tokens['btn_hover']};
        }}
        QPushButton:pressed,
        QToolButton:pressed,
        QCommandLinkButton:pressed {{
            background: {tokens['btn_pressed']};
        }}
        QPushButton:checked,
        QToolButton:checked,
        QCommandLinkButton:checked {{
            background: {tokens['btn_checked']};
            border-color: {tokens['ctrl_focus']};
        }}
        QPushButton:focus,
        QToolButton:focus,
        QCommandLinkButton:focus {{
            baqckground: {tokens['btn_focus']};
            border: 1px solid {tokens['ctrl_focus']};
        }}
        QPushButton:disabled,
        QToolButton:disabled,
        QCommandLinkButton:disabled {{
            background: {tokens['btn_disabled']};
            color: {tokens['fg_muted']};
            border-color: {tokens['divider']};
        }}
        QTabWidget::pane {{
            background: {tokens['bg_panel']};
            border: 1px solid {tokens['divider']};
            padding: 6px;
        }}
        QTabBar::tab {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['divider']};
            border-bottom: none;
            padding: 6px 12px;
            margin-right: 4px;
        }}
        QTabBar::tab:selected {{
            background: {tokens['bg_raised']};
            color: {tokens['fg_primary']};
            margin-top: 0px;
        }}
        QTabBar::tab:hover {{
            background: {tokens['ctrl_hover']};
        }}
        QTabBar::tab:!selected {{
            margin-top: 2px;
        }}

        QToolTip {{
            background: {tokens['bg_raised']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
        }}
        QHeaderView {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            border: none;
        }}
        QHeaderView::section {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            border: 0px;
            padding: 4px 6px;
            border-bottom: 1px solid {tokens['divider']};
        }}
        QHeaderView::section:horizontal {{
            border-bottom: 1px solid {tokens['divider']};
            border-right: 1px solid {tokens['divider']};
        }}
        QHeaderView::section:vertical {{
            border-right: 1px solid {tokens['divider']};
        }}
        QTableCornerButton::section {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            border: 0px;
            border-right: 1px solid {tokens['divider']};
            border-bottom: 1px solid {tokens['divider']};
        }}
        /* Make item-view selection background transparent globally */
        QTableView, QTreeView, QListView {{
            selection-background-color: transparent;
            selection-color: {tokens['fg_primary']};
        }}
        /*
         * Selection styling for tables/lists/trees:
         * - Transparent fill (no overlay), use a high-contrast border only.
         */
        QTableView::item:selected,
        QTreeView::item:selected,
        QListView::item:selected {{
            background: transparent;
            border: 2px solid {selection_border};
            border-radius: 3px;
        }}
        QTableView::item:selected:!active,
        QTreeView::item:selected:!active,
        QListView::item:selected:!active {{
            background: transparent;
            border: 2px solid {selection_border};
        }}
        QScrollBar:vertical {{
            background: {tokens['bg_panel']};
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background: {tokens['ctrl_border']};
            min-height: 25px;
            border-radius: 4px;
        }}
    """)
