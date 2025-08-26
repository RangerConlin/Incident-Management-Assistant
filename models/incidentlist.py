"""
Incident selection data model and helpers.
- Adapts to the existing Incident domain object via COLUMN_MAP.
- Loads rows from data/master.db (SQLite) using load_incidents_from_master().
- Exposes a QSortFilterProxyModel for sorting and filtering.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Callable, List, Sequence
from types import SimpleNamespace

from PySide6.QtCore import (
    QAbstractTableModel,
    QSortFilterProxyModel,
    Qt,
    QModelIndex,
    QObject,
    Signal,
    Slot,
)

# ---------------------------------------------------------------------------
# Column resolution configuration
# ---------------------------------------------------------------------------

# Logical role/column → how to read from the existing Incident object
# Each value may be: attribute name ("name"), dict key ("[name]"), or a
# callable: lambda m: ...
COLUMN_MAP = {
    "id": "id",
    "number": "number",
    "name": "name",
    "type": "type",
    "status": "status",
    "start_time": "start_time",  # ISO8601 UTC string
    "end_time": "end_time",  # ISO8601 UTC string (may be empty)
    "is_training": "is_training",  # bool or 0/1
    "icp_location": "icp_location",
    # Extra fields used for filtering only:
    "description": "description",
    "search_area": "search_area",
}


def resolve(m: object, key: str):
    """Return the value for logical field `key` from Incident `m` using COLUMN_MAP."""

    spec = COLUMN_MAP[key]
    if callable(spec):
        return spec(m)
    if isinstance(spec, str) and spec.startswith("[") and spec.endswith("]"):
        return m[spec[1:-1]]
    return getattr(m, spec)


# ---------------------------------------------------------------------------
# Incident table model
# ---------------------------------------------------------------------------


class IncidentListModel(QAbstractTableModel):
    """Qt table model exposing incidents for the selector UI."""

    headers = [
        "ID",
        "Number",
        "Incident Name",
        "Type",
        "Status",
        "Start (UTC)",
        "End (UTC)",
        "Training",
        "ICP",
    ]

    # Role numbers start at Qt.UserRole
    _roles = {
        Qt.UserRole + i: name.encode()
        for i, name in enumerate(COLUMN_MAP.keys())
    }

    def __init__(self, incidents: Sequence[object] | None = None):
        super().__init__()
        self._incidents: List[object] = list(incidents or [])

    # --- Qt model implementation -----------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._incidents)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self.headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        incident = self._incidents[index.row()]
        if role == Qt.DisplayRole:
            key = list(COLUMN_MAP.keys())[index.column()]
            value = resolve(incident, key)
            if key == "is_training":
                return "Yes" if bool(value) else "No"
            return value
        elif role in self._roles:
            key = self._roles[role].decode()
            return resolve(incident, key)
        return None

    def roleNames(self):  # type: ignore[override]
        return self._roles

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            try:
                return self.headers[section]
            except IndexError:
                return None
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex):  # type: ignore[override]
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    # --- Helpers -----------------------------------------------------------
    def incident_at(self, row: int):
        """Return incident object at model row."""

        if 0 <= row < len(self._incidents):
            return self._incidents[row]
        return None

    # --- Data reloading ----------------------------------------------------
    def reload(self, provider: Callable[[], Sequence[object]] | None = None):
        """Repopulate the model using ``provider`` (defaults to DB loader)."""

        provider = provider or load_incidents_from_master
        incidents = list(provider())
        self.beginResetModel()
        self._incidents = incidents
        self.endResetModel()


# ---------------------------------------------------------------------------
# SQLite loader
# ---------------------------------------------------------------------------


def load_incidents_from_master() -> List[object]:
    """Read incidents from data/master.db; return Incident objects or proxies."""

    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "master.db")
    if not os.path.exists(db_path):
        return []

    try:
        from models.incident import Incident  # type: ignore
    except Exception:  # pragma: no cover - Incident class should exist
        Incident = None  # type: ignore

    incidents: List[object] = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, number, type, description, status,
                   search_area, icp_location, start_time, end_time, is_training
            FROM incidents
            ORDER BY start_time DESC, id DESC
            """
        )
        for row in cur.fetchall():
            if Incident is not None:
                incident = Incident(
                    id=row["id"],
                    number=row["number"],
                    name=row["name"],
                    type=row["type"],
                    description=row["description"],
                    status=row["status"],
                    icp_location=row["icp_location"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    is_training=bool(row["is_training"]),
                )
                # Existing Incident class lacks search_area; attach dynamically.
                setattr(incident, "search_area", row["search_area"])
            else:
                incident = SimpleNamespace(
                    id=row["id"],
                    number=row["number"],
                    name=row["name"],
                    type=row["type"],
                    description=row["description"],
                    status=row["status"],
                    search_area=row["search_area"],
                    icp_location=row["icp_location"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    is_training=bool(row["is_training"]),
                )
            incidents.append(incident)
        conn.close()
    except sqlite3.Error:
        # If the table is missing or unreadable, return empty list.
        return []

    return incidents


# ---------------------------------------------------------------------------
# Proxy filters
# ---------------------------------------------------------------------------


class IncidentProxyModel(QSortFilterProxyModel):
    """Filtering/sorting proxy for IncidentListModel."""

    def __init__(self):
        super().__init__()
        self._status = "All"
        self._type = "All"
        self._training = 0  # 0=All, 1=Only Training, 2=Only Real
        self._text = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setDynamicSortFilter(True)

    # -- Slots to adjust filters ------------------------------------------
    @Slot(str)
    def setStatusFilter(self, value: str):
        self._status = value
        self.invalidateFilter()

    @Slot(str)
    def setTypeFilter(self, value: str):
        self._type = value
        self.invalidateFilter()

    @Slot(int)
    def setTrainingFilter(self, value: int):
        self._training = value
        self.invalidateFilter()

    @Slot(str)
    def setTextFilter(self, value: str):
        self._text = value.lower()
        self.invalidateFilter()

    # -- Filter logic ------------------------------------------------------
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        model: IncidentListModel = self.sourceModel()  # type: ignore[assignment]
        incident = model.incident_at(source_row)
        if incident is None:
            return False

        # Status filter
        if self._status and self._status != "All":
            if str(resolve(incident, "status")).lower() != self._status.lower():
                return False

        # Type filter
        if self._type and self._type != "All":
            if str(resolve(incident, "type")).lower() != self._type.lower():
                return False

        # Training filter
        if self._training == 1 and not bool(resolve(incident, "is_training")):
            return False
        if self._training == 2 and bool(resolve(incident, "is_training")):
            return False

        # Text search across multiple fields
        if self._text:
            haystack = " ".join(
                str(resolve(incident, key) or "")
                for key in [
                    "name",
                    "number",
                    "description",
                    "icp_location",
                    "search_area",
                ]
            ).lower()
            if self._text not in haystack:
                return False

        return True


# ---------------------------------------------------------------------------
# Controller slots
# ---------------------------------------------------------------------------


class IncidentController(QObject):
    """Controller emitting CRUD-related signals for incidents."""

    incidentLoaded = Signal(int)
    incidentEdited = Signal(int)
    incidentDeleted = Signal(int)
    incidentCreated = Signal(int)
    error = Signal(str)

    def __init__(self, model: IncidentListModel):
        super().__init__()
        self._model = model

    # -- Slots used by QML -------------------------------------------------
    @Slot(QObject, int)
    def loadIncident(self, proxy: IncidentProxyModel, proxyRow: int):
        """Emit incidentLoaded for the row."""

        incident_id = self._incident_id_from_proxy(proxy, proxyRow)
        if incident_id is not None:
            self.incidentLoaded.emit(incident_id)

    @Slot(QObject, int)
    def editIncident(self, proxy: IncidentProxyModel, proxyRow: int):
        """Emit incidentEdited. DB updates will be wired later."""

        incident_id = self._incident_id_from_proxy(proxy, proxyRow)
        if incident_id is not None:
            self.incidentEdited.emit(incident_id)

    @Slot(QObject, int)
    def deleteIncident(self, proxy: IncidentProxyModel, proxyRow: int):
        """Emit incidentDeleted. Actual DB removal will be handled later."""

        incident_id = self._incident_id_from_proxy(proxy, proxyRow)
        if incident_id is not None:
            self.incidentDeleted.emit(incident_id)

    @Slot()
    def newIncident(self):
        """Emit incidentCreated placeholder signal."""

        # When a creation dialog is wired up, the new incident ID will be
        # emitted here instead of -1.
        self.incidentCreated.emit(-1)

    # -- Internal helpers --------------------------------------------------
    def _incident_id_from_proxy(self, proxy: IncidentProxyModel, proxyRow: int):
        if proxy is None or proxyRow < 0:
            return None
        source_index = proxy.mapToSource(proxy.index(proxyRow, 0))
        incident = self._model.incident_at(source_index.row())
        if incident is None:
            return None
        return int(resolve(incident, "id"))


__all__ = [
    "IncidentListModel",
    "IncidentProxyModel",
    "IncidentController",
    "load_incidents_from_master",
]

