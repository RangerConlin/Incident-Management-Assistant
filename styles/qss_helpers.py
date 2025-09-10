from textwrap import dedent


def global_qss(tokens: dict) -> str:
    return dedent(f"""
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

