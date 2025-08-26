"""
Mission selection data model and helpers.
- Adapts to the existing Mission domain object via COLUMN_MAP.
- Loads rows from data/master.db (SQLite) using load_missions_from_master().
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

# Logical role/column → how to read from the existing Mission object
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
    """Return the value for logical field `key` from Mission `m` using COLUMN_MAP."""

    spec = COLUMN_MAP[key]
    if callable(spec):
        return spec(m)
    if isinstance(spec, str) and spec.startswith("[") and spec.endswith("]"):
        return m[spec[1:-1]]
    return getattr(m, spec)


# ---------------------------------------------------------------------------
# Mission table model
# ---------------------------------------------------------------------------


class MissionListModel(QAbstractTableModel):
    """Qt table model exposing missions for the selector UI."""

    headers = [
        "ID",
        "Number",
        "Mission Name",
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

    def __init__(self, missions: Sequence[object] | None = None):
        super().__init__()
        self._missions: List[object] = list(missions or [])

    # --- Qt model implementation -----------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._missions)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self.headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        mission = self._missions[index.row()]
        if role == Qt.DisplayRole:
            key = list(COLUMN_MAP.keys())[index.column()]
            value = resolve(mission, key)
            if key == "is_training":
                return "Yes" if bool(value) else "No"
            return value
        elif role in self._roles:
            key = self._roles[role].decode()
            return resolve(mission, key)
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
    def mission_at(self, row: int):
        """Return mission object at model row."""

        if 0 <= row < len(self._missions):
            return self._missions[row]
        return None

    # --- Data reloading ----------------------------------------------------
    def reload(self, provider: Callable[[], Sequence[object]] | None = None):
        """Repopulate the model using ``provider`` (defaults to DB loader)."""

        provider = provider or load_missions_from_master
        missions = list(provider())
        self.beginResetModel()
        self._missions = missions
        self.endResetModel()


# ---------------------------------------------------------------------------
# SQLite loader
# ---------------------------------------------------------------------------


def load_missions_from_master() -> List[object]:
    """Read missions from data/master.db; return Mission objects or proxies."""

    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "master.db")
    if not os.path.exists(db_path):
        return []

    try:
        from models.mission import Mission  # type: ignore
    except Exception:  # pragma: no cover - Mission class should exist
        Mission = None  # type: ignore

    missions: List[object] = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, number, type, description, status,
                   search_area, icp_location, start_time, end_time, is_training
            FROM missions
            ORDER BY start_time DESC, id DESC
            """
        )
        for row in cur.fetchall():
            if Mission is not None:
                mission = Mission(
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
                # Existing Mission class lacks search_area; attach dynamically.
                setattr(mission, "search_area", row["search_area"])
            else:
                mission = SimpleNamespace(
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
            missions.append(mission)
        conn.close()
    except sqlite3.Error:
        # If the table is missing or unreadable, return empty list.
        return []

    return missions


# ---------------------------------------------------------------------------
# Proxy filters
# ---------------------------------------------------------------------------


class MissionProxyModel(QSortFilterProxyModel):
    """Filtering/sorting proxy for MissionListModel."""

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
        model: MissionListModel = self.sourceModel()  # type: ignore[assignment]
        mission = model.mission_at(source_row)
        if mission is None:
            return False

        # Status filter
        if self._status and self._status != "All":
            if str(resolve(mission, "status")).lower() != self._status.lower():
                return False

        # Type filter
        if self._type and self._type != "All":
            if str(resolve(mission, "type")).lower() != self._type.lower():
                return False

        # Training filter
        if self._training == 1 and not bool(resolve(mission, "is_training")):
            return False
        if self._training == 2 and bool(resolve(mission, "is_training")):
            return False

        # Text search across multiple fields
        if self._text:
            haystack = " ".join(
                str(resolve(mission, key) or "")
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


class MissionController(QObject):
    """Controller emitting CRUD-related signals for missions."""

    missionLoaded = Signal(int)
    missionEdited = Signal(int)
    missionDeleted = Signal(int)
    missionCreated = Signal(int)
    error = Signal(str)

    def __init__(self, model: MissionListModel):
        super().__init__()
        self._model = model

    # -- Slots used by QML -------------------------------------------------
    @Slot(QObject, int)
    def loadMission(self, proxy: MissionProxyModel, proxyRow: int):
        """Emit missionLoaded for the row."""

        mission_id = self._mission_id_from_proxy(proxy, proxyRow)
        if mission_id is not None:
            self.missionLoaded.emit(mission_id)

    @Slot(QObject, int)
    def editMission(self, proxy: MissionProxyModel, proxyRow: int):
        """Emit missionEdited. DB updates will be wired later."""

        mission_id = self._mission_id_from_proxy(proxy, proxyRow)
        if mission_id is not None:
            self.missionEdited.emit(mission_id)

    @Slot(QObject, int)
    def deleteMission(self, proxy: MissionProxyModel, proxyRow: int):
        """Emit missionDeleted. Actual DB removal will be handled later."""

        mission_id = self._mission_id_from_proxy(proxy, proxyRow)
        if mission_id is not None:
            self.missionDeleted.emit(mission_id)

    @Slot()
    def newMission(self):
        """Emit missionCreated placeholder signal."""

        # When a creation dialog is wired up, the new mission ID will be
        # emitted here instead of -1.
        self.missionCreated.emit(-1)

    # -- Internal helpers --------------------------------------------------
    def _mission_id_from_proxy(self, proxy: MissionProxyModel, proxyRow: int):
        if proxy is None or proxyRow < 0:
            return None
        source_index = proxy.mapToSource(proxy.index(proxyRow, 0))
        mission = self._model.mission_at(source_index.row())
        if mission is None:
            return None
        return int(resolve(mission, "id"))


__all__ = [
    "MissionListModel",
    "MissionProxyModel",
    "MissionController",
    "load_missions_from_master",
]

