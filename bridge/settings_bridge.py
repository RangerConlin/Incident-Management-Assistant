from PySide6.QtCore import QObject, Slot, Signal

class QmlSettingsBridge(QObject):
    settingChanged = Signal(str, object)  # key, value

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    @Slot(str, result=object)  # use object instead of QVariant
    def getSetting(self, key):
        return self.manager.get(key)

    @Slot(str, object)  # use object instead of QVariant
    def setSetting(self, key, value):
        self.manager.set(key, value)
        self.settingChanged.emit(key, value)
