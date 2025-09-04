from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from PySide6.QtCore import Qt, QSortFilterProxyModel, QUrl
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QTableView,
)

from ..models.models import ICS214Model, ICS214Entry


class ICS214ProxyModel(QSortFilterProxyModel):
    """Filter proxy to handle search text and critical toggle."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._search = ""
        self._critical_only = False

    # Properties ------------------------------------------------------
    def setSearchText(self, text: str) -> None:
        self._search = text.lower()
        self.invalidateFilter()

    def setCriticalOnly(self, state: bool) -> None:
        self._critical_only = state
        self.invalidateFilter()

    # QSortFilterProxyModel override ---------------------------------
    def filterAcceptsRow(
        self, source_row: int, source_parent
    ) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if not model:
            return True

        if self._critical_only:
            idx = model.index(source_row, 5, source_parent)
            if not model.data(idx, Qt.DisplayRole):
                return False

        if self._search:
            # Check entry text and tags columns
            entry_idx = model.index(source_row, 2, source_parent)
            tags_idx = model.index(source_row, 6, source_parent)
            entry = model.data(entry_idx, Qt.DisplayRole) or ""
            tags = model.data(tags_idx, Qt.DisplayRole) or ""
            haystack = f"{entry} {tags}".lower()
            return self._search in haystack
        return True


class ICS214Panel(QWidget):
    """Dockable panel for the ICS 214 Activity Log."""

    def __init__(
        self,
        parent=None,
        services: Any | None = None,
        styles: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.sv = services  # expects list_214/add_214/update_214/export_214
        self._init_ui(styles)
        self._connect_signals()
        self.refresh()

    # --- UI ----------------------------------------------------------
    def _init_ui(self, styles: Any | None) -> None:
        self.scope = QComboBox()
        self.scope.addItems(["Section", "Team", "Person", "Task"])
        self.context = QComboBox()
        self.context.setEnabled(False)
        self.op = QComboBox()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter text or #tags")
        self.chkCritical = QCheckBox("Critical only")
        self.chkMine = QCheckBox("Mine only")
        self.btnNew = QPushButton("New Entry")
        self.btnExport = QPushButton("Export")
        self.btnRefresh = QPushButton("Refresh")

        header = QHBoxLayout()
        for w in (
            self.scope,
            self.context,
            self.op,
            self.search,
            self.chkCritical,
            self.chkMine,
            self.btnNew,
            self.btnExport,
            self.btnRefresh,
        ):
            header.addWidget(w)
        header.addStretch(1)

        self.model = ICS214Model()
        self.proxy = ICS214ProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)

        root = QVBoxLayout(self)
        root.addLayout(header)
        root.addWidget(self.table)

    def _connect_signals(self) -> None:
        self.btnRefresh.clicked.connect(self.refresh)
        self.btnExport.clicked.connect(self._on_export)
        self.btnNew.clicked.connect(self._on_new)
        self.scope.currentIndexChanged.connect(self._on_scope_changed)
        self.search.textChanged.connect(self.proxy.setSearchText)
        self.chkCritical.toggled.connect(self.proxy.setCriticalOnly)
        # TODO: hook "Mine only" when user context available

    # --- Actions -----------------------------------------------------
    def refresh(self) -> None:
        """Refresh the model from services."""
        if not self.sv or not hasattr(self.sv, "list_214"):
            self.model.set_entries([])
            return
        try:
            scope = self.scope.currentText().lower()
            ctx = self.context.currentData()
            op = self.op.currentData()
            rows: Sequence[dict[str, Any]] = self.sv.list_214(scope, ctx, op)
            entries = [
                ICS214Entry(
                    when=r.get("when", ""),
                    entered_by=r.get("entered_by", ""),
                    entry=r.get("entry", ""),
                    target=r.get("target", ""),
                    source=r.get("source", ""),
                    critical=bool(r.get("critical", False)),
                    tags=r.get("tags", []),
                )
                for r in rows
            ]
            self.model.set_entries(entries)
        except Exception:
            # Best effort; keep old data on failure
            pass

    def _on_export(self) -> None:
        if not self.sv or not hasattr(self.sv, "export_214"):
            return
        try:
            scope = self.scope.currentText().lower()
            ctx = self.context.currentData()
            op = self.op.currentData()
            pdf_path = self.sv.export_214(
                {"scope": scope, "scope_id": ctx, "op": op},
                prefer_fillable=True,
            )
            print(f"Exported 214 to {pdf_path}")
        except Exception:
            pass

    def _on_new(self) -> None:
        qml_path = (
            Path(__file__).resolve().parent.parent
            / "qml"
            / "LogEntryDialog.qml"
        )
        view = QQuickView()
        view.setTitle("New 214 Entry")
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.setFlags(Qt.Window)
        view.setModality(Qt.NonModal)
        view.setSource(QUrl.fromLocalFile(str(qml_path)))
        root = view.rootObject()
        if root is not None:
            root.saveRequested.connect(self._on_save)
            root.cancelRequested.connect(view.close)
        view.show()

    def _on_save(
        self,
        whenLocal: str,
        enteredBy: str,
        critical: bool,
        tagsText: str,
        entryText: str,
        scope: str,
        scopeTargetId: str,
    ) -> None:
        if not self.sv or not hasattr(self.sv, "add_214"):
            return
        try:
            payload = {
                "when": whenLocal,
                "entered_by": enteredBy,
                "critical": critical,
                "tags": [t.strip() for t in tagsText.split(",") if t.strip()],
                "entry": entryText,
                "scope": scope,
                "scope_id": scopeTargetId,
            }
            self.sv.add_214(payload)
            self.refresh()
        except Exception:
            pass

    def _on_scope_changed(self, idx: int) -> None:
        is_section = idx == 0
        self.context.setEnabled(not is_section)
        if is_section:
            self.context.clear()
        else:
            # TODO: populate context options from services
            self.context.clear()
            # Placeholder entries
            self.context.addItem("Context1", "ctx1")
            self.context.addItem("Context2", "ctx2")
