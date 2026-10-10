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
        QToolBar#ModuleRail {{
            background: {tokens['bg_panel']};
            border: none;
            border-right: 1px solid {tokens['divider']};
            spacing: 4px;
            padding: 8px 8px;
        }}
        QToolButton#ModuleRailButton {{
            background: transparent;
            color: {tokens['fg_muted']};
            border: none;
            border-left: 2px solid transparent;
            border-radius: 6px;
            font-weight: 700;
            font-size: 10px;
        }}
        QToolButton#ModuleRailButton:hover {{
            background: {tokens['ctrl_hover']};
            color: {tokens['fg_primary']};
        }}
        QToolButton#ModuleRailButton:checked {{
            background: {tokens['bg_raised']};
            color: {tokens['ctrl_focus']};
            border-left: 2px solid {tokens['ctrl_focus']};
        }}
        QFrame#KpiTile {{
            background: {tokens['bg_panel']};
            border: 1px solid {tokens['divider']};
            border-left: 3px solid {tokens['ctrl_border']};
            border-radius: 6px;
        }}
        QLabel#KpiValue {{
            color: {tokens['fg_primary']};
            font-size: 18px;
            font-weight: 700;
        }}
        QLabel#KpiCaption {{
            color: {tokens['fg_muted']};
            font-size: 10.5px;
        }}
        QToolButton#StatusChip {{
            background: transparent;
            color: {tokens['fg_muted']};
            border: 1px solid {tokens['divider']};
            border-radius: 12px;
            padding: 3px 12px;
            font-size: 11.5px;
            font-weight: 600;
        }}
        QToolButton#StatusChip:hover {{
            background: {tokens['ctrl_hover']};
        }}
        QToolButton#StatusChip:checked {{
            background: {tokens['bg_raised']};
            color: {tokens['ctrl_focus']};
            border: 1px solid {tokens['ctrl_focus']};
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
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 22px;
            border-left: 1px solid {tokens['ctrl_border']};
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
        }}
        QComboBox::down-arrow {{
            image: none;
            width: 0px;
            height: 0px;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {tokens['fg_muted']};
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
            border: 1px solid {tokens['divider']};
            border-radius: 6px;
            margin-top: 14px;
            padding: 10px 8px 8px 8px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 8px;
            top: -2px;
            padding: 0px 4px;
            background: transparent;
            color: {tokens['fg_primary']};
        }}
        QCheckBox, QRadioButton {{
            color: {tokens['fg_primary']};
            background: transparent;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 14px;
            height: 14px;
            background: {tokens['ctrl_bg']};
            border: 1px solid {tokens['ctrl_border']};
        }}
        QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
            border: 1px solid {tokens['ctrl_focus']};
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background: {tokens['ctrl_focus']};
            border: 1px solid {tokens['ctrl_focus']};
        }}
        QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
            background: {tokens['bg_raised']};
            border: 1px solid {tokens['divider']};
        }}
        QRadioButton::indicator {{
            border-radius: 7px;
        }}
        QAbstractItemView {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            alternate-background-color: {tokens['bg_raised']};
            selection-background-color: {tokens['ctrl_hover']};
            selection-color: {tokens['fg_primary']};
            outline: none;
        }}
        QAbstractItemView::item {{
            padding: 2px 6px;
            border: none;
        }}
        QTreeView::branch {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: {tokens['bg_panel']};
            width: 12px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {tokens['ctrl_border']};
            min-height: 25px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {tokens['ctrl_hover']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
            background: transparent;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            background: {tokens['bg_panel']};
            height: 12px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {tokens['ctrl_border']};
            min-width: 25px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {tokens['ctrl_hover']};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
            background: transparent;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}
        QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit, QTimeEdit {{
            background: {tokens['ctrl_bg']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
            border-radius: 3px;
            padding: 2px 4px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QDateTimeEdit:focus, QTimeEdit:focus {{
            border: 1px solid {tokens['ctrl_focus']};
        }}
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QDateEdit::up-button, QDateTimeEdit::up-button, QTimeEdit::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 16px;
            border-left: 1px solid {tokens['ctrl_border']};
            background: {tokens['btn_bg']};
        }}
        QSpinBox::down-button, QDoubleSpinBox::down-button,
        QDateEdit::down-button, QDateTimeEdit::down-button, QTimeEdit::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 16px;
            border-left: 1px solid {tokens['ctrl_border']};
            border-top: 1px solid {tokens['ctrl_border']};
            background: {tokens['btn_bg']};
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover,
        QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
        QDateEdit::up-button:hover, QDateEdit::down-button:hover,
        QDateTimeEdit::up-button:hover, QDateTimeEdit::down-button:hover,
        QTimeEdit::up-button:hover, QTimeEdit::down-button:hover {{
            background: {tokens['btn_hover']};
        }}
        QCalendarWidget QWidget {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_primary']};
            alternate-background-color: {tokens['bg_raised']};
        }}
        QCalendarWidget QToolButton {{
            background: transparent;
            color: {tokens['fg_primary']};
        }}
        QCalendarWidget QAbstractItemView:enabled {{
            selection-background-color: {tokens['ctrl_focus']};
            selection-color: {tokens['fg_primary']};
        }}
        QSplitter::handle {{
            background: {tokens['divider']};
        }}
        QSplitter::handle:hover {{
            background: {tokens['ctrl_focus']};
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}
        QProgressBar {{
            background: {tokens['ctrl_bg']};
            color: {tokens['fg_primary']};
            border: 1px solid {tokens['ctrl_border']};
            border-radius: 4px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background: {tokens['ctrl_focus']};
            border-radius: 3px;
        }}
        QSlider::groove:horizontal {{
            background: {tokens['ctrl_border']};
            height: 4px;
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {tokens['ctrl_focus']};
            width: 14px;
            margin: -6px 0;
            border-radius: 7px;
        }}
        QStatusBar {{
            background: {tokens['bg_panel']};
            color: {tokens['fg_muted']};
            border-top: 1px solid {tokens['divider']};
        }}
        QStatusBar::item {{
            border: none;
        }}
        QToolBar {{
            background: {tokens['bg_panel']};
            border: none;
            spacing: 4px;
            padding: 2px;
        }}
        QToolBar::separator {{
            background: {tokens['divider']};
            width: 1px;
            margin: 4px 2px;
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
