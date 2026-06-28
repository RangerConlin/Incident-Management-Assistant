from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from utils.api_client import APIError
from utils.app_signals import app_signals
from utils.state import AppState
from utils.table_view_styles import apply_statusboard_table_behavior

from .. import services
from ..models import HastyTaskCreate, HastyTaskRead, InitialOverviewRead


@dataclass(frozen=True)
class TaskSuggestion:
    category: str
    task_type: str
    title: str
    objective: str
    instructions: str
    priority: str = "High"


_CATEGORY_ORDER = [
    "Investigation",
    "Initial Planning Point",
    "Containment",
    "Immediate Area",
    "Travel Corridors",
    "High Probability",
]


_OBJECTIVE_LIBRARY = {
    "Missing Person": [
        "Locate the subject and refine the incident picture.",
        "Investigate and validate the primary planning anchor and related locations.",
        "Cover likely early movement areas and preserve emerging clues.",
    ],
    "Missing Aircraft": [
        "Locate the aircraft or refine the last known route and likely impact corridor.",
        "Investigate aviation-specific leads and confirm last known communications or tracking.",
        "Cover likely route segments and high-probability terrain features quickly.",
    ],
}


_PERSON_GENERIC: list[TaskSuggestion] = [
    TaskSuggestion(
        "Investigation",
        "Interview",
        "Recontact reporting party",
        "Refine the timeline and verify what is known right now.",
        "Recontact the reporting party, confirm timeline details, clarify last known information, and capture any missed destinations, habits, or immediate concerns.",
        "High",
    ),
    TaskSuggestion(
        "Investigation",
        "Witness",
        "Interview witnesses",
        "Verify sightings and likely movement details.",
        "Contact known witnesses, confirm the time and location of each observation, and document direction of travel, demeanor, pace, and any clues mentioned.",
        "High",
    ),
    TaskSuggestion(
        "Initial Planning Point",
        "Point Search",
        "Confirm and search the planning anchor",
        "Validate the selected IPP/LKP and search the immediate anchor zone.",
        "Respond to the selected planning anchor, confirm the point with available witnesses or source information, and conduct a quick but deliberate search of the immediate area for clues or the subject.",
        "High",
    ),
    TaskSuggestion(
        "Containment",
        "Containment",
        "Monitor likely exits",
        "Watch likely egress points and keep the subject from leaving unnoticed.",
        "Cover likely exit points, trailheads, road intersections, and access routes associated with the planning anchor. Report all observations immediately.",
        "Medium",
    ),
    TaskSuggestion(
        "Immediate Area",
        "Area Search",
        "Search the immediate area",
        "Cover nearby terrain and obvious hiding or rest locations near the anchor.",
        "Search the immediate area around the planning anchor, including nearby structures, terrain traps, concealment spots, and natural attraction points.",
        "High",
    ),
    TaskSuggestion(
        "Travel Corridors",
        "Route Search",
        "Search likely travel corridors",
        "Check roads, trails, drainages, and other linear features leading away from the anchor.",
        "Conduct a hasty search along likely travel corridors leaving the anchor, with emphasis on roads, trails, drainages, fences, and other linear features.",
        "High",
    ),
    TaskSuggestion(
        "High Probability",
        "Point Search",
        "Search high-probability features",
        "Check likely destinations and attraction features tied to the subject profile.",
        "Search high-probability features associated with the subject, including likely destinations, attraction points, shelter locations, and terrain offering easy travel or concealment.",
        "High",
    ),
]


_DEMENTIA_EXTRA = [
    TaskSuggestion(
        "Travel Corridors",
        "Trail Search",
        "Hasty search of trails and paths of least resistance",
        "Cover easy travel features commonly used by dementia subjects.",
        "Search trails, roads, and other paths of least resistance radiating from the anchor. Pay attention to rest points, edges, and features that allow steady wandering movement.",
        "High",
    ),
    TaskSuggestion(
        "High Probability",
        "Attraction Search",
        "Search water, concealment, and nearby shelter features",
        "Cover nearby features that frequently draw or conceal dementia subjects.",
        "Search nearby water features, brush lines, outbuildings, porches, vehicles, and concealment or shelter opportunities within quick travel distance.",
        "High",
    ),
]


_CHILD_EXTRA = [
    TaskSuggestion(
        "Immediate Area",
        "Structure Search",
        "Search nearby structures and concealment spots",
        "Cover places a child may hide or wander into close to the anchor.",
        "Search nearby homes, sheds, play areas, culverts, vehicles, and other concealment or attraction features near the anchor.",
        "High",
    ),
]


_HIKER_EXTRA = [
    TaskSuggestion(
        "Travel Corridors",
        "Trail Search",
        "Search planned routes and trail segments",
        "Cover intended hiking routes and obvious route continuations.",
        "Search intended routes, junctions, trail continuations, and decision points connected to the planning anchor and any known destination.",
        "High",
    ),
]


_AIRCRAFT_SUGGESTIONS: list[TaskSuggestion] = [
    TaskSuggestion(
        "Investigation",
        "Ramp Check",
        "Conduct ramp and airport checks",
        "Verify aircraft status at likely origin, destination, and diversion fields.",
        "Contact or visit likely airports, FBOs, and hangars to confirm whether the aircraft arrived, diverted, refueled, or was observed by personnel on the ground.",
        "High",
    ),
    TaskSuggestion(
        "Investigation",
        "Aviation Follow-Up",
        "Review route, comms, and tracking leads",
        "Refine the route picture using available aviation data.",
        "Review departure information, destination, route of flight, radio or radar information, ADS-B or tracker data, and any missed communications associated with the aircraft.",
        "High",
    ),
    TaskSuggestion(
        "Initial Planning Point",
        "Point Validation",
        "Validate the last known aircraft point",
        "Confirm the best available starting anchor for the route search.",
        "Validate the last known point, route anchor, or last reliable contact position and confirm how it should drive early tasking.",
        "High",
    ),
    TaskSuggestion(
        "Containment",
        "Notification",
        "Notify likely receiving facilities and corridor stakeholders",
        "Make sure likely receiving points are aware and reporting sightings quickly.",
        "Notify likely airports, airfields, corridor facilities, and aviation partners associated with the projected route or diversion options.",
        "Medium",
    ),
    TaskSuggestion(
        "Immediate Area",
        "Area Search",
        "Search terrain near the last known point",
        "Quickly cover terrain immediately surrounding the best known anchor.",
        "Search terrain immediately surrounding the selected route anchor or last known point, with emphasis on likely emergency landing or impact areas.",
        "High",
    ),
    TaskSuggestion(
        "Travel Corridors",
        "Route Search",
        "Conduct route search",
        "Search likely route segments and alternates.",
        "Search the planned route and likely alternates, prioritizing terrain, weather exposures, and likely emergency landing corridors.",
        "High",
    ),
    TaskSuggestion(
        "High Probability",
        "Terrain Search",
        "Search high-probability terrain and approach corridors",
        "Focus on terrain traps and likely emergency landing zones.",
        "Search ridge lines, valleys, drainages, open fields, approach corridors, and terrain traps that align with the projected route and conditions.",
        "High",
    ),
]


class HastyToolsPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        del incident_id
        self.setObjectName("HastyToolsPanel")
        self._status = QLabel("")
        self._context = QLabel("No active incident selected")
        self._context.setStyleSheet("font-weight: 600;")
        self._objectives = QTextEdit()
        self._objectives.setFixedHeight(90)
        self._generated_preview = QTextEdit()
        self._generated_preview.setReadOnly(True)
        self._suggestions: list[TaskSuggestion] = []
        self._build_ui()
        try:
            app_signals.incidentChanged.connect(lambda *_: self.reload())
        except Exception:
            pass
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QFrame()
        header.setFrameShape(QFrame.Shape.StyledPanel)
        header.setStyleSheet("QFrame { border: 1px solid #d0d0d0; border-radius: 4px; padding: 8px; }")
        header_layout = QVBoxLayout(header)
        top_row = QHBoxLayout()
        title = QLabel("Early Tasking")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top_row.addWidget(title)
        top_row.addStretch(1)
        top_row.addWidget(self._status)
        header_layout.addLayout(top_row)
        subtitle = QLabel(
            "Generate recommended early taskings from the incident picture so the first operational push is easier to build and repeat."
        )
        subtitle.setWordWrap(True)
        header_layout.addWidget(self._context)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        context_box = QGroupBox("Situation Context")
        context_grid = QGridLayout(context_box)
        self._mode_value = QLabel("—")
        self._behavior_value = QLabel("—")
        self._anchor_value = QLabel("—")
        self._subject_value = QLabel("—")
        labels = [
            ("Mode", self._mode_value),
            ("Behavior", self._behavior_value),
            ("Primary Anchor", self._anchor_value),
            ("Subject / Aircraft", self._subject_value),
        ]
        for idx, (label, widget) in enumerate(labels):
            r = idx // 2
            c = (idx % 2) * 2
            cap = QLabel(label)
            cap.setStyleSheet("font-weight: 600;")
            context_grid.addWidget(cap, r, c)
            context_grid.addWidget(widget, r, c + 1)
        layout.addWidget(context_box)

        objective_box = QGroupBox("Incident Objectives")
        objective_layout = QVBoxLayout(objective_box)
        self._objectives.setPlaceholderText("Objectives will be generated from the incident type and can be edited here.")
        objective_layout.addWidget(self._objectives)
        layout.addWidget(objective_box)

        suggestion_box = QGroupBox("Suggested Taskings")
        suggestion_layout = QVBoxLayout(suggestion_box)
        suggestion_actions = QHBoxLayout()
        btn_refresh = QPushButton("Refresh Suggestions")
        btn_build = QPushButton("Build Selected Tasks")
        btn_select_all = QPushButton("Select All")
        btn_clear_selection = QPushButton("Clear Selection")
        btn_refresh.clicked.connect(self.reload)
        btn_build.clicked.connect(self._build_selected_tasks)
        btn_select_all.clicked.connect(lambda: self._set_all_suggestions(True))
        btn_clear_selection.clicked.connect(lambda: self._set_all_suggestions(False))
        suggestion_actions.addWidget(btn_refresh)
        suggestion_actions.addWidget(btn_build)
        suggestion_actions.addStretch(1)
        suggestion_actions.addWidget(btn_select_all)
        suggestion_actions.addWidget(btn_clear_selection)
        suggestion_layout.addLayout(suggestion_actions)

        self._suggestion_table = QTableWidget(0, 6)
        self._suggestion_table.setHorizontalHeaderLabels(["Use", "Qty", "Category", "Type", "Suggested Task", "Priority"])
        apply_statusboard_table_behavior(self._suggestion_table)
        header_view = self._suggestion_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        suggestion_layout.addWidget(self._suggestion_table)
        layout.addWidget(suggestion_box)

        build_box = QGroupBox("Task Build")
        build_layout = QVBoxLayout(build_box)
        build_top = QFormLayout()
        self._create_ops_tasks = QCheckBox("Create linked operations tasks")
        self._create_ops_tasks.setChecked(True)
        self._request_logistics = QCheckBox("Request logistics support for high-priority taskings")
        build_top.addRow(self._create_ops_tasks)
        build_top.addRow(self._request_logistics)
        build_layout.addLayout(build_top)

        self._build_table = QTableWidget(0, 6)
        self._build_table.setHorizontalHeaderLabels(["Task #", "Type", "Title", "Location", "Priority", "Category"])
        apply_statusboard_table_behavior(self._build_table)
        self._build_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._build_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._build_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._build_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._build_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._build_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        build_layout.addWidget(self._build_table)
        build_actions = QHBoxLayout()
        btn_preview = QPushButton("Preview")
        btn_generate = QPushButton("Generate Tasks")
        btn_clear_build = QPushButton("Clear Build")
        btn_preview.clicked.connect(self._refresh_preview)
        btn_generate.clicked.connect(self._generate_tasks)
        btn_clear_build.clicked.connect(self._clear_build)
        build_actions.addWidget(btn_preview)
        build_actions.addWidget(btn_generate)
        build_actions.addWidget(btn_clear_build)
        build_actions.addStretch(1)
        build_layout.addLayout(build_actions)
        layout.addWidget(build_box)

        preview_box = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.addWidget(self._generated_preview)
        layout.addWidget(preview_box)

        logged_box = QGroupBox("Generated Early Tasks")
        logged_layout = QVBoxLayout(logged_box)
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Area / Task", "Priority", "Task", "Logistics", "Notes", "Created"])
        apply_statusboard_table_behavior(self._table, stretch_last_section=True)
        logged_layout.addWidget(self._table)
        layout.addWidget(logged_box)

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Initial response API unavailable: {exc}"
            return f"Initial response API error {exc.status_code}: {exc}"
        return str(exc)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _incident(self) -> str | None:
        return AppState.get_active_incident()

    def _load_context(self, incident_id: str) -> InitialOverviewRead:
        return services.get_initial_overview_entry(incident_id)

    def _subject_summary(self, overview: InitialOverviewRead) -> str:
        if overview.incident_mode == "Missing Aircraft":
            tail = str(overview.aircraft_info.get("tail_number", "")).strip()
            pilot = str(overview.aircraft_info.get("pilot", "")).strip()
            return " | ".join(part for part in [tail, pilot] if part) or "Aircraft details not entered"
        name = str(overview.subject_info.get("name", "")).strip()
        age = str(overview.subject_info.get("age", "")).strip()
        sex = str(overview.subject_info.get("sex", "")).strip()
        detail = " ".join(part for part in [age, sex] if part).strip()
        return " | ".join(part for part in [name, detail] if part) or "Subject details not entered"

    def _anchor_summary(self, overview: InitialOverviewRead) -> str:
        anchor_type = str(overview.primary_anchor.get("anchor_type", "")).strip()
        address = str(overview.primary_anchor.get("address", "")).strip()
        return " ".join(part for part in [anchor_type, address] if part).strip() or "Not established"

    def _generate_objectives(self, overview: InitialOverviewRead) -> list[str]:
        base = list(_OBJECTIVE_LIBRARY.get(overview.incident_mode, _OBJECTIVE_LIBRARY["Missing Person"]))
        behavior = str(overview.behavior_category or "").strip().lower()
        if behavior == "dementia":
            base.append("Focus early efforts on easy travel features, nearby concealment, and water-related hazards.")
        elif behavior.startswith("child"):
            base.append("Cover nearby attraction and concealment features rapidly and protect likely exit points.")
        elif behavior == "aircraft":
            base.append("Prioritize route-based leads, airfield checks, and terrain aligned with the last known route.")
        elif behavior == "hiker":
            base.append("Cover intended routes, trail junctions, and known destinations quickly.")
        return base

    def _generate_suggestions(self, overview: InitialOverviewRead) -> list[TaskSuggestion]:
        if overview.incident_mode == "Missing Aircraft":
            return list(_AIRCRAFT_SUGGESTIONS)

        suggestions = list(_PERSON_GENERIC)
        behavior = str(overview.behavior_category or "").strip().lower()
        if behavior == "dementia":
            suggestions.extend(_DEMENTIA_EXTRA)
        elif behavior.startswith("child"):
            suggestions.extend(_CHILD_EXTRA)
        elif behavior == "hiker":
            suggestions.extend(_HIKER_EXTRA)
        return suggestions

    def _populate_suggestions(self, rows: list[TaskSuggestion]) -> None:
        self._suggestions = rows
        self._suggestion_table.setRowCount(0)
        for row_idx, suggestion in enumerate(rows):
            self._suggestion_table.insertRow(row_idx)
            use_box = QCheckBox()
            qty_box = QSpinBox()
            qty_box.setRange(1, 8)
            qty_box.setValue(1)
            if suggestion.priority in {"High", "Critical"}:
                use_box.setChecked(True)
            self._suggestion_table.setCellWidget(row_idx, 0, use_box)
            self._suggestion_table.setCellWidget(row_idx, 1, qty_box)
            values = [
                suggestion.category,
                suggestion.task_type,
                suggestion.title,
                suggestion.priority,
            ]
            for col_idx, value in enumerate(values, start=2):
                self._suggestion_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _set_all_suggestions(self, checked: bool) -> None:
        for row in range(self._suggestion_table.rowCount()):
            box = self._suggestion_table.cellWidget(row, 0)
            if isinstance(box, QCheckBox):
                box.setChecked(checked)

    def _selected_suggestions(self) -> list[tuple[TaskSuggestion, int]]:
        selected: list[tuple[TaskSuggestion, int]] = []
        for row_idx, suggestion in enumerate(self._suggestions):
            use_box = self._suggestion_table.cellWidget(row_idx, 0)
            qty_box = self._suggestion_table.cellWidget(row_idx, 1)
            if isinstance(use_box, QCheckBox) and use_box.isChecked():
                qty = qty_box.value() if isinstance(qty_box, QSpinBox) else 1
                selected.append((suggestion, qty))
        return selected

    def _build_selected_tasks(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._set_status("Select an incident before building tasks.", error=True)
            return
        try:
            overview = self._load_context(incident_id)
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        selected = self._selected_suggestions()
        if not selected:
            self._set_status("Select at least one suggested tasking.", error=True)
            return
        self._build_table.setRowCount(0)
        anchor_location = self._anchor_summary(overview)
        task_number = 1
        for suggestion, qty in selected:
            for copy_index in range(qty):
                row = self._build_table.rowCount()
                self._build_table.insertRow(row)
                title = suggestion.title if qty == 1 else f"{suggestion.title} {copy_index + 1}"
                values = [str(task_number), suggestion.task_type, title, anchor_location, suggestion.priority, suggestion.category]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 0:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self._build_table.setItem(row, col, item)
                task_number += 1
        self._refresh_preview()
        self._set_status(f"Built {self._build_table.rowCount()} template tasks")

    def _clear_build(self) -> None:
        self._build_table.setRowCount(0)
        self._generated_preview.clear()

    def _note_for_task(self, overview: InitialOverviewRead, suggestion: TaskSuggestion, title: str, location: str) -> str:
        subject = self._subject_summary(overview)
        behavior = str(overview.behavior_category or "").strip() or "Not selected"
        anchor = self._anchor_summary(overview)
        objectives = [line.strip("- ").strip() for line in self._objectives.toPlainText().splitlines() if line.strip()]
        objective_block = "\n".join(f"- {line}" for line in objectives[:3]) if objectives else "- No objectives entered"
        return (
            f"Template Task: {title}\n"
            f"Category: {suggestion.category}\n"
            f"Type: {suggestion.task_type}\n"
            f"Priority: {suggestion.priority}\n"
            f"Location: {location or anchor}\n\n"
            f"Objective:\n{suggestion.objective}\n\n"
            f"Instructions:\n{suggestion.instructions}\n\n"
            f"Incident Context:\n"
            f"- Mode: {overview.incident_mode}\n"
            f"- Behavior Category: {behavior}\n"
            f"- Primary Anchor: {anchor}\n"
            f"- Subject / Aircraft: {subject}\n\n"
            f"Incident Objectives:\n{objective_block}"
        )

    def _refresh_preview(self) -> None:
        incident_id = self._incident()
        if not incident_id or self._build_table.rowCount() == 0:
            self._generated_preview.clear()
            return
        try:
            overview = self._load_context(incident_id)
        except Exception as exc:
            self._generated_preview.setPlainText(self._describe_error(exc))
            return
        blocks: list[str] = []
        for row in range(self._build_table.rowCount()):
            title = self._build_table.item(row, 2).text().strip() if self._build_table.item(row, 2) else ""
            location = self._build_table.item(row, 3).text().strip() if self._build_table.item(row, 3) else ""
            task_type = self._build_table.item(row, 1).text().strip() if self._build_table.item(row, 1) else ""
            category = self._build_table.item(row, 5).text().strip() if self._build_table.item(row, 5) else ""
            priority = self._build_table.item(row, 4).text().strip() if self._build_table.item(row, 4) else "High"
            suggestion = next(
                (item for item in self._suggestions if item.title == title or (item.task_type == task_type and item.category == category)),
                TaskSuggestion(category, task_type, title, "", "", priority),
            )
            blocks.append(self._note_for_task(overview, suggestion, title, location))
        self._generated_preview.setPlainText("\n\n" + ("\n\n" + ("-" * 60) + "\n\n").join(blocks))

    def _generate_tasks(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._set_status("Select an incident before generating tasks.", error=True)
            return
        if self._build_table.rowCount() == 0:
            self._set_status("Build at least one task first.", error=True)
            return
        try:
            overview = self._load_context(incident_id)
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        created = 0
        for row in range(self._build_table.rowCount()):
            title = self._build_table.item(row, 2).text().strip() if self._build_table.item(row, 2) else ""
            location = self._build_table.item(row, 3).text().strip() if self._build_table.item(row, 3) else ""
            task_type = self._build_table.item(row, 1).text().strip() if self._build_table.item(row, 1) else ""
            category = self._build_table.item(row, 5).text().strip() if self._build_table.item(row, 5) else ""
            priority = self._build_table.item(row, 4).text().strip() if self._build_table.item(row, 4) else "High"
            suggestion = next(
                (item for item in self._suggestions if item.title == title or (item.task_type == task_type and item.category == category)),
                TaskSuggestion(category, task_type, title, "", "", priority),
            )
            area_value = " | ".join(part for part in [title, location] if part)
            note_value = self._note_for_task(overview, suggestion, title, location)
            payload = HastyTaskCreate(
                area=area_value,
                priority=priority,
                notes=note_value,
                create_task=self._create_ops_tasks.isChecked(),
                request_logistics=self._request_logistics.isChecked(),
            )
            try:
                services.create_hasty_task(payload)
            except Exception as exc:
                self._set_status(self._describe_error(exc), error=True)
                QMessageBox.critical(self, "Generate failed", self._describe_error(exc))
                return
            created += 1
        self._clear_build()
        self.reload()
        self._set_status(f"Generated {created} early tasks")

    def _populate_logged(self, rows: Iterable[HastyTaskRead]) -> None:
        self._table.setRowCount(0)
        for record in rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            values = [
                record.area,
                record.priority or "",
                str(record.operations_task_id or ""),
                record.logistics_request_id or "",
                record.notes or "",
                record.created_at or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in {2, 3}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, col, item)

    def reload(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._context.setText("No active incident selected")
            self._objectives.clear()
            self._suggestion_table.setRowCount(0)
            self._table.setRowCount(0)
            self._set_status("Select an incident to use early tasking.", error=True)
            return
        try:
            overview = self._load_context(incident_id)
            rows = services.list_hasty_task_entries(incident_id)
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            QMessageBox.critical(self, "Load failed", self._describe_error(exc))
            return

        self._context.setText(f"Incident {incident_id}")
        self._mode_value.setText(overview.incident_mode or "—")
        self._behavior_value.setText(overview.behavior_category or "—")
        self._anchor_value.setText(self._anchor_summary(overview))
        self._subject_value.setText(self._subject_summary(overview))
        self._objectives.setPlainText("\n".join(f"- {line}" for line in self._generate_objectives(overview)))
        self._populate_suggestions(self._generate_suggestions(overview))
        self._populate_logged(rows)
        active_links = sum(1 for row in rows if row.operations_task_id)
        self._set_status(f"{len(rows)} early tasks | {active_links} ops links")
