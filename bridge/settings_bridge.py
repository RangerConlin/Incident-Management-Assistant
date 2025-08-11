from PySide6.QtCore import QObject, Slot, QVariant

class QmlSettingsBridge(QObject):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    @Slot(str, result="QVariant")
    def getSetting(self, key):
        return self.manager.get(key)

    @Slot(str, "QVariant")
    def setSetting(self, key, value):
        self.manager.set(key, value)
