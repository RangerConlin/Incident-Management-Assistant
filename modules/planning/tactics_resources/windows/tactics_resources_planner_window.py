"""
TacticsResourcesPlannerWindow
=============================
Main board window for the Tactics and Resources Planner.

Shows all strategies as contained row cards. Double-click a card to open the
strategy detail window; secondary actions live in the card context menu.

Accessible from: Planning, Operations, and Logistics menus.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from modules.planning.tactics_resources.models.work_assignment_models import (
    PLANNING_STATUS_VALUES,
    RESOURCE_STATUS_VALUES,
    SAFETY_STATUS_VALUES,
    WorkAssignment,
)
from modules.planning.tactics_resources.windows.work_assignment_detail_window import (
    WorkAssignmentDetailWindow,
)
from utils.styles import (
    get_palette,
    resource_status_colors,
    subscribe_theme,
    wa_planning_status_colors,
    wa_safety_status_colors,
)


_Meta = tuple[int, int, int, int, int, int]
_EMPTY_META: _Meta = (0, 0, 0, 0, 0, 0)
_NEEDS_ACTION_PLANNING = {"Draft", "Under Review"}
_NEEDS_ACTION_SAFETY = {"Needs Review", "Hazards Identified", "Safety Concern"}


def _color_name(key: str, fallback: str = "ctrl_border") -> str:
    pal = get_palette()
    color = pal.get(key) or pal.get(fallback)
    return color.name() if color is not None else ""


def _chip(text: str, brushes: dict[str, Any] | None, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setAlignment(Qt.AlignCenter)
    label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    if brushes:
        bg = brushes["bg"].color().name()
        fg = brushes["fg"].color().name()
        label.setStyleSheet(
            f"background:{bg}; color:{fg}; padding:2px 8px; "
            "border-radius:4px; font-weight:700;"
        )
    else:
        label.setStyleSheet("padding:2px 8px; font-weight:700;")
    return label


def _metric_label(label: str, value: str, alert: bool = False) -> QLabel:
    widget = QLabel(f"<b>{label}</b>  {value}")
    widget.setTextFormat(Qt.RichText)
    widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    if alert:
        widget.setStyleSheet(f"color:{_color_name('danger')};")
    else:
        widget.setStyleSheet(f"color:{_color_name('fg')};")
    return widget


def _format_display_timestamp(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.replace("T", " ")
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        if "." in normalized:
            normalized = normalized.split(".", 1)[0]
        return normalized[:19]
    return f"{dt:%b} {dt.day}, {dt.year} {dt:%H:%M:%S}"


def _area_label(wa: WorkAssignment) -> str:
    parts = [part for part in (wa.branch, wa.division_group) if part]
    return " / ".join(parts) if parts else "No branch or division assigned"


def _has_resource_gap(meta: _Meta) -> bool:
    return meta[2] > 0


def _has_open_hazard(meta: _Meta) -> bool:
    return meta[4] > 0


def _needs_action(wa: WorkAssignment, meta: _Meta) -> bool:
    return (
        wa.planning_status in _NEEDS_ACTION_PLANNING
        or wa.safety_status in _NEEDS_ACTION_SAFETY
        or _has_resource_gap(meta)
        or _has_open_hazard(meta)
    )


def _stat_card(title: str) -> tuple[QFrame, QLabel, QLabel]:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setAttribute(Qt.WA_StyledBackground, True)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    frame.setFixedHeight(72)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(6, 8, 6, 8)
    layout.setSpacing(2)

    count = QLabel("0")
    count.setAlignment(Qt.AlignCenter)
    count.setStyleSheet("font-size:24px; font-weight:700; background:transparent;")
    name = QLabel(title)
    name.setAlignment(Qt.AlignCenter)
    name.setWordWrap(True)
    name.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")

    layout.addWidget(count)
    layout.addWidget(name)
    frame.setStyleSheet(
        "QFrame { "
        f"background-color:{_color_name('bg_raised')}; "
        f"border:1px solid {_color_name('ctrl_border')}; "
        "border-radius:6px; "
        "}"
    )
    return frame, count, name


def _tint_stat_card(card: tuple[QFrame, QLabel, QLabel], brushes: dict[str, Any] | None) -> None:
    frame, count_label, title_label = card
    if not brushes:
        frame.setStyleSheet(
            "QFrame { "
            f"background-color:{_color_name('bg_raised')}; "
            f"border:1px solid {_color_name('ctrl_border')}; "
            "border-radius:6px; "
            "}"
        )
        count_label.setStyleSheet("font-size:24px; font-weight:700; background:transparent;")
        title_label.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
        return

    bg = brushes["bg"].color().name()
    fg = brushes["fg"].color().name()
    frame.setStyleSheet(f"QFrame {{ background-color:{bg}; border-radius:6px; }}")
    count_label.setStyleSheet(
        f"font-size:24px; font-weight:700; background:transparent; color:{fg};"
    )
    title_label.setStyleSheet(
        f"font-size:11px; font-weight:600; background:transparent; color:{fg};"
    )


class _StrategyCard(QFrame):
    """One contained row card for a strategy summary."""

    opened = Signal(int)
    clone_requested = Signal(int)
    archive_requested = Signal(int)
    restore_requested = Signal(int)
    recalculate_requested = Signal(int)
    create_task_requested = Signal(int)
    link_task_requested = Signal(int)
    copy_requested = Signal(int)

    def __init__(
        self,
        wa: WorkAssignment,
        meta: _Meta,
        objective_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._wa = wa
        self._meta = meta
        self._objective_label = objective_label

        self.setFrameShape(QFrame.StyledPanel)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        wa = self._wa
        req_total, assigned_total, gap, hazard_total, open_hazards, task_count = self._meta

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        number = wa.assignment_number or f"Strategy {wa.id or ''}".strip()
        title = QLabel(f"{number}  {wa.assignment_name or '(Untitled Strategy)'}")
        title.setStyleSheet("font-weight:700; font-size:14px;")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header.addWidget(title, 1)
        header.addWidget(_chip(wa.planning_status, wa_planning_status_colors().get(wa.planning_status), self))
        header.addWidget(_chip(wa.resource_status, resource_status_colors().get(wa.resource_status), self))
        header.addWidget(_chip(wa.safety_status, wa_safety_status_colors().get(wa.safety_status), self))
        layout.addLayout(header)

        objective = QLabel(self._objective_label or "No objective linked")
        objective.setWordWrap(True)
        objective.setStyleSheet(f"color:{_color_name('fg')};")
        layout.addWidget(objective)

        assignment_row = QHBoxLayout()
        assignment_row.setSpacing(8)
        area = QLabel(_area_label(wa))
        area.setStyleSheet(f"color:{_color_name('muted')};")
        assignment_row.addWidget(area, 1)
        if wa.operational_period_id:
            op_label = QLabel(f"OP {wa.operational_period_id}")
            op_label.setStyleSheet(f"color:{_color_name('muted')}; font-weight:600;")
            assignment_row.addWidget(op_label)
        layout.addLayout(assignment_row)

        tactics_text = wa.tactics_summary or wa.description or ""
        if tactics_text:
            tactics = QLabel(f"Tactics: {tactics_text}")
            tactics.setWordWrap(True)
            tactics.setStyleSheet(f"color:{_color_name('muted')};")
            layout.addWidget(tactics)

        metrics = QHBoxLayout()
        metrics.setSpacing(18)
        metrics.addWidget(
            _metric_label(
                "Resources",
                f"{req_total} req / {assigned_total} assigned / Gap {gap}",
                alert=gap > 0,
            )
        )
        metrics.addWidget(
            _metric_label(
                "Hazards",
                f"{hazard_total} / {open_hazards} open",
                alert=open_hazards > 0,
            )
        )
        metrics.addWidget(_metric_label("Tasks", str(task_count)))
        if wa.updated_at:
            updated = QLabel(f"Updated {_format_display_timestamp(wa.updated_at)}")
            updated.setStyleSheet(f"color:{_color_name('muted')}; font-size:11px;")
            metrics.addStretch(1)
            metrics.addWidget(updated)
        else:
            metrics.addStretch(1)
        layout.addLayout(metrics)

    def _apply_style(self) -> None:
        wa = self._wa
        border_color = _color_name("ctrl_border")
        left_border = border_color
        if _has_open_hazard(self._meta) or wa.safety_status == "Safety Concern":
            left_border = _color_name("danger")
        elif _has_resource_gap(self._meta):
            brushes = resource_status_colors().get(wa.resource_status)
            if brushes:
                left_border = brushes["bg"].color().name()
            else:
                left_border = _color_name("danger")
        elif wa.planning_status == "Ready for IAP":
            brushes = wa_planning_status_colors().get(wa.planning_status)
            if brushes:
                left_border = brushes["bg"].color().name()

        opacity_rule = "color: palette(mid);" if wa.is_archived else ""
        self.setStyleSheet(
            "_StrategyCard { "
            f"background-color:{_color_name('bg_raised')}; "
            f"border:1px solid {border_color}; "
            f"border-left:4px solid {left_border}; "
            "border-radius:8px; "
            f"{opacity_rule}"
            "}"
        )

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and self._wa.id is not None:
            self.opened.emit(int(self._wa.id))
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, position) -> None:
        if self._wa.id is None:
            return
        assignment_id = int(self._wa.id)
        menu = QMenu(self)
        menu.addAction("Open / Edit", lambda: self.opened.emit(assignment_id))
        menu.addAction("Clone", lambda: self.clone_requested.emit(assignment_id))
        menu.addSeparator()
        if self._wa.is_archived:
            menu.addAction("Restore", lambda: self.restore_requested.emit(assignment_id))
        else:
            menu.addAction("Archive", lambda: self.archive_requested.emit(assignment_id))
        menu.addSeparator()
        menu.addAction("Recalculate Resource Gaps", lambda: self.recalculate_requested.emit(assignment_id))
        menu.addSeparator()
        menu.addAction("Create Operations Task", lambda: self.create_task_requested.emit(assignment_id))
        menu.addAction("Link Existing Task", lambda: self.link_task_requested.emit(assignment_id))
        menu.addSeparator()
        menu.addAction("Copy Strategy Summary", lambda: self.copy_requested.emit(assignment_id))
        menu.exec(self.mapToGlobal(position))


class TacticsResourcesPlannerWindow(QWidget):
    """
    Main planning board for strategies.

    Designed to be opened modeless (non-blocking).
    """

    def __init__(self, db_path: str | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tactics and Resources Planner")
        self.setWindowFlags(Qt.Window)
        self.setMinimumSize(1100, 650)
        self._db_path = db_path
        self._open_detail_windows: list[WorkAssignmentDetailWindow] = []
        self._assignments_cache: list[WorkAssignment] = []
        self._meta_by_id: dict[int, _Meta] = {}
        self._objective_labels: dict[str, str] = {}

        self._build_ui()
        self.reload()
        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass

    def _on_theme_changed(self, _name: str) -> None:
        self._render_stats()
        self._render_cards()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self._stat_cards: dict[str, tuple[QFrame, QLabel, QLabel]] = {}
        for key, title in [
            ("total", "TOTAL"),
            ("needs_action", "NEEDS ACTION"),
            ("resource_gaps", "RESOURCE GAPS"),
            ("safety_review", "SAFETY REVIEW"),
            ("ready", "READY FOR IAP"),
        ]:
            card, count, title_label = _stat_card(title)
            stats_row.addWidget(card)
            self._stat_cards[key] = (card, count, title_label)
        layout.addLayout(stats_row)

        layout.addWidget(self._build_filter_bar())
        layout.addWidget(self._build_toolbar())

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

    def _build_filter_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search strategies...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(lambda _text: self._render_cards())
        row.addWidget(QLabel("Search:"))
        row.addWidget(self._search_edit, 1)

        def _combo(placeholder: str, values: list[str]) -> QComboBox:
            combo = QComboBox()
            combo.addItem(placeholder)
            combo.addItems(values)
            combo.currentIndexChanged.connect(self.reload)
            return combo

        self._filter_status = _combo("All Statuses", PLANNING_STATUS_VALUES)
        self._filter_safety = _combo("All Safety", SAFETY_STATUS_VALUES)
        self._filter_resource = _combo("All Resources", RESOURCE_STATUS_VALUES)

        row.addWidget(QLabel("Status:"))
        row.addWidget(self._filter_status)
        row.addWidget(QLabel("Safety:"))
        row.addWidget(self._filter_safety)
        row.addWidget(QLabel("Resource:"))
        row.addWidget(self._filter_resource)

        self._show_archived = QCheckBox("Show Archived")
        self._show_archived.stateChanged.connect(self.reload)
        row.addWidget(self._show_archived)
        return bar

    def _build_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Planner")
        toolbar.setMovable(False)

        def _action(label: str, slot) -> QAction:
            action = QAction(label, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)
            return action

        _action("New Strategy", self._new_assignment)
        toolbar.addSeparator()
        _action("Refresh", self.reload)
        return toolbar

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_objective_labels(self) -> dict[str, str]:
        try:
            from utils import incident_context
            from utils.api_client import api_client

            iid = incident_context.get_active_incident_id()
            if not iid:
                return {}
            rows = api_client.get("/api/objectives", params={"incident_id": iid}) or []
        except Exception:
            return {}
        labels: dict[str, str] = {}
        for row in rows:
            code = row.get("code") or row.get("_id") or ""
            text = row.get("text") or ""
            labels[str(row.get("_id"))] = f"{code} - {text}" if text else code
        return labels

    def reload(self) -> None:
        """Reload strategies and render the card board."""
        filters: dict[str, Any] = {}
        if self._show_archived.isChecked():
            filters["show_archived"] = True
        status = self._filter_status.currentText()
        if status and status != self._filter_status.itemText(0):
            filters["planning_status"] = status
        safety = self._filter_safety.currentText()
        if safety and safety != self._filter_safety.itemText(0):
            filters["safety_status"] = safety
        resource = self._filter_resource.currentText()
        if resource and resource != self._filter_resource.itemText(0):
            filters["resource_status"] = resource

        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.initialize_schema()
            assignments = repo.list_work_assignments(filters)
        except Exception as exc:
            QMessageBox.critical(self, "Planner", f"Failed to load strategies:\n{exc}")
            return

        meta_by_id: dict[int, _Meta] = {}
        for wa in assignments:
            if wa.id is None:
                continue
            try:
                reqs = repo.list_resource_requirements(wa.id)
                hazards = repo.list_hazards(wa.id)
                links = repo.list_linked_tasks(wa.id)
            except Exception:
                reqs, hazards, links = [], [], []
            req_total = sum(r.quantity_required for r in reqs)
            assigned_total = sum(r.quantity_assigned for r in reqs)
            gap = sum(max(r.quantity_required - r.quantity_assigned, 0) for r in reqs)
            open_hazards = sum(1 for h in hazards if not h.is_resolved)
            meta_by_id[int(wa.id)] = (req_total, assigned_total, gap, len(hazards), open_hazards, len(links))

        self._assignments_cache = assignments
        self._meta_by_id = meta_by_id
        self._objective_labels = self._load_objective_labels()
        self._render_stats()
        self._render_cards()

    def _filtered_assignments(self) -> list[WorkAssignment]:
        needle = self._search_edit.text().strip().lower()
        if not needle:
            return list(self._assignments_cache)

        result: list[WorkAssignment] = []
        for wa in self._assignments_cache:
            objective = self._objective_labels.get(str(wa.objective_id), "")
            haystack = " ".join(
                [
                    wa.assignment_number,
                    wa.assignment_name,
                    objective,
                    wa.branch,
                    wa.division_group,
                    wa.location,
                    wa.description,
                    wa.tactics_summary,
                ]
            ).lower()
            if needle in haystack:
                result.append(wa)
        return result

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_stats(self) -> None:
        rows = self._assignments_cache
        total = len(rows)
        needs_action = 0
        resource_gaps = 0
        safety_review = 0
        ready = 0
        for wa in rows:
            meta = self._meta_by_id.get(int(wa.id or 0), _EMPTY_META)
            if _needs_action(wa, meta):
                needs_action += 1
            if _has_resource_gap(meta):
                resource_gaps += 1
            if wa.safety_status in _NEEDS_ACTION_SAFETY or _has_open_hazard(meta):
                safety_review += 1
            if wa.planning_status == "Ready for IAP":
                ready += 1

        values = {
            "total": total,
            "needs_action": needs_action,
            "resource_gaps": resource_gaps,
            "safety_review": safety_review,
            "ready": ready,
        }
        for key, value in values.items():
            self._stat_cards[key][1].setText(str(value))

        _tint_stat_card(self._stat_cards["total"], None)
        _tint_stat_card(
            self._stat_cards["needs_action"],
            wa_safety_status_colors().get("Safety Concern") if needs_action else None,
        )
        _tint_stat_card(
            self._stat_cards["resource_gaps"],
            resource_status_colors().get("Gap Exists") if resource_gaps else None,
        )
        _tint_stat_card(
            self._stat_cards["safety_review"],
            wa_safety_status_colors().get("Needs Review") if safety_review else None,
        )
        _tint_stat_card(
            self._stat_cards["ready"],
            wa_planning_status_colors().get("Ready for IAP") if ready else None,
        )

    def _render_cards(self) -> None:
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self._filtered_assignments()
        if not rows:
            empty = QLabel("No strategies match the current filters.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{_color_name('muted')}; font-style:italic; padding:24px;")
            self._card_layout.insertWidget(0, empty)
            return

        for wa in rows:
            if wa.id is None:
                continue
            meta = self._meta_by_id.get(int(wa.id), _EMPTY_META)
            objective = self._objective_labels.get(str(wa.objective_id), str(wa.objective_id or ""))
            card = _StrategyCard(wa, meta, objective, self._card_container)
            card.opened.connect(self._open_detail)
            card.clone_requested.connect(self._clone_assignment)
            card.archive_requested.connect(self._archive_assignment)
            card.restore_requested.connect(self._restore_assignment)
            card.recalculate_requested.connect(self._recalculate_assignment)
            card.create_task_requested.connect(self._create_task)
            card.link_task_requested.connect(self._link_task)
            card.copy_requested.connect(self._copy_summary)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _assignment_by_id(self, assignment_id: int) -> WorkAssignment | None:
        return next((wa for wa in self._assignments_cache if wa.id == assignment_id), None)

    def _new_assignment(self) -> None:
        win = WorkAssignmentDetailWindow(db_path=self._db_path, parent=None)
        win.saved.connect(self.reload)
        win.show()
        self._open_detail_windows.append(win)

    def _open_detail(self, work_assignment_id: int) -> None:
        import shiboken6

        self._open_detail_windows = [w for w in self._open_detail_windows if shiboken6.isValid(w)]
        for win in list(self._open_detail_windows):
            if not win.isVisible():
                self._open_detail_windows.remove(win)
                continue
            if win._work_assignment_id == work_assignment_id:
                win.raise_()
                win.activateWindow()
                return
        win = WorkAssignmentDetailWindow(
            work_assignment_id=work_assignment_id, db_path=self._db_path, parent=None
        )
        win.saved.connect(self.reload)
        win.show()
        self._open_detail_windows.append(win)

    def _clone_assignment(self, assignment_id: int) -> None:
        try:
            repo = WorkAssignmentRepository(self._db_path)
            new_id = repo.clone_work_assignment(assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Clone", f"Failed to clone:\n{exc}")
            return
        self.reload()
        if new_id:
            self._open_detail(new_id)

    def _archive_assignment(self, assignment_id: int) -> None:
        wa = self._assignment_by_id(assignment_id)
        if wa is None:
            return
        if wa.is_archived:
            QMessageBox.information(self, "Archive", "Strategy is already archived.")
            return
        if QMessageBox.question(
            self, "Archive", f"Archive '{wa.assignment_name}'?"
        ) != QMessageBox.Yes:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.archive_work_assignment(assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Archive", f"Failed:\n{exc}")
            return
        self.reload()

    def _restore_assignment(self, assignment_id: int) -> None:
        wa = self._assignment_by_id(assignment_id)
        if wa is None:
            return
        if not wa.is_archived:
            QMessageBox.information(self, "Restore", "Strategy is not archived.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.restore_work_assignment(assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Restore", f"Failed:\n{exc}")
            return
        self.reload()

    def _recalculate_assignment(self, assignment_id: int) -> None:
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.recalculate_all_resource_gaps(assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Recalculate", f"Failed:\n{exc}")
            return
        self.reload()
        QMessageBox.information(self, "Recalculate", "Resource gaps recalculated.")

    def _create_task(self, assignment_id: int) -> None:
        try:
            repo = WorkAssignmentRepository(self._db_path)
            task_id = repo.create_task_from_work_assignment(assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Create Task", f"Failed:\n{exc}")
            return
        if task_id is None:
            QMessageBox.information(
                self,
                "Create Task",
                "Taskings module not found - task creation unavailable.\n"
                "Open the strategy and create a task from the Tasks tab.",
            )
        else:
            QMessageBox.information(self, "Create Task", f"Operations task {task_id} created.")
        self.reload()

    def _link_task(self, assignment_id: int) -> None:
        self._open_detail(assignment_id)

    def _copy_summary(self, assignment_id: int) -> None:
        wa = self._assignment_by_id(assignment_id)
        if not wa:
            return
        meta = self._meta_by_id.get(assignment_id, _EMPTY_META)
        req_total, assigned_total, gap, hazard_total, open_hazards, task_count = meta
        text = (
            f"{wa.assignment_number} {wa.assignment_name}\n"
            f"Status: {wa.planning_status}  Safety: {wa.safety_status}  Resources: {wa.resource_status}\n"
            f"Branch: {wa.branch}  Division/Group: {wa.division_group}\n"
            f"Resources: {req_total} required / {assigned_total} assigned / Gap {gap}\n"
            f"Hazards: {hazard_total} total / {open_hazards} open  Tasks: {task_count}"
        )
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(text)
