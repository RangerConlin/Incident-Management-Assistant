from __future__ import annotations

"""Qt Widgets panel for managing Incident Objectives."""

from dataclasses import dataclass
from html import escape
from typing import Any, List, Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QTextDocument
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from modules.command.models.objectives import (
    ApiObjectiveRepository,
    ObjectiveFilters,
    ObjectiveSummary,
)
from modules.command.widgets.objective_detail_dialog import ObjectiveDetailDialog
from modules.command.widgets.objective_template_picker_dialog import ObjectiveTemplatePickerDialog
from modules.planning.operational_periods.repository import OperationalPeriodRepository
from utils import incident_context, timefmt
from utils.styles import (
    get_palette,
    subscribe_theme,
    task_status_colors,
    wa_priority_colors,
)


_STATUS_COLOR_KEYS = {
    "draft": "created",
    "active": "in progress",
    "completed": "complete",
    "cancelled": "cancelled",
}


def _color_name(key: str, fallback: str = "ctrl_border") -> str:
    pal = get_palette()
    color = pal.get(key) or pal.get(fallback)
    return color.name() if color is not None else ""


def _brush_color(brushes: dict[str, Any] | None, role: str, fallback: str) -> str:
    if brushes and role in brushes:
        return brushes[role].color().name()
    return _color_name(fallback)


def _chip(text: str, brushes: dict[str, Any] | None, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setAlignment(Qt.AlignCenter)
    label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    bg = _brush_color(brushes, "bg", "ctrl_bg")
    fg = _brush_color(brushes, "fg", "fg")
    border = _color_name("ctrl_border")
    label.setStyleSheet(
        f"background:{bg}; color:{fg}; border:1px solid {border}; "
        "padding:2px 8px; border-radius:4px; font-weight:700;"
    )
    return label


def _metric_label(label: str, value: str, alert: bool = False) -> QLabel:
    widget = QLabel(f"<b>{escape(label)}</b>  {escape(value)}")
    widget.setTextFormat(Qt.RichText)
    widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    widget.setStyleSheet(f"color:{_color_name('danger' if alert else 'fg')};")
    return widget


def _priority_brushes(priority: str) -> dict[str, Any] | None:
    return wa_priority_colors().get(priority.title())


def _status_brushes(status: str) -> dict[str, Any] | None:
    key = _STATUS_COLOR_KEYS.get(status.lower())
    if key:
        return task_status_colors().get(key)
    return None


class _ObjectiveCard(QFrame):
    """One contained row card for an incident objective summary."""

    opened = Signal(str)
    quick_status_requested = Signal(str)
    complete_requested = Signal(str)
    duplicate_requested = Signal(str)
    move_requested = Signal(str, int)

    def __init__(self, objective: ObjectiveSummary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._objective = objective
        self.setFrameShape(QFrame.StyledPanel)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        objective = self._objective
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(8)
        code = objective.code or f"Objective {objective.display_order + 1}"
        title = QLabel(f"{code}  {objective.text or '(Untitled Objective)'}", self)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight:700; font-size:14px; background:transparent;")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header.addWidget(title, 1)
        header.addWidget(_chip(objective.priority.title(), _priority_brushes(objective.priority), self))
        header.addWidget(_chip(objective.status.title(), _status_brushes(objective.status), self))
        layout.addLayout(header)

        meta = QHBoxLayout()
        meta.setSpacing(10)
        owner = objective.owner_section or "No owner assigned"
        op_period = objective.op_period_id or "No OP"
        owner_label = QLabel(owner, self)
        owner_label.setStyleSheet(f"color:{_color_name('muted')}; background:transparent;")
        meta.addWidget(owner_label, 1)
        op_label = QLabel(f"OP {op_period}" if objective.op_period_id else op_period, self)
        op_label.setStyleSheet(f"color:{_color_name('muted')}; font-weight:600; background:transparent;")
        meta.addWidget(op_label)
        if objective.updated_at:
            updated = QLabel(f"Updated {timefmt.humanize_relative(objective.updated_at)}", self)
            updated.setStyleSheet(f"color:{_color_name('muted')}; font-size:11px; background:transparent;")
            meta.addWidget(updated)
        layout.addLayout(meta)

        footer = QHBoxLayout()
        footer.setSpacing(18)
        footer.addWidget(_metric_label("Strategies", str(objective.strategies), alert=objective.strategies == 0))
        footer.addWidget(
            _metric_label(
                "Tasks",
                f"{objective.open_tasks} open / {objective.total_tasks} total",
                alert=objective.open_tasks > 0,
            )
        )
        if objective.tags:
            tags = QLabel("  ".join(f"#{tag}" for tag in objective.tags[:4]), self)
            tags.setStyleSheet(f"color:{_color_name('muted')}; background:transparent;")
            footer.addWidget(tags, 1)
        else:
            footer.addStretch(1)
        layout.addLayout(footer)

    def _apply_style(self) -> None:
        objective = self._objective
        border_color = _color_name("ctrl_border")
        left_border = border_color
        if objective.status in {"completed", "cancelled"}:
            left_border = _brush_color(_status_brushes(objective.status), "bg", "ctrl_border")
        elif objective.priority == "urgent":
            left_border = _brush_color(_priority_brushes(objective.priority), "bg", "danger")
        elif objective.priority == "high":
            left_border = _brush_color(_priority_brushes(objective.priority), "bg", "warning")
        elif objective.status == "active":
            left_border = _brush_color(_status_brushes(objective.status), "bg", "accent")

        self.setStyleSheet(
            "_ObjectiveCard { "
            f"background-color:{_color_name('bg_raised')}; "
            f"border:1px solid {border_color}; "
            f"border-left:4px solid {left_border}; "
            "border-radius:8px; "
            "}"
        )

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.opened.emit(self._objective.id)
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, position: QPoint) -> None:
        objective_id = self._objective.id
        menu = QMenu(self)
        menu.addAction("Edit", lambda: self.opened.emit(objective_id))
        menu.addAction("Quick Status", lambda: self.quick_status_requested.emit(objective_id))
        menu.addSeparator()
        menu.addAction("Add Strategy", lambda: self.opened.emit(objective_id))
        menu.addAction("Create Task", lambda: self.opened.emit(objective_id))
        menu.addAction("View All Tasks", lambda: self.opened.emit(objective_id))
        menu.addAction("Duplicate", lambda: self.duplicate_requested.emit(objective_id))
        menu.addAction("Complete/Cancel", lambda: self.complete_requested.emit(objective_id))
        menu.addSeparator()
        menu.addAction("Move Up", lambda: self.move_requested.emit(objective_id, -1))
        menu.addAction("Move Down", lambda: self.move_requested.emit(objective_id, 1))
        menu.exec(self.mapToGlobal(position))


@dataclass
class _ToolbarWidgets:
    search: QLineEdit


class IncidentObjectivesPanel(QWidget):
    """Main QWidget surface for the Incident Objectives workspace."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._detail_windows: list[ObjectiveDetailDialog] = []
        self._objectives: list[ObjectiveSummary] = []
        self._toolbar = QToolBar("Objectives", self)
        self._toolbar.setIconSize(self._toolbar.iconSize())
        self._toolbar.setMovable(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self._toolbar)

        toolbar_widgets = self._build_toolbar()
        self._toolbar_widgets = toolbar_widgets

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._card_container = QWidget(self._scroll)
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(8)
        self._card_layout.addStretch(1)
        self._scroll.setWidget(self._card_container)
        layout.addWidget(self._scroll, 1)

        toolbar_widgets.search.textChanged.connect(lambda _text: self._render_cards())
        subscribe_theme(self, self._on_theme_changed)
        self.reload()

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> _ToolbarWidgets:
        new_action = QAction(QIcon.fromTheme("list-add"), "New Objective", self)
        new_action.triggered.connect(self._create_objective)
        self._toolbar.addAction(new_action)

        template_action = QAction("New From Template...", self)
        template_action.triggered.connect(self._create_from_template)
        self._toolbar.addAction(template_action)

        manage_templates_action = QAction("Manage Templates...", self)
        manage_templates_action.triggered.connect(self._open_template_manager)
        self._toolbar.addAction(manage_templates_action)

        clone_action = QAction("Clone From Previous OP", self)
        clone_action.triggered.connect(self._clone_previous)
        self._toolbar.addAction(clone_action)

        reorder_action = QAction("Reorder", self)
        reorder_action.triggered.connect(self._prompt_reorder_help)
        self._toolbar.addAction(reorder_action)

        self._toolbar.addSeparator()

        search_edit = QLineEdit(self)
        search_edit.setPlaceholderText("Search objectives...")
        search_edit.setClearButtonEnabled(True)
        search_edit.setMaximumWidth(260)
        self._toolbar.addWidget(search_edit)

        filters_action = QAction("Filters", self)
        filters_action.triggered.connect(self._show_filters_dialog)
        self._toolbar.addAction(filters_action)

        export_button = QToolButton(self)
        export_button.setText("Export")
        export_button.setPopupMode(QToolButton.MenuButtonPopup)
        export_menu = QMenu(export_button)
        export_menu.addAction("ICS-202", self._export_ics202)
        export_button.setMenu(export_menu)
        export_button.clicked.connect(self._export_ics202)
        self._toolbar.addWidget(export_button)

        print_action = QAction("Print Preview", self)
        print_action.triggered.connect(self._show_print_preview)
        self._toolbar.addAction(print_action)

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._toolbar.addWidget(spacer)
        return _ToolbarWidgets(search=search_edit)

    # ------------------------------------------------------------------
    def reload(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            self._objectives = []
            self._render_cards()
            return
        try:
            objectives = ApiObjectiveRepository(str(incident_id)).list_objectives(ObjectiveFilters())
        except Exception as exc:  # pragma: no cover - UI fallback
            QMessageBox.critical(self, "Incident Objectives", f"Failed to load objectives:\n{exc}")
            objectives = []
        self._objectives = sorted(objectives, key=lambda obj: (obj.display_order, obj.code))
        self._render_cards()

    def _on_theme_changed(self, _name: str) -> None:
        self._render_cards()

    def _filtered_objectives(self) -> list[ObjectiveSummary]:
        needle = self._toolbar_widgets.search.text().strip().lower()
        if not needle:
            return list(self._objectives)
        result: list[ObjectiveSummary] = []
        for objective in self._objectives:
            haystack = " ".join(
                [
                    objective.code,
                    objective.text,
                    objective.priority,
                    objective.status,
                    objective.owner_section or "",
                    objective.op_period_id or "",
                    " ".join(objective.tags),
                ]
            ).lower()
            if needle in haystack:
                result.append(objective)
        return result

    def _render_cards(self) -> None:
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self._filtered_objectives()
        if not rows:
            empty = QLabel("No objectives match the current filters.", self._card_container)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{_color_name('muted')}; font-style:italic; padding:24px;")
            self._card_layout.insertWidget(0, empty)
            return

        for objective in rows:
            card = _ObjectiveCard(objective, self._card_container)
            card.opened.connect(self._open_detail)
            card.quick_status_requested.connect(self._quick_status)
            card.complete_requested.connect(lambda objective_id: self._quick_status(objective_id, target="completed"))
            card.duplicate_requested.connect(self._duplicate_objective)
            card.move_requested.connect(self._move_objective)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

    # ------------------------------------------------------------------
    def _create_objective(self) -> None:
        dialog = ObjectiveDetailDialog(self, on_saved=self.reload)
        dialog.setWindowTitle("New Objective")
        dialog.show()
        self._detail_windows.append(dialog)

    def _create_from_template(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "New From Template", "Select an incident first.")
            return
        dialog = ObjectiveTemplatePickerDialog(self, on_imported=self.reload)
        dialog.exec()

    def _open_template_manager(self) -> None:
        from modules.planning.widgets.objectives_editor import show_objectives_editor
        editor = show_objectives_editor(None)
        editor.raise_()
        editor.activateWindow()

    def _clone_previous(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "Clone Objectives", "Select an incident to clone objectives.")
            return
        try:
            op_repo = OperationalPeriodRepository(str(incident_id))
            periods = sorted(op_repo.list_periods(), key=lambda p: p.number)
        except Exception as exc:  # pragma: no cover - UI fallback
            QMessageBox.critical(self, "Clone Objectives", f"Failed to load operational periods:\n{exc}")
            return
        if len(periods) < 2:
            QMessageBox.information(self, "Clone Objectives", "There is no previous operational period to clone from.")
            return
        active = op_repo.get_active_period()
        if active is not None:
            earlier = [p for p in periods if p.number < active.number]
            if not earlier:
                QMessageBox.information(self, "Clone Objectives", "There is no operational period before the active one.")
                return
            target = active
            source = earlier[-1]
        else:
            target = periods[-1]
            source = periods[-2]

        try:
            objectives = ApiObjectiveRepository(str(incident_id)).list_objectives(
                ObjectiveFilters(op_period_id=source.id)
            )
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Clone Objectives", f"Failed to load source objectives:\n{exc}")
            return
        if not objectives:
            QMessageBox.information(self, "Clone Objectives", f"OP {source.number} has no objectives to clone.")
            return

        confirm = QMessageBox.question(
            self,
            "Clone Objectives",
            f"Clone {len(objectives)} objective(s) from OP {source.number} into OP {target.number}?",
        )
        if confirm != QMessageBox.Yes:
            return

        repo = ApiObjectiveRepository(str(incident_id))
        failures = 0
        for objective in objectives:
            try:
                repo.create_objective(
                    {
                        "text": objective.text,
                        "priority": objective.priority,
                        "status": "draft",
                        "owner_section": objective.owner_section,
                        "op_period_id": target.id,
                        "tags": list(objective.tags),
                    }
                )
            except Exception:
                failures += 1
        self.reload()
        if failures:
            QMessageBox.warning(self, "Clone Objectives", f"Cloned with {failures} failure(s). See logs for details.")
        else:
            QMessageBox.information(self, "Clone Objectives", f"Cloned {len(objectives)} objective(s) into OP {target.number}.")

    def _prompt_reorder_help(self) -> None:
        QMessageBox.information(
            self,
            "Reorder Objectives",
            "Right-click an objective card and use Move Up or Move Down to change the display order.",
        )

    def _show_filters_dialog(self) -> None:
        QMessageBox.information(
            self,
            "Filters",
            "Advanced filters will be available in a future update.",
        )

    def _export_ics202(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "Export", "Select an incident to export ICS-202 data.")
            return
        try:
            payload = ApiObjectiveRepository(str(incident_id)).export_ics202()
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Export", f"Failed to build ICS-202 export:\n{exc}")
            return
        try:
            from pathlib import Path
            from utils import incident_storage
            from modules.forms_creator.api import export_form_unified

            paths = incident_storage.resolve_incident_paths_by_identifier(str(incident_id))
            out_dir = paths.forms_exports if paths else Path("data") / "exports" / str(incident_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            result = export_form_unified(
                "ics_202",
                out_dir / "ICS202.pdf",
                values=payload if isinstance(payload, dict) else {},
                context={"incident_id": str(incident_id)},
            )
            QMessageBox.information(self, "Export", f"ICS-202 exported to:\n{result.path}")
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Export", f"Export failed:\n{exc}")

    def _show_print_preview(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "Print Preview", "Select an incident to preview objectives.")
            return
        try:
            payload = ApiObjectiveRepository(str(incident_id)).export_ics202()
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Print Preview", f"Failed to build preview:\n{exc}")
            return

        document = QTextDocument(self)
        document.setHtml(self._build_preview_html(payload))
        printer = QPrinter(QPrinter.HighResolution)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Incident Objectives - Print Preview")
        preview.paintRequested.connect(document.print_)
        preview.exec()

    @staticmethod
    def _build_preview_html(payload: dict) -> str:
        rows = []
        for obj in payload.get("objectives", []):
            rows.append(
                "<tr>"
                f"<td>{escape(str(obj.get('order', '')))}</td>"
                f"<td>{escape(str(obj.get('code', '')))}</td>"
                f"<td>{escape(str(obj.get('text', '')))}</td>"
                f"<td>{escape(str(obj.get('priority', '')).title())}</td>"
                f"<td>{escape(str(obj.get('status', '')).title())}</td>"
                "</tr>"
            )
        return (
            "<h2>Incident Objectives (ICS-202)</h2>"
            "<table border='1' cellspacing='0' cellpadding='4' width='100%'>"
            "<tr><th>#</th><th>Code</th><th>Objective</th><th>Priority</th><th>Status</th></tr>"
            + "".join(rows)
            + "</table>"
        )

    def _objective_by_id(self, objective_id: str) -> ObjectiveSummary | None:
        return next((objective for objective in self._objectives if objective.id == objective_id), None)

    def _open_detail(self, objective_id: str) -> None:
        dialog = ObjectiveDetailDialog(self, on_saved=self.reload)
        dialog.load_objective(objective_id)
        dialog.show()
        self._detail_windows.append(dialog)

    def _quick_status(self, objective_id: str, target: str | None = None) -> None:
        objective = self._objective_by_id(objective_id)
        if not objective:
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        next_status = target or ("active" if objective.status != "active" else "completed")
        try:
            ApiObjectiveRepository(str(incident_id)).set_status(objective.id, next_status)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Quick Status", f"Failed to update status:\n{exc}")
            return
        self.reload()

    def _duplicate_objective(self, objective_id: str) -> None:
        objective = self._objective_by_id(objective_id)
        if not objective:
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        try:
            ApiObjectiveRepository(str(incident_id)).create_objective(
                {
                    "text": f"{objective.text} (Copy)",
                    "priority": objective.priority,
                    "status": "draft",
                    "owner_section": objective.owner_section,
                    "op_period_id": objective.op_period_id,
                    "tags": list(objective.tags),
                }
            )
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Duplicate Objective", f"Failed to duplicate objective:\n{exc}")
            return
        self.reload()

    def _move_objective(self, objective_id: str, direction: int) -> None:
        index = next((idx for idx, obj in enumerate(self._objectives) if obj.id == objective_id), -1)
        if index < 0:
            return
        target = index + direction
        if target < 0 or target >= len(self._objectives):
            return
        self._objectives[index], self._objectives[target] = self._objectives[target], self._objectives[index]
        for display_order, objective in enumerate(self._objectives):
            objective.display_order = display_order
        self._persist_reorder([objective.id for objective in self._objectives])
        self._render_cards()

    def _persist_reorder(self, ordered_ids: List[str]) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        try:
            ApiObjectiveRepository(str(incident_id)).reorder_objectives(ordered_ids)
        except Exception as exc:  # pragma: no cover
            QMessageBox.warning(self, "Reorder", f"Failed to persist order:\n{exc}")
