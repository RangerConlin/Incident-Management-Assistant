from textwrap import dedent


def global_qss(tokens: dict) -> str:
    return dedent(f"""
        QMainWindow {{
            background: {tokens['bg_window']};
            color: {tokens['fg_primary']};
        }}
        QMenuBar {{
            background: {tokens['bg_panel']};
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
            background: {tokens['bg_raised']};
            color: {tokens['fg_primary']};
            padding: 4px 8px;
        }}
        QToolTip {{
            background: {tokens['bg_raised']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
        }}
        QHeaderView::section {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            border: 0px;
            border-bottom: 1px solid {tokens['divider']};
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

