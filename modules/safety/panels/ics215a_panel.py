"""ICS-215A Incident Action Safety Analysis panel.

Pulls hazards embedded in work assignment documents and presents two
simultaneous views in a horizontal QSplitter:

  Left  — Consolidated (deduplicated) view: one row per unique hazard,
           with a "Work Assignments" column listing every WA that shares it.
  Right — By-Assignment view: one group section per WA, each with its own
           hazard table.

Each section can be collapsed / restored via its header button.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.api_client import api_client
from utils.state import AppState

# ---------------------------------------------------------------------------
# Risk-level colour palette
# ---------------------------------------------------------------------------

_RISK_COLORS: Dict[str, str] = {
    "Extreme": "#ffcdd2",
    "High":    "#ffe0b2",
    "Medium":  "#fff9c4",
    "Low":     "#c8e6c9",
}

_RISK_TEXT: Dict[str, str] = {
    "Extreme": "#b71c1c",
    "High":    "#e65100",
    "Medium":  "#f57f17",
    "Low":     "#1b5e20",
}

_SPE_COLORS: Dict[str, str] = {
    "Very High":   "#ffcdd2",
    "High":        "#ffe0b2",
    "Substantial": "#fff9c4",
    "Possible":    "#fff9c4",
    "Slight":      "#c8e6c9",
}

_SPE_TEXT: Dict[str, str] = {
    "Very High":   "#b71c1c",
    "High":        "#e65100",
    "Substantial": "#f57f17",
    "Possible":    "#f57f17",
    "Slight":      "#1b5e20",
}

_SPE_ORDER = {"Very High": 0, "High": 1, "Substantial": 2, "Possible": 3, "Slight": 4}


def _risk_item(text: str, risk: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    bg = _RISK_COLORS.get(risk)
    fg = _RISK_TEXT.get(risk)
    if bg:
        item.setBackground(QColor(bg))
    if fg:
        item.setForeground(QColor(fg))
    return item


def _ro_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


def _section_header(title: str) -> QLabel:
    lbl = QLabel(title)
    font = QFont()
    font.setBold(True)
    font.setPointSize(9)
    lbl.setFont(font)
    lbl.setStyleSheet("color: #1a237e; background: #e8eaf6; padding: 4px 8px;")
    return lbl


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color: #bdbdbd;")
    return f


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dedup_key(hazard: dict) -> str:
    """Stable deduplication key: prefer hazard_type_id, fall back to text."""
    tid = hazard.get("hazard_type_id")
    if tid:
        return f"id:{tid}"
    return f"text:{hazard.get('hazard_type_text', '').lower().strip()}"


def _wa_label(wa: dict) -> str:
    num = wa.get("assignment_number") or ""
    name = wa.get("assignment_name") or ""
    if num and name:
        return f"{num} – {name}"
    return num or name or f"WA {wa.get('id', '?')}"


def _spe_item(text: str, degree: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    bg = _SPE_COLORS.get(degree)
    fg = _SPE_TEXT.get(degree)
    if bg:
        item.setBackground(QColor(bg))
    if fg:
        item.setForeground(QColor(fg))
    return item


# ---------------------------------------------------------------------------
# Consolidated hazard table (left pane)
# ---------------------------------------------------------------------------

_CONSOLIDATED_COLS = [
    "Hazard",
    "Category",
    "Risk",
    "Likelihood",
    "Severity",
    "Control Measure",
    "PPE",
    "Resolved",
    "Work Assignments",
]


class _ConsolidatedTable(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._count_lbl = QLabel("0 unique hazards")
        self._count_lbl.setStyleSheet("font-size: 11px; color: #546e7a;")
        layout.addWidget(self._count_lbl)

        self._tbl = QTableWidget(0, len(_CONSOLIDATED_COLS))
        self._tbl.setHorizontalHeaderLabels(_CONSOLIDATED_COLS)
        self._tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self._tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.horizontalHeader().setStretchLastSection(True)
        self._tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._tbl, 1)

    def load(self, rows: List[Tuple[dict, List[str]]]) -> None:
        """rows: list of (hazard_dict, [wa_label, ...])"""
        self._tbl.setRowCount(0)
        for hazard, wa_labels in rows:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            risk = hazard.get("risk_level", "Unknown")
            shared = len(wa_labels) > 1

            cells = [
                hazard.get("hazard_type_text", ""),
                hazard.get("category", ""),
                risk,
                hazard.get("likelihood", ""),
                hazard.get("severity", ""),
                hazard.get("control_measure", "") or hazard.get("mitigation_text", ""),
                hazard.get("ppe_text", ""),
                "Yes" if hazard.get("is_resolved") else "No",
                ", ".join(wa_labels),
            ]

            for c, text in enumerate(cells):
                item = _risk_item(text, risk) if c == 2 else _ro_item(text)
                # Highlight rows shared across multiple WAs with a subtle blue tint
                if shared and c != 2:
                    item.setBackground(QColor("#e3f2fd"))
                self._tbl.setItem(r, c, item)

        self._count_lbl.setText(
            f"{self._tbl.rowCount()} unique hazard{'s' if self._tbl.rowCount() != 1 else ''}"
            + (f"  ·  shared hazards highlighted in blue" if any(len(wa) > 1 for _, wa in rows) else "")
        )


# ---------------------------------------------------------------------------
# By-Assignment view (right pane — scrollable list of per-WA tables)
# ---------------------------------------------------------------------------

_WA_COLS = [
    "Hazard",
    "Category",
    "Risk",
    "Likelihood",
    "Severity",
    "Control Measure",
    "PPE",
    "Resolved",
]


class _ByAssignmentWidget(QScrollArea):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        self.setWidget(self._container)

    def load(self, wa_groups: List[Tuple[dict, List[dict]]]) -> None:
        """wa_groups: list of (wa_dict, [hazard_dict, ...])"""
        # Clear existing children
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not wa_groups:
            lbl = QLabel("No work assignments with hazards found for this op period.")
            lbl.setStyleSheet("color: #9e9e9e; font-size: 12px; padding: 12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._layout.insertWidget(0, lbl)
            return

        for idx, (wa, hazards) in enumerate(wa_groups):
            label = _wa_label(wa)

            # Group header
            header = QWidget()
            header.setStyleSheet(
                "background: #c5cae9; border-left: 4px solid #3949ab; padding: 2px 0px;"
            )
            hrow = QHBoxLayout(header)
            hrow.setContentsMargins(8, 4, 8, 4)
            title_lbl = QLabel(label)
            font = QFont()
            font.setBold(True)
            title_lbl.setFont(font)
            title_lbl.setStyleSheet("color: #1a237e;")
            hrow.addWidget(title_lbl)
            hrow.addStretch()
            count_lbl = QLabel(f"{len(hazards)} hazard{'s' if len(hazards) != 1 else ''}")
            count_lbl.setStyleSheet("color: #5c6bc0; font-size: 11px;")
            hrow.addWidget(count_lbl)
            self._layout.insertWidget(self._layout.count() - 1, header)

            if not hazards:
                none_lbl = QLabel("  No hazards recorded.")
                none_lbl.setStyleSheet("color: #9e9e9e; font-size: 11px; padding: 4px 8px;")
                self._layout.insertWidget(self._layout.count() - 1, none_lbl)
                continue

            tbl = QTableWidget(0, len(_WA_COLS))
            tbl.setHorizontalHeaderLabels(_WA_COLS)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            tbl.setSelectionBehavior(QTableWidget.SelectRows)
            tbl.setAlternatingRowColors(True)
            tbl.horizontalHeader().setStretchLastSection(True)
            tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            tbl.verticalHeader().setVisible(False)
            tbl.setStyleSheet("font-size: 12px;")

            for hazard in hazards:
                r = tbl.rowCount()
                tbl.insertRow(r)
                risk = hazard.get("risk_level", "Unknown")
                cells = [
                    hazard.get("hazard_type_text", ""),
                    hazard.get("category", ""),
                    risk,
                    hazard.get("likelihood", ""),
                    hazard.get("severity", ""),
                    hazard.get("control_measure", "") or hazard.get("mitigation_text", ""),
                    hazard.get("ppe_text", ""),
                    "Yes" if hazard.get("is_resolved") else "No",
                ]
                for c, text in enumerate(cells):
                    tbl.setItem(r, c, _risk_item(text, risk) if c == 2 else _ro_item(text))

            # Size table to content without internal scroll
            tbl.setMinimumHeight(tbl.horizontalHeader().height() + len(hazards) * 26 + 4)
            tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            self._layout.insertWidget(self._layout.count() - 1, tbl)

            if idx < len(wa_groups) - 1:
                self._layout.insertWidget(self._layout.count() - 1, _divider())


# ---------------------------------------------------------------------------
# Canonical hazard register view (Safety Risk Manager)
# ---------------------------------------------------------------------------

_CANONICAL_COLS = [
    "Title",
    "Category",
    "Op Period(s)",
    "Initial SPE",
    "Residual SPE",
    "Linked Work Assignments",
]


class _CanonicalRegisterTable(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._count_lbl = QLabel("0 hazards")
        self._count_lbl.setStyleSheet("font-size: 11px; color: #546e7a;")
        layout.addWidget(self._count_lbl)

        self._tbl = QTableWidget(0, len(_CANONICAL_COLS))
        self._tbl.setHorizontalHeaderLabels(_CANONICAL_COLS)
        self._tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self._tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.horizontalHeader().setStretchLastSection(True)
        self._tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._tbl, 1)

    def load(self, hazards: List[dict], wa_labels_by_id: Dict[int, str]) -> None:
        self._tbl.setRowCount(0)
        for hazard in hazards:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)

            initial = hazard.get("spe_initial") or {}
            residual = hazard.get("spe_residual") or {}
            initial_degree = initial.get("band", "")
            residual_degree = residual.get("band", "")
            initial_text = f"{initial['score']} — {initial_degree}" if initial else "Not assessed"
            residual_text = f"{residual['score']} — {residual_degree}" if residual else "Not assessed"

            links = hazard.get("links") or {}
            wa_ids = links.get("work_assignment_ids") or []
            wa_text = ", ".join(wa_labels_by_id.get(wid, str(wid)) for wid in wa_ids)

            cells = [
                (hazard.get("title", ""), None),
                (hazard.get("category", ""), None),
                (", ".join(str(op) for op in hazard.get("op_period_ids") or []), None),
                (initial_text, initial_degree),
                (residual_text, residual_degree),
                (wa_text, None),
            ]
            for c, (text, degree) in enumerate(cells):
                item = _spe_item(text, degree) if degree else _ro_item(text)
                self._tbl.setItem(r, c, item)

        self._count_lbl.setText(
            f"{self._tbl.rowCount()} hazard{'s' if self._tbl.rowCount() != 1 else ''}"
        )


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

class ICS215APanel(QWidget):
    """Incident Action Safety Analysis — cross-cutting hazard dashboard."""

    def __init__(self, incident_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._build_ui()
        if incident_id:
            self._load()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Header bar ----
        header_bar = QWidget()
        header_bar.setStyleSheet("background: #e8eaf6; padding: 6px;")
        hrow = QHBoxLayout(header_bar)
        hrow.setContentsMargins(12, 6, 12, 6)

        title = QLabel("Incident Action Safety Analysis (ICS-215A)")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1a237e;")
        hrow.addWidget(title)
        hrow.addStretch()

        # View toggle buttons
        self._btn_consolidated = QPushButton("Consolidated")
        self._btn_by_assignment = QPushButton("By Assignment")
        self._btn_canonical = QPushButton("Canonical Register")
        for btn in (self._btn_consolidated, self._btn_by_assignment, self._btn_canonical):
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                "QPushButton { border: 1px solid #9fa8da; padding: 2px 14px;"
                " background: #fff; color: #1a237e; font-weight: 600; }"
                "QPushButton:checked { background: #3949ab; color: #fff; border-color: #3949ab; }"
                "QPushButton:first-child { border-radius: 3px 0 0 3px; }"
                "QPushButton:last-child  { border-radius: 0 3px 3px 0; }"
            )
        self._btn_consolidated.setChecked(True)
        self._btn_consolidated.clicked.connect(lambda: self._switch_view("consolidated"))
        self._btn_by_assignment.clicked.connect(lambda: self._switch_view("by_assignment"))
        self._btn_canonical.clicked.connect(lambda: self._switch_view("canonical"))
        hrow.addWidget(self._btn_consolidated)
        hrow.addWidget(self._btn_by_assignment)
        hrow.addWidget(self._btn_canonical)

        hrow.addSpacing(16)
        hrow.addWidget(QLabel("Op Period:"))
        self._op_spin = QSpinBox()
        self._op_spin.setRange(0, 99)
        self._op_spin.setSpecialValueText("All")
        self._op_spin.setValue(0)
        self._op_spin.setFixedWidth(70)
        self._op_spin.setToolTip("0 = show all op periods")
        hrow.addWidget(self._op_spin)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setStyleSheet(
            "background: #3949ab; color: white; font-weight: 600;"
            "padding: 4px 14px; border-radius: 3px;"
        )
        self._refresh_btn.clicked.connect(self._load)
        hrow.addWidget(self._refresh_btn)

        outer.addWidget(header_bar)

        # Status strip
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            "color: #546e7a; font-size: 11px; padding: 2px 14px;"
            "background: #fafafa; border-bottom: 1px solid #e0e0e0;"
        )
        self._status_lbl.setAlignment(Qt.AlignRight)
        outer.addWidget(self._status_lbl)

        # ---- Stacked views ----
        self._stack = QStackedWidget()

        self._consolidated_tbl = _ConsolidatedTable()
        self._stack.addWidget(self._consolidated_tbl)   # index 0

        self._by_assignment_wgt = _ByAssignmentWidget()
        self._stack.addWidget(self._by_assignment_wgt)  # index 1

        self._canonical_tbl = _CanonicalRegisterTable()
        self._stack.addWidget(self._canonical_tbl)      # index 2

        self._stack.setCurrentIndex(0)
        outer.addWidget(self._stack, 1)

    def _switch_view(self, view: str) -> None:
        index = {"consolidated": 0, "by_assignment": 1, "canonical": 2}[view]
        self._stack.setCurrentIndex(index)
        self._btn_consolidated.setChecked(view == "consolidated")
        self._btn_by_assignment.setChecked(view == "by_assignment")
        self._btn_canonical.setChecked(view == "canonical")

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _fetch_was(self) -> List[dict]:
        op = self._op_spin.value()
        params: dict = {}
        if op > 0:
            params["op_period_id"] = op
        try:
            result = api_client.get(
                f"/api/incidents/{self._incident_id}/planning/work-assignments",
                params=params,
            )
            return result or []
        except Exception:
            return []

    def _fetch_hazards(self) -> List[dict]:
        op = self._op_spin.value()
        params: dict = {}
        if op > 0:
            params["op_period"] = op
        try:
            result = api_client.get(
                f"/api/incidents/{self._incident_id}/safety/hazards",
                params=params,
            )
            return result or []
        except Exception:
            return []

    def _load(self) -> None:
        if not self._incident_id:
            return

        self._status_lbl.setText("Loading…")
        was = self._fetch_was()

        # Filter out archived
        was = [w for w in was if not w.get("is_archived")]

        # Build consolidated dedup map: key → (hazard, [wa_labels])
        dedup: Dict[str, Tuple[dict, List[str]]] = {}
        # Build by-assignment list: [(wa, [hazards])]
        by_wa: List[Tuple[dict, List[dict]]] = []

        for wa in was:
            hazards = [h for h in (wa.get("hazards") or []) if not h.get("is_resolved", False) is True]
            # Include all hazards (resolved and unresolved) — resolved shown as "Yes"
            hazards = wa.get("hazards") or []
            wa_lbl = _wa_label(wa)
            by_wa.append((wa, hazards))

            for h in hazards:
                key = _dedup_key(h)
                if key not in dedup:
                    dedup[key] = (h, [wa_lbl])
                else:
                    existing_labels = dedup[key][1]
                    if wa_lbl not in existing_labels:
                        existing_labels.append(wa_lbl)

        # Sort consolidated: Extreme first, then High, Medium, Low, Unknown
        risk_order = {"Extreme": 0, "High": 1, "Medium": 2, "Low": 3, "Unknown": 4}
        consolidated_rows = sorted(
            dedup.values(),
            key=lambda t: (risk_order.get(t[0].get("risk_level", "Unknown"), 4), t[0].get("hazard_type_text", "").lower()),
        )

        self._consolidated_tbl.load(consolidated_rows)
        self._by_assignment_wgt.load(by_wa)

        wa_labels_by_id: Dict[int, str] = {}
        for wa in was:
            wa_id = wa.get("id")
            if wa_id is not None:
                wa_labels_by_id[int(wa_id)] = _wa_label(wa)

        canonical_hazards = sorted(
            self._fetch_hazards(),
            key=lambda h: _SPE_ORDER.get(((h.get("spe_residual") or {}).get("band")), 5),
        )
        self._canonical_tbl.load(canonical_hazards, wa_labels_by_id)

        total_hazards = sum(len(w.get("hazards") or []) for w in was)
        unique = len(dedup)
        self._status_lbl.setText(
            f"{len(was)} assignment{'s' if len(was) != 1 else ''}  ·  "
            f"{total_hazards} total hazard record{'s' if total_hazards != 1 else ''}  ·  "
            f"{unique} unique  ·  "
            f"{len(canonical_hazards)} in canonical register"
        )
