"""Qt bridge exposing the check-in API to QML."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot, QByteArray
from PySide6.QtQml import QJSValue

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

    @Slot(str, str, str, 'QJSValue')
    def searchEntity(self, entityType: str, term: str, status: str, callback: QJSValue) -> None:
        """Search entities and invoke a QML callback with results."""
        try:
            results = api.search_entities(entityType, term, status)
            if isinstance(callback, QJSValue) and callback.isCallable():
                callback.call([results])
        except Exception as exc:  # pragma: no cover
            self.toast.emit(str(exc))

    @Slot(str, str, 'QJSValue')
    def getDetails(self, entityType: str, entityId: str, callback: QJSValue) -> None:
        """Fetch detailed info for an entity."""
        try:
            details = api.get_entity_details(entityType, entityId)
            if isinstance(callback, QJSValue) and callback.isCallable():
                callback.call([details])
        except Exception as exc:  # pragma: no cover
            self.toast.emit(str(exc))

    @Slot(dict, 'QJSValue')
    def checkInEntity(self, payload: dict, callback: QJSValue) -> None:
        """Perform a check-in operation for an entity."""
        ok = False
        message = ""
        try:
            entity_type = payload.get("entityType")
            entity_id = payload.get("id")
            result = api.check_in_entity(entity_type, {"mode": "id", "value": entity_id})
            if result.get("success"):
                status = (
                    payload.get("personnelStatus")
                    if entity_type == "personnel"
                    else payload.get("checkinStatus")
                )
                if status:
                    api.update_incident_status(entity_type, entity_id, status)
                ok = True
                message = "Check-in saved"
            else:
                ok = False
                message = result.get("message", "Failed to save check-in")
        except Exception as exc:  # pragma: no cover
            ok = False
            message = str(exc)
        if isinstance(callback, QJSValue) and callback.isCallable():
            callback.call([ok, message])
        self.toast.emit(message)

    @Slot(str, dict)
    def createNew(self, entityType: str, payload: dict) -> None:
        try:
            result = api.create_master_plus_incident(entityType, payload)
            self.checkInResult.emit(result)
            self.toast.emit("Created")
        except Exception as exc:  # pragma: no cover
            self.toast.emit(str(exc))
