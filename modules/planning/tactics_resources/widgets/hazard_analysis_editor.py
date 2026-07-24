"""
HazardAnalysisEditor
====================
ICS 215A-style hazard view for one Work Assignment.

This widget does not own a separate hazard store. It shows canonical incident
hazards filtered by their work-assignment link and opens the reusable Incident
Hazard Detail Window for create/edit.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from modules.safety.orm import service as hazard_service
from modules.safety.orm.models import Hazard
from modules.safety.orm.ui.incident_hazard_detail_window import IncidentHazardDetailWindow
from utils.styles import get_palette, subscribe_theme

_SPE_PALETTE_TOKEN = {
    "Slight": "success",
    "Possible": "warning",
    "Substantial": "warning",
    "High": "danger",
    "Very High": "danger",
}


def _incident_id() -> str | None:
    try:
        from utils.incident_context import get_active_incident_id

        value = get_active_incident_id()
    except Exception:
        value = None
    return str(value) if value else None


def _join_ids(values: list[int]) -> str:
    return ", ".join(str(value) for value in values) if values else ""


def _spe_text(assessment) -> str:
    if not assessment:
        return "Not assessed"
    return f"{assessment.score} - {assessment.band}"


def _spe_band(assessment) -> str:
    if not assessment:
        return "Not assessed"
    return assessment.band or "Not assessed"


class HazardAnalysisEditor(QWidget):
    """
    Displays incident hazards linked to one Work Assignment.

    Signals:
        changed() - emitted after any add/update/unlink operation.
    """

    changed = Signal()

    def __init__(
        self,
        work_assignment_id: int,
        db_path: str | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._work_assignment_id = int(work_assignment_id)
        self._db_path = db_path
        self._hazards: list[Hazard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        btn_bar = QHBoxLayout()
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        self._add_btn = QPushButton("Add Hazard")
        btn_bar.addWidget(self._summary_label)
        btn_bar.addStretch(1)
        btn_bar.addWidget(self._add_btn)
        layout.addLayout(btn_bar)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._card_container = QWidget()
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(8)
        self._card_layout.addStretch(1)
        self._scroll.setWidget(self._card_container)
        layout.addWidget(self._scroll, 1)

        self._add_btn.clicked.connect(self._add_hazard)

        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            self.reload()

    def _on_theme_changed(self, _name: str) -> None:
        self.reload()

    def reload(self) -> None:
        incident_id = _incident_id()
        if not incident_id:
            self._hazards = []
            self._refresh_cards()
            return
        try:
            self._hazards = hazard_service.list_hazards(
                incident_id,
                work_assignment_id=self._work_assignment_id,
            )
        except Exception as exc:
            QMessageBox.critical(self, "ICS 215A Hazards", f"Failed to load hazards:\n{exc}")
            return
        self._refresh_cards()

    def _refresh_cards(self) -> None:
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        high_count = sum(1 for hazard in self._hazards if _spe_band(hazard.default_spe) in ("High", "Very High"))
        mitigated_count = sum(1 for hazard in self._hazards if _spe_band(hazard.spe_residual) in ("Slight", "Possible"))
        self._summary_label.setText(
            f"{len(self._hazards)} linked hazards | {high_count} high risk | {mitigated_count} mitigated"
        )
        if not self._hazards:
            empty = QLabel("No hazards linked to this strategy.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{get_palette().get('fg_muted').name()}; padding:24px;")
            self._card_layout.insertWidget(0, empty)
            return
        for hazard in self._hazards:
            self._card_layout.insertWidget(self._card_layout.count() - 1, self._build_card(hazard))

    def _build_card(self, hazard: Hazard) -> QFrame:
        card = QFrame(self._card_container)
        card.setFrameShape(QFrame.StyledPanel)
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setContextMenuPolicy(Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos, h=hazard, c=card: self._show_hazard_context_menu(h, c, pos))
        card.mouseDoubleClickEvent = lambda _event, h=hazard: self._edit_hazard(h)  # type: ignore[method-assign]

        initial_band = _spe_band(hazard.default_spe)
        token = _SPE_PALETTE_TOKEN.get(initial_band, "ctrl_border")
        border = get_palette().get(token, get_palette().get("ctrl_border")).name()
        card.setStyleSheet(
            "QFrame { "
            f"background:{get_palette().get('bg_raised').name()}; "
            f"border:1px solid {get_palette().get('ctrl_border').name()}; "
            f"border-left:4px solid {border}; "
            "border-radius:6px; "
            "}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        header = QHBoxLayout()
        title = QLabel(hazard.title)
        title.setStyleSheet("font-weight:700;")
        header.addWidget(title, 1)
        badge = QLabel(initial_band)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{border}; color:{get_palette().get('fg').name()}; "
            "padding:2px 8px; border-radius:4px; font-weight:700;"
        )
        header.addWidget(badge)
        layout.addLayout(header)

        detail_bits = [part for part in (hazard.category, f"Initial SPE: {_spe_text(hazard.default_spe)}", f"Residual SPE: {_spe_text(hazard.spe_residual)}") if part]
        detail = QLabel(" | ".join(detail_bits))
        detail.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        layout.addWidget(detail)

        if hazard.control_measure:
            layout.addWidget(QLabel(f"<b>Control measure:</b> {hazard.control_measure}"))
        if hazard.mitigation_text:
            layout.addWidget(QLabel(f"<b>Mitigation:</b> {hazard.mitigation_text}"))
        if hazard.ppe_text:
            layout.addWidget(QLabel(f"<b>PPE:</b> {hazard.ppe_text}"))
        if hazard.safety_message:
            layout.addWidget(QLabel(f"<b>Safety message:</b> {hazard.safety_message}"))
        return card

    def _show_hazard_context_menu(self, hazard: Hazard, card: QFrame, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Open Detail", lambda: self._edit_hazard(hazard))
        menu.addAction("Unlink From Strategy", lambda: self._unlink_hazard(hazard))
        menu.exec(card.mapToGlobal(pos))

    def _add_hazard(self) -> None:
        incident_id = _incident_id()
        if not incident_id:
            QMessageBox.information(self, "ICS 215A Hazards", "Select an incident first.")
            return
        dialog = IncidentHazardDetailWindow(
            incident_id,
            self,
            default_work_assignment_id=self._work_assignment_id,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.result_payload()
        if not payload:
            return
        links = payload.setdefault("links", {})
        work_assignment_ids = list(links.get("work_assignment_ids") or [])
        if self._work_assignment_id not in work_assignment_ids:
            work_assignment_ids.append(self._work_assignment_id)
        links["work_assignment_ids"] = work_assignment_ids
        try:
            hazard_service.create_hazard(incident_id, payload)
        except Exception as exc:
            QMessageBox.critical(self, "Add Hazard", f"Failed to add hazard:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _edit_hazard(self, hazard: Hazard | None = None) -> None:
        incident_id = _incident_id()
        if hazard is None:
            return
        if not incident_id:
            return
        dialog = IncidentHazardDetailWindow(incident_id, self, hazard=asdict(hazard))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.result_payload()
        if not payload:
            return
        links = payload.setdefault("links", {})
        work_assignment_ids = list(links.get("work_assignment_ids") or [])
        if self._work_assignment_id not in work_assignment_ids:
            work_assignment_ids.append(self._work_assignment_id)
        links["work_assignment_ids"] = work_assignment_ids
        try:
            hazard_service.update_hazard(incident_id, hazard.id, payload)
        except Exception as exc:
            QMessageBox.critical(self, "Incident Hazard Detail", f"Failed to update hazard:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _unlink_hazard(self, hazard: Hazard | None = None) -> None:
        incident_id = _incident_id()
        if hazard is None:
            return
        if not incident_id:
            return
        if (
            QMessageBox.question(
                self,
                "Unlink Hazard",
                "Unlink this hazard from the strategy? The hazard will remain in the incident register.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        links = asdict(hazard.links)
        links["work_assignment_ids"] = [
            value for value in links.get("work_assignment_ids", []) if int(value) != self._work_assignment_id
        ]
        try:
            hazard_service.update_hazard(incident_id, hazard.id, {"links": links})
        except Exception as exc:
            QMessageBox.critical(self, "Unlink Hazard", f"Failed to unlink hazard:\n{exc}")
            return
        self.reload()
        self.changed.emit()
