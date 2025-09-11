"""Qt models for ICS 206 Medical Plan tables."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Sequence, Tuple

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


# ---------------------------------------------------------------------------
# Dataclasses representing rows
# ---------------------------------------------------------------------------

@dataclass
class AidStationRow:
    id: int | None
    name: str
    type: str
    level: str
    is_24_7: int
    notes: str = ""


@dataclass
class AmbulanceRow:
    id: int | None
    agency: str
    level: str
    et_minutes: int
    notes: str = ""


@dataclass
class HospitalRow:
    id: int | None
    hospital: str
    trauma_center: str
    bed_cap: int | None
    phone_er: str
    address: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    helipad_lat: float | None = None
    helipad_lon: float | None = None


@dataclass
class AirAmbulanceRow:
    id: int | None
    provider: str
    contact: str
    notes: str = ""


@dataclass
class CommRow:
    id: int | None
    function: str
    channel: str
    notes: str = ""


# ---------------------------------------------------------------------------
# Base table model
# ---------------------------------------------------------------------------

class DictTableModel(QAbstractTableModel):
    """Generic table model working with a list of dictionaries."""

    def __init__(self, headers: Sequence[Tuple[str, str]], parent=None) -> None:
        super().__init__(parent)
        self.headers = list(headers)
        self.rows: List[Dict[str, Any]] = []

    # Qt model interface -------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        return len(self.rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        return len(self.headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        field = self.headers[index.column()][0]
        row = self.rows[index.row()]
        value = row.get(field)
        if role in (Qt.DisplayRole, Qt.EditRole):
            if field == "is_24_7":
                return "Yes" if value else "No"
            return value
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section][1]
        return super().headerData(section, orientation, role)

    # convenience --------------------------------------------------------
    def setRows(self, rows: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def row(self, index: QModelIndex) -> Dict[str, Any] | None:
        if not index.isValid() or index.row() >= len(self.rows):
            return None
        return self.rows[index.row()]


# ---------------------------------------------------------------------------
# Specific table models using the bridge
# ---------------------------------------------------------------------------

class AidStationsModel(DictTableModel):
    def __init__(self, bridge, parent=None) -> None:
        headers = [
            ("id", "ID"),
            ("name", "Name"),
            ("type", "Type"),
            ("level", "Level"),
            ("is_24_7", "24/7"),
        ]
        super().__init__(headers, parent)
        self.bridge = bridge
        self.refresh()

    def refresh(self) -> None:
        self.setRows(self.bridge.list_aid_stations())

    def insertRow(self, row: Dict[str, Any]) -> int:  # type: ignore[override]
        rid = self.bridge.add_aid_station(row)
        self.refresh()
        return rid

    def updateRow(self, row_id: int, row: Dict[str, Any]) -> None:
        self.bridge.update_aid_station(row_id, row)
        self.refresh()

    def removeRow(self, row_id: int) -> None:  # type: ignore[override]
        self.bridge.delete_aid_station(row_id)
        self.refresh()


class AmbulanceModel(DictTableModel):
    def __init__(self, bridge, parent=None) -> None:
        headers = [
            ("id", "ID"),
            ("agency", "Agency"),
            ("level", "Level"),
            ("et_minutes", "ET (min)"),
            ("notes", "Notes"),
        ]
        super().__init__(headers, parent)
        self.bridge = bridge
        self.refresh()

    def refresh(self) -> None:
        self.setRows(self.bridge.list_ambulance())

    def insertRow(self, row: Dict[str, Any]) -> int:  # type: ignore[override]
        rid = self.bridge.add_ambulance(row)
        self.refresh()
        return rid

    def updateRow(self, row_id: int, row: Dict[str, Any]) -> None:
        self.bridge.update_ambulance(row_id, row)
        self.refresh()

    def removeRow(self, row_id: int) -> None:  # type: ignore[override]
        self.bridge.delete_ambulance(row_id)
        self.refresh()


class HospitalsModel(DictTableModel):
    def __init__(self, bridge, parent=None) -> None:
        headers = [
            ("id", "ID"),
            ("hospital", "Hospital"),
            ("trauma_center", "Trauma Center"),
            ("bed_cap", "Bed Cap"),
            ("phone_er", "Phone (ER)"),
            ("helipad_lat", "Helipad"),
        ]
        super().__init__(headers, parent)
        self.bridge = bridge
        self.refresh()

    def refresh(self) -> None:
        self.setRows(self.bridge.list_hospitals())

    def insertRow(self, row: Dict[str, Any]) -> int:  # type: ignore[override]
        rid = self.bridge.add_hospital(row)
        self.refresh()
        return rid

    def updateRow(self, row_id: int, row: Dict[str, Any]) -> None:
        self.bridge.update_hospital(row_id, row)
        self.refresh()

    def removeRow(self, row_id: int) -> None:  # type: ignore[override]
        self.bridge.delete_hospital(row_id)
        self.refresh()


class AirAmbulanceModel(DictTableModel):
    def __init__(self, bridge, parent=None) -> None:
        headers = [
            ("id", "ID"),
            ("provider", "Provider"),
            ("contact", "Contact"),
            ("notes", "Notes"),
        ]
        super().__init__(headers, parent)
        self.bridge = bridge
        self.refresh()

    def refresh(self) -> None:
        self.setRows(self.bridge.list_air_ambulance())

    def insertRow(self, row: Dict[str, Any]) -> int:  # type: ignore[override]
        rid = self.bridge.add_air_ambulance(row)
        self.refresh()
        return rid

    def updateRow(self, row_id: int, row: Dict[str, Any]) -> None:
        self.bridge.update_air_ambulance(row_id, row)
        self.refresh()

    def removeRow(self, row_id: int) -> None:  # type: ignore[override]
        self.bridge.delete_air_ambulance(row_id)
        self.refresh()


class CommsModel(DictTableModel):
    def __init__(self, bridge, parent=None) -> None:
        headers = [
            ("id", "ID"),
            ("function", "Function"),
            ("channel", "Channel"),
            ("notes", "Notes"),
        ]
        super().__init__(headers, parent)
        self.bridge = bridge
        self.refresh()

    def refresh(self) -> None:
        self.setRows(self.bridge.list_comms())

    def insertRow(self, row: Dict[str, Any]) -> int:  # type: ignore[override]
        rid = self.bridge.add_comm(row)
        self.refresh()
        return rid

    def updateRow(self, row_id: int, row: Dict[str, Any]) -> None:
        self.bridge.update_comm(row_id, row)
        self.refresh()

    def removeRow(self, row_id: int) -> None:  # type: ignore[override]
        self.bridge.delete_comm(row_id)
        self.refresh()


__all__ = [
    "AidStationsModel",
    "AmbulanceModel",
    "HospitalsModel",
    "AirAmbulanceModel",
    "CommsModel",
]
