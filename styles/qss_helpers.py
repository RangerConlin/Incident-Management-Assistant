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
        QPushButton,
        QToolButton,
        QCommandLinkButton {{
            background: {tokens['ctrl_bg']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
            border-radius: 4px;
            padding: 4px 12px;
        }}
        QPushButton:hover,
        QToolButton:hover,
        QCommandLinkButton:hover {{
            background: {tokens['ctrl_hover']};
        }}
        QPushButton:pressed,
        QToolButton:pressed,
        QCommandLinkButton:pressed {{
            background: {tokens['bg_raised']};
        }}
        QPushButton:checked,
        QToolButton:checked,
        QCommandLinkButton:checked {{
            background: {tokens['bg_raised']};
            border-color: {tokens['ctrl_focus']};
        }}
        QPushButton:focus,
        QToolButton:focus,
        QCommandLinkButton:focus {{
            border: 1px solid {tokens['ctrl_focus']};
        }}
        QPushButton:disabled,
        QToolButton:disabled,
        QCommandLinkButton:disabled {{
            background: {tokens['bg_panel']};
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

