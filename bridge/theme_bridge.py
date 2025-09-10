from PySide6.QtCore import QObject, Signal, Slot, Property


class ThemeBridge(QObject):
    tokensChanged = Signal(object)  # emits dict of current tokens

    def __init__(self, initial_tokens: dict):
        super().__init__()
        self._tokens = dict(initial_tokens)

    def getTokens(self):
        return self._tokens

    @Property("QVariantMap", notify=tokensChanged)
    def tokens(self):
        return self._tokens

    @Slot(dict)
    def updateTokens(self, tokens: dict):
        self._tokens = dict(tokens)
        self.tokensChanged.emit(self._tokens)

