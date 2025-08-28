# models/incidentlist.py
# QML-friendly IncidentListModel + filterable IncidentProxyModel + QObject IncidentController

from PySide6.QtCore import (
    QAbstractListModel, QModelIndex, Qt, QByteArray,
    QObject, Slot, Signal
)
from PySide6.QtCore import QSortFilterProxyModel, QObject, Signal, Slot, QModelIndex
import os, sqlite3
from types import SimpleNamespace
from typing import List, Any
import logging

logger = logging.getLogger(__name__)

__all__ = ["IncidentListModel", "IncidentProxyModel", "IncidentController"]

# ---------------- Helpers (DB) ---------------- #

def _abs_master_db_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.join(here, os.pardir))
    return os.path.join(repo_root, "data", "master.db")

def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;", (name,))
    return cur.fetchone() is not None

def _cols(cur, table: str) -> set:
    cur.execute(f"PRAGMA table_info({table});")
    return {row[1] for row in cur.fetchall()}

def load_incidents_from_master() -> List[SimpleNamespace]:
    """Load incident rows from the master.db file."""
    db_path = _abs_master_db_path()
    rows: List[SimpleNamespace] = []
    con = None
    try:
        if not os.path.exists(db_path):
            print(f"[incidentlist] DB not found: {db_path}")
            return rows

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        table = "incidents" if _table_exists(cur, "incidents") else ("missions" if _table_exists(cur, "missions") else None)
        if not table:
            print("[incidentlist] Neither 'incidents' nor 'missions' table exists.")
            return rows

        cset = _cols(cur, table)
        def col(name, fallback=None, alias=None):
            chosen = name if name in cset else (fallback if fallback in cset else None)
            if chosen:
                return chosen if alias is None else f"{chosen} AS {alias}"
            safe_alias = alias or name
            return f"NULL AS {safe_alias}"

        select_sql = f"""
            SELECT
                {col('id')},
                {col('number')},
                {col('name')},
                {col('type')},
                {col('status')},
                {col('start_time', 'start')},
                {col('end_time', 'end')},
                {col('is_training', 'training', alias='is_training')},
                {col('icp_location', 'icp')},
                {col('description')},
                {col('search_area', 'area', alias='search_area')}
            FROM {table}
            ORDER BY id DESC
        """
        try:
            cur.execute(select_sql)
        except sqlite3.OperationalError as e:
            print(f"[incidentlist] Fallback SELECT due to {e}")
            cur.execute(f"SELECT * FROM {table} ORDER BY id DESC")

        for r in cur.fetchall():
            rows.append(SimpleNamespace(**{k: r[k] for k in r.keys()}))

        print(f"[incidentlist] Loaded {len(rows)} row(s) from '{table}' in {db_path}")
        return rows
    except Exception as e:
        print(f"[incidentlist] ERROR loading incidents: {e}")
        return rows
    finally:
        try:
            if con:
                con.close()
        except Exception:
            pass

# ---------------- Base list model ---------------- #

class IncidentListModel(QAbstractListModel):
    """QML-facing model exposing roles for incidents."""
    ROLE_NAMES = [
        "id", "number", "name", "type", "status",
        "start_time", "end_time", "is_training", "icp_location",
        "description", "search_area",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: List[SimpleNamespace] = []
        self._role_map = {Qt.UserRole + i + 1: name.encode() for i, name in enumerate(self.ROLE_NAMES)}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._rows)

    def roleNames(self):  # type: ignore[override]
        return {k: QByteArray(v) for k, v in self._role_map.items()}

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        name = self._role_map.get(role)
        if not name:
            return getattr(row, "name", None)
        key = name.decode() if isinstance(name, (bytes, bytearray)) else name
        return getattr(row, key, None)

    def refresh(self) -> None:
        items = load_incidents_from_master()
        self.beginResetModel()
        self._rows = items
        self.endResetModel()

    # Compatibility shim for older code paths
    def reload(self, loader=None) -> None:
        if callable(loader):
            items = loader()
        else:
            items = load_incidents_from_master()
        self.beginResetModel()
        self._rows = items or []
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def count(self) -> int:
        return len(self._rows)

    def load_sample(self) -> None:
        from types import SimpleNamespace as NS
        self.beginResetModel()
        self._rows = [
            NS(id=1, number="G-001", name="Test Incident", type="SAR", status="Active",
               start_time=None, end_time=None, is_training=False, icp_location="HQ",
               description="This is just a sample row.", search_area="Trail 5"),
        ]
        self.endResetModel()

# ---------------- Proxy (with QML-callable filters) ---------------- #

class IncidentProxyModel(QSortFilterProxyModel):
    """Proxy with QML-callable filters: status/type/training/text."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._text_filter = ""
        self._status_filter = ""
        self._type_filter = ""
        self._training_filter: object | None = None  # None=no filter, True/False filter
        self.setDynamicSortFilter(True)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    # QML-callable slots
    @Slot(str)
    def setFilterText(self, text: str) -> None:
        self._text_filter = text or ""
        self.invalidateFilter()

    @Slot(str)
    def setTextFilter(self, text: str) -> None:
        self.setFilterText(text)

    @Slot(str)
    def setStatusFilter(self, status: str) -> None:
        self._status_filter = (status or "").strip()
        self.invalidateFilter()

    @Slot(str)
    def setTypeFilter(self, t: str) -> None:
        self._type_filter = (t or "").strip()
        self.invalidateFilter()

    @Slot('QVariant')
    def setTrainingFilter(self, v) -> None:
        if isinstance(v, bool):
            self._training_filter = v
        else:
            s = (str(v) if v is not None else "").strip().lower()
            if s in ("", "all", "any"):
                self._training_filter = None
            elif s in ("true", "1", "yes", "y"):
                self._training_filter = True
            elif s in ("false", "0", "no", "n"):
                self._training_filter = False
            else:
                self._training_filter = None
        self.invalidateFilter()

    # helpers
    def _role_number(self, name_bytes: bytes | str) -> int | None:
        sm = self.sourceModel()
        if sm is None:
            return None
        rn = sm.roleNames()
        key = name_bytes.encode() if isinstance(name_bytes, str) else name_bytes
        for role, rname in rn.items():
            if bytes(rname) == key:
                return role
        return None

    def _get(self, sm, row: int, role_name: bytes):
        role = self._role_number(role_name)
        if role is None:
            return None
        idx = sm.index(row, 0)
        return sm.data(idx, role)

    # filtering logic
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        sm = self.sourceModel()
        if sm is None:
            return True

        # Text filter across common fields
        if self._text_filter:
            needle = self._text_filter.lower()
            hay = [self._get(sm, source_row, r) for r in (b"name", b"number", b"status", b"type", b"icp_location", b"description", b"search_area")]
            if not any((str(v).lower().find(needle) != -1) for v in hay if v is not None):
                return False

        # Status filter
        if self._status_filter:
            val = self._get(sm, source_row, b"status")
            if (val or "").strip() != self._status_filter:
                return False

        # Type filter
        if self._type_filter:
            val = self._get(sm, source_row, b"type")
            if (val or "").strip() != self._type_filter:
                return False

        # Training filter
        if self._training_filter is not None:
            v = self._get(sm, source_row, b"is_training")
            vb = bool(v) if v is not None else False
            if vb != bool(self._training_filter):
                return False

        return True

    def lessThan(self, left, right):  # type: ignore[override]
        sm = self.sourceModel()
        if sm is None:
            return False
        role = self._role_number(b"name") or Qt.DisplayRole
        l = sm.data(left, role)
        r = sm.data(right, role)
        return str(l) < str(r)

# ---------------- QObject controller (invokable from QML) ---------------- #
class IncidentController(QObject):
    incidentselected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.model = IncidentListModel()
        self.model.refresh()
        self.proxy = IncidentProxyModel()
        self.proxy.setSourceModel(self.model)

    # Support BOTH call styles:
    #   - controller.loadIncident(proxy, row)
    #   - controller.loadIncident("INC-123")
    @Slot(QObject, int)
    @Slot(str)
    def loadIncident(self, arg1, row: int | None = None) -> None:
        # Overloaded slot handler
        if row is None:
            # Called with a single string
            incident_number = str(arg1) if arg1 is not None else ""
            if incident_number:
                self.incidentselected.emit(incident_number)
            return

        # Called with (model, row)
        model = arg1
        if row < 0 or model is None:
            return
        try:
            role = model.roleForName(b"number")
        except Exception:
            role = None
        idx = model.index(row, 0)
        num = model.data(idx, role) if role is not None else None
        if num is not None:
            self.incidentselected.emit(str(num))

            # ---- OVERLOAD 1: very permissive (catches QML when types are fuzzy) ----
    @Slot('QVariant', 'QVariant')
    def loadIncident(self, proxy_any, row_any):
        print("DEBUG: loadIncident(QVariant,QVariant) called:", proxy_any, row_any, flush=True)
        try:
            row = int(row_any) if row_any is not None else -1
        except Exception:
            row = -1
        self._emit_from_proxy_row(proxy_any, row)

    # ---- OVERLOAD 2: explicit QObject + int ----
    @Slot(QObject, int)
    def loadIncident2(self, proxy_obj, row):
        print("DEBUG: loadIncident(QObject,int) called:", proxy_obj, row, flush=True)
        self._emit_from_proxy_row(proxy_obj, row)

    # ---- OVERLOAD 3: accept just a row, use a proxy set earlier if you want ----
    @Slot(int)
    def loadIncidentByRow(self, row):
        print("DEBUG: loadIncidentByRow(int) called:", row, flush=True)
        # If you store a proxy on the controller (e.g., self._proxy = proxy),
        # you can use it here. Otherwise just no-op with a warning.
        proxy = getattr(self, "_proxy", None)
        if proxy is None:
            print("DEBUG: no stored proxy on controller", flush=True)
            return
        self._emit_from_proxy_row(proxy, row)

    # ---- OVERLOAD 4: accept a number string directly ----
    @Slot(str)
    def loadIncidentByNumber(self, number):
        print("DEBUG: loadIncidentByNumber(str) called:", number, flush=True)
        if not number:
            print("DEBUG: empty number; ignoring", flush=True)
            return
        logger.info("Emitting incidentselected with %r (direct number)", number)
        self.incidentselected.emit(str(number))

    # ---- Shared worker ----
    def _emit_from_proxy_row(self, proxy, row: int):
        try:
            if proxy is None:
                print("DEBUG: proxy is None", flush=True)
                return
            if not hasattr(proxy, "mapToSource"):
                print("DEBUG: proxy has no mapToSource; type:", type(proxy), flush=True)
                return
            if row is None or row < 0:
                print("DEBUG: invalid row:", row, flush=True)
                return

            # Map proxy row to source index
            src_index: QModelIndex = proxy.mapToSource(proxy.index(int(row), 0))
            src_model = proxy.sourceModel()
            if not src_index.isValid() or src_model is None:
                print("DEBUG: invalid src_index or no sourceModel", src_index, src_model, flush=True)
                return

            # Try to read "number" role; fall back to DisplayRole
            role = src_model.roleForName(b"number") if hasattr(src_model, "roleForName") else None
            if role is None:
                number = src_model.data(src_index)  # DisplayRole
            else:
                number = src_model.data(src_index, role)

            print("DEBUG: resolved incident number:", number, flush=True)
            logger.info("Emitting incidentselected with %r", number)
            self.incidentselected.emit(str(number))
        except Exception as e:
            import traceback
            print("DEBUG: _emit_from_proxy_row exception:", e, flush=True)
            traceback.print_exc()

    # --- Stubs so QML buttons don't explode (fill these out later) ---
    @Slot(QObject, int)
    def editIncident(self, model, row: int) -> None:
        print("[IncidentController] editIncident called for row", row)

    @Slot(QObject, int)
    def deleteIncident(self, model, row: int) -> None:
        print("[IncidentController] deleteIncident called for row", row)

    @Slot()
    def newIncident(self) -> None:
        print("[IncidentController] newIncident called")

    # Convenience for QML filter bar
    @Slot()
    def refresh(self) -> None:
        self.model.refresh()

    @Slot(str)
    def setFilterText(self, text: str) -> None:
        self.proxy.setFilterText(text)

    @Slot(str)
    def setStatusFilter(self, status: str) -> None:
        self.proxy.setStatusFilter(status)

    @Slot(str)
    def setTypeFilter(self, t: str) -> None:
        self.proxy.setTypeFilter(t)

    @Slot('QVariant')
    def setTrainingFilter(self, v) -> None:
        # Accept bool/str/int (0=All, 1=Only Training, 2=Only Real)
        if isinstance(v, int):
            mapped = None if v == 0 else (True if v == 1 else False)
            self.proxy.setTrainingFilter(mapped)
        else:
            self.proxy.setTrainingFilter(v)

    # getters for Python to pass to QML
    def getProxy(self):
        return self.proxy

    def getModel(self):
        return self.model
