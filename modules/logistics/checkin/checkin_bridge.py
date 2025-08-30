"""Qt bridge exposing the check-in API to QML."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot, QByteArray

from . import api


class CheckInBridge(QObject):
    """QObject bridge used by QML to interact with the Python backend."""

    lookupResults = Signal(list)
    checkInResult = Signal(dict)
    toast = Signal(str)

    @Slot(str, str, str)
    def lookup(self, entityType: str, mode: str, value: str) -> None:
        try:
            if mode == "id":
                results = api.lookup_entity(entityType, mode, value=value)
            elif entityType == "personnel" and mode == "name":
                first, last = value.split(" ", 1)
                results = api.lookup_entity(entityType, mode, first=first, last=last)
            else:
                results = api.lookup_entity(entityType, mode, value=value)
            self.lookupResults.emit(results)
        except Exception as exc:  # pragma: no cover - defensive
            self.toast.emit(str(exc))

    @Slot(str, str)
    def checkInById(self, entityType: str, idValue: str) -> None:
        try:
            result = api.check_in_entity(entityType, {"mode": "id", "value": idValue})
            self.checkInResult.emit(result)
            if result.get("success"):
                self.toast.emit("Checked In")
        except Exception as exc:  # pragma: no cover
            self.toast.emit(str(exc))

    @Slot(str, dict)
    def createNew(self, entityType: str, payload: dict) -> None:
        try:
            result = api.create_master_plus_incident(entityType, payload)
            self.checkInResult.emit(result)
            self.toast.emit("Created")
        except Exception as exc:  # pragma: no cover
            self.toast.emit(str(exc))
