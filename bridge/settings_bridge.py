from PySide6.QtCore import QObject, Slot, Signal

class QmlSettingsBridge(QObject):
    settingChanged = Signal(str, 'QVariant')  # key, value

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    @Slot(str, result='QVariant')
    def getSetting(self, key):
        # Return a QVariant-compatible type for QML
        return self.manager.get(key)

    @Slot(str, 'QVariant')
    def setSetting(self, key, value):
        self.manager.set(key, value)
        self.settingChanged.emit(key, value)
