from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import QObject, Slot

from models.master_catalog import make_service, ENTITY_CONFIGS


class CatalogBridge(QObject):
    """QObject bridge exposing CRUD for master catalog entities to QML.

    Methods return plain Python types (list[dict], bool, int) which Qt converts
    to QVariant for QML.
    """

    def __init__(self, db_path: str = "data/master.db") -> None:
        super().__init__()
        self._db_path = db_path
        # Build services from entity configs
        self._services: Dict[str, Any] = {
            key: make_service(db_path, key) for key in ENTITY_CONFIGS.keys()
        }

    # --- utilities -----------------------------------------------------
    def _svc(self, key: str):
        return self._services[key]

    # --- Personnel -----------------------------------------------------
    @Slot(str, result=list)
    def listPersonnel(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("personnel").list(searchText)

    @Slot(dict, result=int)
    def createPersonnel(self, data: Dict[str, Any]) -> int:
        return self._svc("personnel").create(data)

    @Slot(int, dict, result=bool)
    def updatePersonnel(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("personnel").update(id_value, data)

    @Slot(int, result=bool)
    def deletePersonnel(self, id_value: int) -> bool:
        return self._svc("personnel").delete(id_value)

    # --- Vehicles ------------------------------------------------------
    @Slot(str, result=list)
    def listVehicles(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("vehicles").list(searchText)

    @Slot(dict, result=int)
    def createVehicles(self, data: Dict[str, Any]) -> int:
        return self._svc("vehicles").create(data)

    @Slot(int, dict, result=bool)
    def updateVehicles(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("vehicles").update(id_value, data)

    @Slot(int, result=bool)
    def deleteVehicles(self, id_value: int) -> bool:
        return self._svc("vehicles").delete(id_value)

    # --- Aircraft -----------------------------------------------------
    @Slot(str, result=list)
    def listAircraft(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("aircraft").list(searchText)

    @Slot(dict, result=int)
    def createAircraft(self, data: Dict[str, Any]) -> int:
        return self._svc("aircraft").create(data)

    @Slot(int, dict, result=bool)
    def updateAircraft(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("aircraft").update(id_value, data)

    @Slot(int, result=bool)
    def deleteAircraft(self, id_value: int) -> bool:
        return self._svc("aircraft").delete(id_value)

    # --- Equipment -----------------------------------------------------
    @Slot(str, result=list)
    def listEquipment(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("equipment").list(searchText)

    @Slot(dict, result=int)
    def createEquipment(self, data: Dict[str, Any]) -> int:
        return self._svc("equipment").create(data)

    @Slot(int, dict, result=bool)
    def updateEquipment(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("equipment").update(id_value, data)

    @Slot(int, result=bool)
    def deleteEquipment(self, id_value: int) -> bool:
        return self._svc("equipment").delete(id_value)

    # --- Communications Resources -------------------------------------
    @Slot(str, result=list)
    def listCommsResources(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("comms_resources").list(searchText)

    @Slot(dict, result=int)
    def createCommsResources(self, data: Dict[str, Any]) -> int:
        return self._svc("comms_resources").create(data)

    @Slot(int, dict, result=bool)
    def updateCommsResources(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("comms_resources").update(id_value, data)

    @Slot(int, result=bool)
    def deleteCommsResources(self, id_value: int) -> bool:
        return self._svc("comms_resources").delete(id_value)

    # --- Objectives (master templates) --------------------------------
    @Slot(str, result=list)
    def listObjectives(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("incident_objectives").list(searchText)

    @Slot(dict, result=int)
    def createObjectives(self, data: Dict[str, Any]) -> int:
        return self._svc("incident_objectives").create(data)

    @Slot(int, dict, result=bool)
    def updateObjectives(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("incident_objectives").update(id_value, data)

    @Slot(int, result=bool)
    def deleteObjectives(self, id_value: int) -> bool:
        return self._svc("incident_objectives").delete(id_value)

    # --- Certifications -----------------------------------------------
    @Slot(str, result=list)
    def listCertifications(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("certification_types").list(searchText)

    @Slot(dict, result=int)
    def createCertification(self, data: Dict[str, Any]) -> int:
        return self._svc("certification_types").create(data)

    @Slot(int, dict, result=bool)
    def updateCertification(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("certification_types").update(id_value, data)

    @Slot(int, result=bool)
    def deleteCertification(self, id_value: int) -> bool:
        return self._svc("certification_types").delete(id_value)

    # Assign certification to personnel (personnel_certifications)
    @Slot(int, int, int, result=bool)
    def assignCertificationToPersonnel(self, certification_id: int, personnel_id: int, level: int = 0) -> bool:
        import sqlite3
        try:
            con = sqlite3.connect(self._db_path)
            with con:
                con.execute(
                    "INSERT INTO personnel_certifications (personnel_id, certification_id, level) VALUES (?,?,?)",
                    (personnel_id, certification_id, level),
                )
            return True
        except Exception as e:  # pragma: no cover
            print("[assignCertificationToPersonnel]", e)
            return False

    # --- Placeholders --------------------------------------------------
    @Slot(str, result=list)
    def listEms(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("ems").list(searchText)

    @Slot(dict, result=int)
    def createEms(self, data: Dict[str, Any]) -> int:
        return self._svc("ems").create(data)

    @Slot(int, dict, result=bool)
    def updateEms(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("ems").update(id_value, data)

    @Slot(int, result=bool)
    def deleteEms(self, id_value: int) -> bool:
        return self._svc("ems").delete(id_value)

    @Slot(str, result=list)
    def listCannedCommEntries(self, searchText: str = "") -> List[Dict[str, Any]]:
        rows = self._svc("canned_comm_entries").list(searchText)
        try:
            print(f"[CatalogBridge.listCannedCommEntries] returning {len(rows)} rows for search='{searchText}'")
        except Exception:
            pass
        return rows

    @Slot(dict, result=int)
    def createCannedCommEntry(self, data: Dict[str, Any]) -> int:
        return self._svc("canned_comm_entries").create(data)

    @Slot(int, dict, result=bool)
    def updateCannedCommEntry(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("canned_comm_entries").update(id_value, data)

    @Slot(int, result=bool)
    def deleteCannedCommEntry(self, id_value: int) -> bool:
        return self._svc("canned_comm_entries").delete(id_value)

    @Slot(str, result=list)
    def listTaskTypes(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("task_types").list(searchText)

    @Slot(dict, result=int)
    def createTaskType(self, data: Dict[str, Any]) -> int:
        return self._svc("task_types").create(data)

    @Slot(int, dict, result=bool)
    def updateTaskType(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("task_types").update(id_value, data)

    @Slot(int, result=bool)
    def deleteTaskType(self, id_value: int) -> bool:
        return self._svc("task_types").delete(id_value)

    @Slot(str, result=list)
    def listTeamTypes(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("team_types").list(searchText)

    @Slot(dict, result=int)
    def createTeamType(self, data: Dict[str, Any]) -> int:
        return self._svc("team_types").create(data)

    @Slot(int, dict, result=bool)
    def updateTeamType(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("team_types").update(id_value, data)

    @Slot(int, result=bool)
    def deleteTeamType(self, id_value: int) -> bool:
        return self._svc("team_types").delete(id_value)

    # --- Safety Templates ---------------------------------------------
    @Slot(str, result=list)
    def listSafetyTemplates(self, searchText: str = "") -> List[Dict[str, Any]]:
        return self._svc("safety_templates").list(searchText)

    @Slot(dict, result=int)
    def createSafetyTemplate(self, data: Dict[str, Any]) -> int:
        return self._svc("safety_templates").create(data)

    @Slot(int, dict, result=bool)
    def updateSafetyTemplate(self, id_value: int, data: Dict[str, Any]) -> bool:
        return self._svc("safety_templates").update(id_value, data)

    @Slot(int, result=bool)
    def deleteSafetyTemplate(self, id_value: int) -> bool:
        return self._svc("safety_templates").delete(id_value)

