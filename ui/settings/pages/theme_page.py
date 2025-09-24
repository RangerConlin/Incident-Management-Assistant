"""Theme and appearance settings page."""

from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from ..binding import bind_combobox


class ThemePage(QWidget):
    """Visual customization options."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        theme = QComboBox()
        theme.addItems(["System Default", "Dark", "Light", "Custom"])
        bind_combobox(theme, bridge, "themeIndex", 0)
        layout.addRow("Theme:", theme)

        font_size = QComboBox()
        font_size.addItems(["Small", "Medium", "Large"])
        bind_combobox(font_size, bridge, "fontSizeIndex", 1)
        layout.addRow("Font Size:", font_size)

        color_profile = QComboBox()
        color_profile.addItems(["Standard SAR", "High Contrast", "Colorblind Safe"])
        bind_combobox(color_profile, bridge, "colorProfileIndex", 0)
        layout.addRow("Color Profile:", color_profile)

        ui_template = QComboBox()
        ui_template.addItems(["Default", "Compact", "Wide", "Operator View"])
        bind_combobox(ui_template, bridge, "uiTemplateIndex", 0)
        layout.addRow("UI Template:", ui_template)
