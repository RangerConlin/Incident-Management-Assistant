"""Qt panel exposing ICS 206 Medical Plan functionality to QML."""
from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import QObject, Signal, Slot

from bridge.medical_bridge import MedicalBridge


class ICS206Panel(QObject):
    """Controller object registered to QML as ``ics206Bridge``."""

    aidStationsLoaded = Signal(list)
    ambulanceLoaded = Signal(list)
    hospitalsLoaded = Signal(list)
    airAmbulanceLoaded = Signal(list)
    commsLoaded = Signal(list)
    proceduresLoaded = Signal(str)
    signaturesLoaded = Signal(dict)
    pdfRequested = Signal()
    toast = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.bridge = MedicalBridge()
        self.bridge.data_changed.connect(self._handle_data_change)
        self.bridge.toast.connect(self.toast)
        # Ensure DB schema exists immediately
        try:
            self.bridge.ensure_ics206_tables()
        except Exception as exc:  # pragma: no cover - best effort on init
            self.toast.emit(str(exc))

    # ------------------------------------------------------------------
    # Internal helpers
    def _handle_data_change(self, table: str) -> None:
        loader_map = {
            "aid_stations": self.load_aid_stations,
            "ambulance_services": self.load_ambulance_services,
            "hospitals": self.load_hospitals,
            "air_ambulance": self.load_air_ambulance,
            "medical_comms": self.load_medical_comms,
            "procedures": lambda: self.proceduresLoaded.emit(self.bridge.get_procedures()),
            "ics206_signatures": lambda: self.signaturesLoaded.emit(self.bridge.get_signatures()),
        }
        if table == "all":
            for func in loader_map.values():
                try:
                    func()
                except Exception:
                    pass
            return
        func = loader_map.get(table)
        if func:
            try:
                func()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Aid stations ------------------------------------------------------
    @Slot(result=list)
    def load_aid_stations(self) -> List[Dict[str, Any]]:
        data = self.bridge.list_table("aid_stations")
        self.aidStationsLoaded.emit(data)
        return data

    @Slot(dict, result=int)
    def add_aid_station(self, data: Dict[str, Any]) -> int:
        return self.bridge.add_record("aid_stations", data)

    @Slot(int, dict, result=bool)
    def update_aid_station(self, row_id: int, data: Dict[str, Any]) -> bool:
        return self.bridge.update_record("aid_stations", row_id, data)

    @Slot(int, result=bool)
    def delete_aid_station(self, row_id: int) -> bool:
        return self.bridge.delete_record("aid_stations", row_id)

    @Slot(result=int)
    def import_aid_stations(self) -> int:
        return self.bridge.import_aid_stations()

    # ------------------------------------------------------------------
    # Ambulance services -----------------------------------------------
    @Slot(result=list)
    def load_ambulance_services(self) -> List[Dict[str, Any]]:
        data = self.bridge.list_table("ambulance_services")
        self.ambulanceLoaded.emit(data)
        return data

    @Slot(dict, result=int)
    def add_ambulance_service(self, data: Dict[str, Any]) -> int:
        return self.bridge.add_record("ambulance_services", data)

    @Slot(int, dict, result=bool)
    def update_ambulance_service(self, row_id: int, data: Dict[str, Any]) -> bool:
        return self.bridge.update_record("ambulance_services", row_id, data)

    @Slot(int, result=bool)
    def delete_ambulance_service(self, row_id: int) -> bool:
        return self.bridge.delete_record("ambulance_services", row_id)

    @Slot(result=int)
    def import_ambulance_services(self) -> int:
        return self.bridge.import_ambulance_services()

    # ------------------------------------------------------------------
    # Hospitals ---------------------------------------------------------
    @Slot(result=list)
    def load_hospitals(self) -> List[Dict[str, Any]]:
        data = self.bridge.list_table("hospitals")
        self.hospitalsLoaded.emit(data)
        return data

    @Slot(dict, result=int)
    def add_hospital(self, data: Dict[str, Any]) -> int:
        return self.bridge.add_record("hospitals", data)

    @Slot(int, dict, result=bool)
    def update_hospital(self, row_id: int, data: Dict[str, Any]) -> bool:
        return self.bridge.update_record("hospitals", row_id, data)

    @Slot(int, result=bool)
    def delete_hospital(self, row_id: int) -> bool:
        return self.bridge.delete_record("hospitals", row_id)

    @Slot(result=int)
    def import_hospitals(self) -> int:
        return self.bridge.import_hospitals()

    # ------------------------------------------------------------------
    # Air ambulance -----------------------------------------------------
    @Slot(result=list)
    def load_air_ambulance(self) -> List[Dict[str, Any]]:
        data = self.bridge.list_table("air_ambulance")
        self.airAmbulanceLoaded.emit(data)
        return data

    @Slot(dict, result=int)
    def add_air_ambulance(self, data: Dict[str, Any]) -> int:
        return self.bridge.add_record("air_ambulance", data)

    @Slot(int, dict, result=bool)
    def update_air_ambulance(self, row_id: int, data: Dict[str, Any]) -> bool:
        return self.bridge.update_record("air_ambulance", row_id, data)

    @Slot(int, result=bool)
    def delete_air_ambulance(self, row_id: int) -> bool:
        return self.bridge.delete_record("air_ambulance", row_id)

    @Slot(result=int)
    def import_air_ambulance(self) -> int:
        return self.bridge.import_air_ambulance()

    # ------------------------------------------------------------------
    # Medical comms -----------------------------------------------------
    @Slot(result=list)
    def load_medical_comms(self) -> List[Dict[str, Any]]:
        data = self.bridge.list_table("medical_comms")
        self.commsLoaded.emit(data)
        return data

    @Slot(dict, result=int)
    def add_medical_comm(self, data: Dict[str, Any]) -> int:
        return self.bridge.add_record("medical_comms", data)

    @Slot(int, dict, result=bool)
    def update_medical_comm(self, row_id: int, data: Dict[str, Any]) -> bool:
        return self.bridge.update_record("medical_comms", row_id, data)

    @Slot(int, result=bool)
    def delete_medical_comm(self, row_id: int) -> bool:
        return self.bridge.delete_record("medical_comms", row_id)

    @Slot(result=int)
    def import_medical_comms(self) -> int:
        return self.bridge.import_medical_comms()

    # ------------------------------------------------------------------
    # Procedures and signatures ----------------------------------------
    @Slot(result=str)
    def get_procedures(self) -> str:
        text = self.bridge.get_procedures()
        self.proceduresLoaded.emit(text)
        return text

    @Slot(str)
    def save_procedures(self, text: str) -> None:
        self.bridge.save_procedures(text)

    @Slot(result=dict)
    def get_signatures(self) -> Dict[str, Any]:
        data = self.bridge.get_signatures()
        self.signaturesLoaded.emit(data)
        return data

    @Slot(dict)
    def save_signatures(self, data: Dict[str, Any]) -> None:
        self.bridge.save_signatures(data)

    # ------------------------------------------------------------------
    @Slot(result=bool)
    def duplicate_last_op(self) -> bool:
        return self.bridge.duplicate_last_op()

    @Slot()
    def save_pdf(self) -> None:
        """Emit a signal indicating the user requested a PDF export."""
        self.pdfRequested.emit()
