from textwrap import dedent


def global_qss(tokens: dict) -> str:
    menu_bar_bg = tokens.get("menu_bar_bg", tokens.get("bg_panel"))
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
        QWidget#MenuBarCorner {{
            background: {menu_bar_bg};
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
            background: {tokens.get('btn_pressed', tokens['btn_hover'])};
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
            background: {tokens['btn_focus']};
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
            border-bottom: 2px solid {tokens['ctrl_focus']};
        }}
        QTabBar::tab:hover {{
            background: {tokens['ctrl_hover']};
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
        QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox {{
            background: {tokens['ctrl_bg']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
            border-radius: 3px;
            padding: 2px 4px;
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QAbstractSpinBox:focus {{
            border: 1px solid {tokens['ctrl_focus']};
        }}
        QLineEdit:read-only {{
            background: {tokens['bg_raised']};
            color: {tokens['fg_muted']};
        }}
        QComboBox {{
            background: {tokens['ctrl_bg']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
            border-radius: 3px;
            padding: 2px 4px;
        }}
        QComboBox:focus {{
            border: 1px solid {tokens['ctrl_focus']};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            selection-background-color: {tokens['bg_raised']};
            selection-color: {tokens['fg_primary']};
        }}
        QLabel {{
            color: {tokens['fg_primary']};
            background: transparent;
        }}
        QGroupBox {{
            color: {tokens['fg_primary']};
        }}
        QCheckBox, QRadioButton {{
            color: {tokens['fg_primary']};
            background: transparent;
        }}
        QAbstractItemView {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            alternate-background-color: {tokens['bg_raised']};
            selection-background-color: {tokens['ctrl_hover']};
            selection-color: {tokens['fg_primary']};
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

        /* Qt Advanced Docking System — ads:: namespace -> ads-- prefix in QSS */
        ads--CDockAreaTitleBar {{
            background: {tokens['dock_tab_bg']};
            background-image: none;
            padding: 0px;
            border-bottom: 1px solid {tokens['divider']};
        }}
        ads--CDockAreaTabBar {{
            background: transparent;
            background-image: none;
        }}
        ads--CDockWidgetTab {{
            background: {tokens['bg_panel']};
            background-image: none;
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['divider']};
            border-bottom: none;
            border-radius: 2px 2px 0px 0px;
            padding: 4px 10px;
            margin-right: 2px;
        }}
        ads--CDockWidgetTab:hover {{
            background: {tokens['ctrl_hover']};
            background-image: none;
        }}
        ads--CDockWidgetTab[activeTab="true"] {{
            background: {tokens['bg_raised']};
            background-image: none;
            color: {tokens['fg_primary']};
            border-color: {tokens['ctrl_border']};
        }}
        ads--CDockAreaWidget {{
            background: {tokens['bg_panel']};
            background-image: none;
        }}
        ads--CFloatingDockContainer {{
            background: {tokens['bg_window']};
            background-image: none;
            border: 1px solid {tokens['ctrl_border']};
        }}
    """)


def ads_qss(tokens: dict) -> str:
    """ADS-only rules applied directly on the CDockManager widget."""
    return dedent(f"""
        ads--CDockAreaTitleBar {{
            background: {tokens['dock_tab_bg']};
            background-image: none;
            padding: 0px;
            border-bottom: 1px solid {tokens['divider']};
        }}
        ads--CDockAreaTabBar {{
            background: transparent;
            background-image: none;
        }}
        ads--CDockWidgetTab {{
            background: {tokens['bg_panel']};
            background-image: none;
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['divider']};
            border-bottom: none;
            border-radius: 2px 2px 0px 0px;
            padding: 4px 10px;
            margin-right: 2px;
        }}
        ads--CDockWidgetTab:hover {{
            background: {tokens['ctrl_hover']};
            background-image: none;
        }}
        ads--CDockWidgetTab[activeTab="true"] {{
            background: {tokens['bg_raised']};
            background-image: none;
            color: {tokens['fg_primary']};
            border-color: {tokens['ctrl_border']};
        }}
        ads--CDockAreaWidget {{
            background: {tokens['bg_panel']};
            background-image: none;
        }}
        ads--CFloatingDockContainer {{
            background: {tokens['bg_window']};
            background-image: none;
            border: 1px solid {tokens['ctrl_border']};
        }}
    """)
