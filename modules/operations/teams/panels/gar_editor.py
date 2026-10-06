"""
GarAssessmentEditor
====================
GAR (Green-Amber-Red) risk assessment editor for one Team, scored against an
admin-editable template (``modules/admin/gar_templates/``) rather than a
fixed set of factors.

GAR is scored per team, not per task — a task can carry multiple teams,
each with its own risk posture, so this widget lives on the Team Detail
window rather than the Task Detail window. Every save appends a new
assessment (it never overwrites), which is how "assess once at the start of
the operational period, reassess if conditions change" falls out naturally:
"current" is just the most recent entry, and every prior one stays in
history. The Task Detail window's Safety tab shows a read-only roll-up of
each linked team's current band, pointing back here for the actual edit.

Score/band/required_reviewer/operational_period_id are always computed
server-side (see ``save_team_gar`` in
``data/db/sarapp_db/api/routers/operations.py``); the live score shown here
while editing is a local preview only and is recomputed authoritatively on
save.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from modules.operations.teams.data.gar import GarAssessment
from utils.styles import get_palette, subscribe_theme

_BAND_PALETTE_TOKEN = {
    "Green": "success",
    "Amber": "warning",
    "Red": "danger",
    "No-Go": "danger",
}


def _band_color_hex(band: str) -> str:
    token = _BAND_PALETTE_TOKEN.get(band, "ctrl_border")
    return get_palette().get(token, get_palette().get("ctrl_border")).name()


def _incident_id() -> str | None:
    try:
        from utils.incident_context import get_active_incident_id

        value = get_active_incident_id()
    except Exception:
        value = None
    return str(value) if value else None


def _preview_band(template: dict[str, Any], score: int, no_go: bool) -> tuple[str, str]:
    """Mirrors score_selections' band logic in gar_templates.py for a live
    preview; the server recomputes this authoritatively on save."""
    bands = sorted(template.get("bands") or [], key=lambda b: -int(b.get("floor", 0)))
    if not bands:
        return "", ""
    if no_go:
        return "No-Go", bands[0].get("required_reviewer", "")
    chosen = bands[-1]
    for band in bands:
        if score >= int(band.get("floor", 0)):
            chosen = band
            break
    return chosen.get("label", ""), chosen.get("required_reviewer", "")


class GarAssessmentEditor(QWidget):
    """Editor + history view for a team's GAR risk assessment.

    Signals:
        changed() - emitted after a new assessment is saved.
    """

    changed = Signal()

    def __init__(self, team_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._team_id = int(team_id)
        self._current: Optional[GarAssessment] = None
        self._history: list[GarAssessment] = []
        self._templates: list[dict[str, Any]] = []
        self._active_template: Optional[dict[str, Any]] = None
        self._row_combos: dict[tuple[str, str], QComboBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QLabel("GAR Risk Assessment", self)
        header.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(header)

        self._current_banner = QFrame(self)
        self._current_banner.setFrameShape(QFrame.StyledPanel)
        self._current_banner.setAttribute(Qt.WA_StyledBackground, True)
        banner_layout = QHBoxLayout(self._current_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self._current_label = QLabel("Not yet assessed", self._current_banner)
        self._current_label.setStyleSheet("font-weight: 700;")
        banner_layout.addWidget(self._current_label)
        banner_layout.addStretch(1)
        layout.addWidget(self._current_banner)

        template_row = QHBoxLayout()
        template_row.addWidget(QLabel("Template:", self))
        self._template_combo = QComboBox(self)
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)
        template_row.addWidget(self._template_combo, 1)
        layout.addLayout(template_row)

        self._rows_scroll = QScrollArea(self)
        self._rows_scroll.setWidgetResizable(True)
        self._rows_scroll.setFrameShape(QFrame.NoFrame)
        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(10)
        self._rows_scroll.setWidget(self._rows_container)
        layout.addWidget(self._rows_scroll, 1)

        self._preview_label = QLabel("", self)
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        notes_label = QLabel("Notes / mitigations:", self)
        layout.addWidget(notes_label)
        self._notes_edit = QPlainTextEdit(self)
        self._notes_edit.setFixedHeight(60)
        layout.addWidget(self._notes_edit)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        self._save_btn = QPushButton("Record Assessment", self)
        self._save_btn.setToolTip("Always adds a new assessment; prior assessments stay in history below.")
        self._save_btn.clicked.connect(self._save)
        btn_bar.addWidget(self._save_btn)
        layout.addLayout(btn_bar)

        history_header = QLabel("Assessment History", self)
        history_header.setStyleSheet("font-weight: 600;")
        layout.addWidget(history_header)
        self._history_label = QLabel("No prior assessments.", self)
        self._history_label.setWordWrap(True)
        layout.addWidget(self._history_label)

        try:
            subscribe_theme(self, lambda _name: self._refresh_banner())
        except Exception:
            pass

    # ---- Loading ----

    def reload(self) -> None:
        incident_id = _incident_id()
        if not incident_id:
            self._current = None
            self._history = []
            self._templates = []
            self._refresh_banner()
            self._refresh_history()
            self._rebuild_template_combo()
            return

        from modules.admin.gar_templates.data import gar_template_repository as template_repo
        from modules.operations.teams.data.repository import get_team_gar

        try:
            self._templates = template_repo.list_gar_templates(include_inactive=False)
        except Exception as exc:
            QMessageBox.critical(self, "GAR Assessment", f"Failed to load GAR templates:\n{exc}")
            self._templates = []

        try:
            payload = get_team_gar(self._team_id)
        except Exception as exc:
            QMessageBox.critical(self, "GAR Assessment", f"Failed to load GAR assessment:\n{exc}")
            payload = {"current": None, "history": []}

        current = payload.get("current")
        self._current = GarAssessment.from_dict(current) if current else None
        self._history = [GarAssessment.from_dict(item) for item in (payload.get("history") or [])]

        default_template_id = None
        try:
            default_template_id = template_repo.get_incident_default_gar_template(incident_id)
        except Exception:
            default_template_id = None

        preselect_id = (self._current.template_id if self._current else None) or default_template_id
        self._rebuild_template_combo(preselect_id)
        if self._current:
            self._notes_edit.setPlainText(self._current.notes)
        self._refresh_banner()
        self._refresh_history()

    def _rebuild_template_combo(self, preselect_id: int | None = None) -> None:
        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        for template in self._templates:
            self._template_combo.addItem(template.get("name") or f"Template {template.get('id')}", template.get("id"))
        self._template_combo.blockSignals(False)
        if not self._templates:
            self._active_template = None
            self._build_rows(None)
            return
        index = 0
        if preselect_id is not None:
            found = self._template_combo.findData(preselect_id)
            if found >= 0:
                index = found
        self._template_combo.setCurrentIndex(index)
        self._on_template_changed(index)

    def _on_template_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._templates):
            self._active_template = None
            self._build_rows(None)
            return
        self._active_template = self._templates[index]
        preselected = (
            self._current.selections
            if self._current and self._current.template_id == self._active_template.get("id")
            else []
        )
        self._build_rows(self._active_template, preselected)

    # ---- Dynamic row rendering ----

    def _build_rows(self, template: Optional[dict[str, Any]], preselected: list | None = None) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._row_combos = {}

        if not template:
            empty = QLabel("No GAR templates available. Create one from the Edit menu's GAR Template Library.", self)
            empty.setWordWrap(True)
            self._rows_layout.addWidget(empty)
            self._update_preview()
            return

        preselected_by_row = {(sel.group_id, sel.row_id): sel.option_id for sel in (preselected or [])}

        for group in template.get("groups") or []:
            group_label = QLabel(group.get("name") or "", self)
            group_label.setStyleSheet("font-weight: 700;")
            self._rows_layout.addWidget(group_label)
            for row in group.get("rows") or []:
                row_widget = QWidget(self)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(12, 0, 0, 0)
                row_layout.addWidget(QLabel(row.get("label") or "", row_widget), 1)
                combo = QComboBox(row_widget)
                for option in row.get("options") or []:
                    suffix = " [No-Go]" if option.get("no_go") else f" ({option.get('points', 0)} pts)"
                    combo.addItem(f"{option.get('label', '')}{suffix}", option.get("id"))
                key = (group["id"], row["id"])
                preselected_option = preselected_by_row.get(key)
                if preselected_option:
                    found = combo.findData(preselected_option)
                    if found >= 0:
                        combo.setCurrentIndex(found)
                combo.currentIndexChanged.connect(self._update_preview)
                self._row_combos[key] = combo
                row_layout.addWidget(combo)
                self._rows_layout.addWidget(row_widget)

        self._rows_layout.addStretch(1)
        self._update_preview()

    def _current_selections(self) -> list[dict[str, Any]]:
        selections = []
        for (group_id, row_id), combo in self._row_combos.items():
            option_id = combo.currentData()
            if option_id is None:
                continue
            selections.append({"group_id": group_id, "row_id": row_id, "option_id": option_id})
        return selections

    def _update_preview(self, *_args) -> None:
        if not self._active_template:
            self._preview_label.setText("")
            return
        row_index: dict[tuple[str, str], dict[str, Any]] = {}
        for group in self._active_template.get("groups") or []:
            for row in group.get("rows") or []:
                row_index[(group["id"], row["id"])] = row

        total = 0
        no_go = False
        for key, combo in self._row_combos.items():
            option_id = combo.currentData()
            row = row_index.get(key)
            if not row or option_id is None:
                continue
            option = next((o for o in row.get("options") or [] if o["id"] == option_id), None)
            if option is None:
                continue
            total += int(option.get("points") or 0)
            no_go = no_go or bool(option.get("no_go"))

        band, _reviewer = _preview_band(self._active_template, total, no_go)
        self._preview_label.setText(f"Preview score: {total} ({band}) — recomputed on save.")

    # ---- Banner / history ----

    def _refresh_banner(self) -> None:
        if not self._current:
            self._current_label.setText("Not yet assessed")
            self._current_banner.setStyleSheet(
                f"QFrame {{ border:1px solid {get_palette().get('ctrl_border').name()}; border-radius:6px; }}"
            )
            return
        color = _band_color_hex(self._current.band)
        op_suffix = f" (OP {self._current.operational_period_id})" if self._current.operational_period_id else ""
        self._current_label.setText(
            f"{self._current.band} — Score {self._current.score}{op_suffix} "
            f"— Review: {self._current.required_reviewer or 'n/a'} "
            f"({self._current.template_name})"
        )
        self._current_banner.setStyleSheet(
            "QFrame { "
            f"background:{color}; "
            f"border:1px solid {color}; "
            "border-radius:6px; "
            "}"
        )

    def _refresh_history(self) -> None:
        if not self._history:
            self._history_label.setText("No prior assessments.")
            return
        lines = []
        for item in reversed(self._history):
            who = f" by {item.assessed_by}" if item.assessed_by else ""
            op_suffix = f", OP {item.operational_period_id}" if item.operational_period_id else ""
            lines.append(f"{item.assessed_at}: {item.band} (score {item.score}{op_suffix}, {item.template_name}){who}")
        self._history_label.setText("\n".join(lines))

    # ---- Save ----

    def _save(self) -> None:
        if not _incident_id():
            QMessageBox.information(self, "GAR Assessment", "Select an incident first.")
            return
        if not self._active_template:
            QMessageBox.information(self, "GAR Assessment", "No GAR template selected.")
            return
        selections = self._current_selections()
        expected_rows = sum(len(group.get("rows") or []) for group in self._active_template.get("groups") or [])
        if len(selections) != expected_rows:
            QMessageBox.warning(self, "GAR Assessment", "Please answer every row before recording the assessment.")
            return
        notes = self._notes_edit.toPlainText().strip()
        from modules.operations.teams.data.repository import save_team_gar

        try:
            save_team_gar(self._team_id, int(self._active_template["id"]), selections, notes=notes)
        except Exception as exc:
            QMessageBox.critical(self, "GAR Assessment", f"Failed to save GAR assessment:\n{exc}")
            return
        self.reload()
        self.changed.emit()
