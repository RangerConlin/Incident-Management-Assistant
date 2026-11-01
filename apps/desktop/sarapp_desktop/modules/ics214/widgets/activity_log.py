"""Filtered desktop view over the canonical incident ICS-214 entry stream."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.ics214 import services
from modules.ics214.schemas import (
    CorrectionCreate,
    EntryCreate,
    EntryFilter,
    ExportRequest,
    LogDefinitionCreate,
    VoidRequest,
)
from utils import incident_context
from utils.table_view_styles import apply_statusboard_table_behavior

ASSOCIATION_TYPES = (
    ("All entries", ""),
    ("Person", "person_ids"),
    ("Team", "team_ids"),
    ("Task", "task_ids"),
    ("Organization unit", "org_unit_ids"),
    ("Facility", "facility_ids"),
    ("Resource", "resource_ids"),
    ("External agency", "external_agency_ids"),
)


def _active_user() -> str:
    try:
        from utils.state import AppState
        return str(AppState.get_active_user_id() or "unknown")
    except Exception:
        return "unknown"


class EntryDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        text: str = "",
        title: str = "Add 214 Entry",
        options: dict[str, list[dict[str, Any]]] | None = None,
        default_field: str = "",
        default_id: int | None = None,
        initial_associations: dict[str, list[int]] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(text)
        layout.addWidget(self.text_edit)
        self.incident_wide = QCheckBox("Also include in the incident-wide log", self)
        layout.addWidget(self.incident_wide)
        scope = QHBoxLayout()
        self.type_combo = QComboBox(self)
        for label, field in ASSOCIATION_TYPES:
            self.type_combo.addItem(label, field)
        self.entity_combo = QComboBox(self)
        self._options = options or {}
        self.type_combo.currentIndexChanged.connect(self._type_changed)
        scope.addWidget(self.type_combo)
        scope.addWidget(self.entity_combo, 1)
        add_scope = QPushButton("Add Association", self)
        add_scope.clicked.connect(self._add_association)
        scope.addWidget(add_scope)
        layout.addLayout(scope)
        self.association_list = QListWidget(self)
        self.association_list.setMaximumHeight(90)
        self.association_list.itemDoubleClicked.connect(
            lambda item: self.association_list.takeItem(self.association_list.row(item))
        )
        self.association_list.setToolTip("Double-click an association to remove it")
        layout.addWidget(self.association_list)
        if default_field:
            self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(default_field)))
        self._type_changed()
        if default_id is not None:
            index = self.entity_combo.findData(default_id)
            if index >= 0:
                self.entity_combo.setCurrentIndex(index)
                self._add_association()
        for field, ids in (initial_associations or {}).items():
            for record_id in ids:
                self._append_association(field, int(record_id))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton("Save", self)
        cancel = QPushButton("Cancel", self)
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _type_changed(self, *_args) -> None:
        field = str(self.type_combo.currentData() or "")
        self.entity_combo.clear()
        self.entity_combo.setEnabled(bool(field))
        for row in self._options.get(field, []):
            label = str(row.get("label") or f"Record {row['id']}")
            if row.get("archived"):
                label += " (Archived)"
            self.entity_combo.addItem(label, int(row["id"]))

    def associations(self) -> dict[str, Any]:
        result = {field: [] for _, field in ASSOCIATION_TYPES if field}
        for index in range(self.association_list.count()):
            field, record_id = self.association_list.item(index).data(Qt.UserRole)
            result[field].append(int(record_id))
        result["expand_team_members"] = bool(result["team_ids"])
        return result

    def _add_association(self) -> None:
        field = str(self.type_combo.currentData() or "")
        record_id = self.entity_combo.currentData()
        if not field or record_id is None:
            return
        self._append_association(field, int(record_id))

    def _append_association(self, field: str, record_id: int) -> None:
        key = (field, int(record_id))
        for index in range(self.association_list.count()):
            if tuple(self.association_list.item(index).data(Qt.UserRole)) == key:
                return
        type_label = next((label for label, value in ASSOCIATION_TYPES if value == field), field)
        entity_label = next(
            (str(row.get("label") or f"Record {record_id}")
             for row in self._options.get(field, []) if int(row["id"]) == record_id),
            f"Record {record_id}",
        )
        row = QListWidgetItem(
            f"{type_label}: {entity_label}",
            self.association_list,
        )
        row.setData(Qt.UserRole, key)


class Ics214ActivityLogPanel(QWidget):
    """One timeline whose apparent logs are filters or saved definitions."""

    def __init__(
        self,
        incident_id: Any | None = None,
        launch_context: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.incident_id = str(incident_id or incident_context.get_active_incident_id() or "")
        self.launch_context = launch_context or {}
        self._definitions: dict[str, dict[str, Any]] = {}
        self._options: dict[str, list[dict[str, Any]]] = {}
        self._labels: dict[str, dict[int, str]] = {}
        self._periods: list[dict[str, Any]] = []
        self._entries_by_id: dict[str, dict[str, Any]] = {}
        self._build_ui()
        self._reload_options()
        self._apply_launch_context()
        self._reload_definitions()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("ICS 214 — Incident Activity Stream", self)
        root.addWidget(title)

        saved_bar = QHBoxLayout()
        saved_bar.addWidget(QLabel("Saved log:", self))
        self.saved_combo = QComboBox(self)
        self.saved_combo.addItem("Ad hoc filter", None)
        self.saved_combo.currentIndexChanged.connect(self._saved_changed)
        saved_bar.addWidget(self.saved_combo, 1)
        save_filter = QPushButton("Save Current Filter", self)
        save_filter.clicked.connect(self._save_filter)
        saved_bar.addWidget(save_filter)
        root.addLayout(saved_bar)

        filters = QHBoxLayout()
        self.type_combo = QComboBox(self)
        for label, field in ASSOCIATION_TYPES:
            self.type_combo.addItem(label, field)
        self.type_combo.currentIndexChanged.connect(self._association_type_changed)
        self.entity_combo = QComboBox(self)
        self.entity_combo.setMinimumWidth(180)
        self.period_combo = QComboBox(self)
        self.period_combo.addItem("All operational periods", None)
        self.incident_wide = QCheckBox("Incident-wide", self)
        self.unassigned = QCheckBox("Unassigned", self)
        self.include_voided = QCheckBox("Include voided", self)
        refresh = QPushButton("Refresh", self)
        refresh.clicked.connect(self.refresh)
        for widget in (
            self.type_combo, self.entity_combo, self.period_combo, self.incident_wide,
            self.unassigned, self.include_voided, refresh,
        ):
            filters.addWidget(widget)
        root.addLayout(filters)

        actions = QHBoxLayout()
        add = QPushButton("Add Entry", self)
        void = QPushButton("Void", self)
        correct = QPushButton("Correct", self)
        export = QPushButton("Export ICS-214", self)
        add.clicked.connect(self._add_entry)
        void.clicked.connect(self._void_entry)
        correct.clicked.connect(self._correct_entry)
        export.clicked.connect(self._export)
        for button in (add, void, correct, export):
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.table = QTableView(self)
        self.model = QStandardItemModel(0, 5, self)
        self.model.setHorizontalHeaderLabels(["Occurred", "Entry", "Entered By", "Source", "Scope"])
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        apply_statusboard_table_behavior(self.table)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        root.addWidget(self.table, 1)

        self.status = QLabel(self)
        root.addWidget(self.status)

    def _apply_launch_context(self) -> None:
        category = str(self.launch_context.get("default_log_for_type") or "")
        raw_ref = str(self.launch_context.get("default_log_for_ref") or "")
        field_by_category = {
            "person": "person_ids", "individual": "person_ids", "team": "team_ids",
            "task": "task_ids", "section": "org_unit_ids", "org_unit": "org_unit_ids",
            "facility": "facility_ids", "resource": "resource_ids",
            "external_agency": "external_agency_ids",
        }
        field = field_by_category.get(category)
        if field:
            index = self.type_combo.findData(field)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
            value = raw_ref.split(":", 1)[-1] if raw_ref else ""
            option_index = self.entity_combo.findData(int(value)) if value.isdigit() else -1
            if option_index >= 0:
                self.entity_combo.setCurrentIndex(option_index)

    def _current_filter(self) -> EntryFilter:
        data: dict[str, Any] = {
            "incident_wide": True if self.incident_wide.isChecked() else None,
            "operational_period_id": self.period_combo.currentData(),
            "unassigned": self.unassigned.isChecked(),
            "include_voided": self.include_voided.isChecked(),
        }
        field = str(self.type_combo.currentData() or "")
        value = self.entity_combo.currentData()
        if field and value is not None:
            data[field] = [int(value)]
        return EntryFilter(**data)

    def _scope_text(self, entry: dict[str, Any]) -> str:
        parts = []
        if entry.get("incident_wide"):
            parts.append("Incident")
        labels = {
            "person_ids": "People", "team_ids": "Teams", "task_ids": "Tasks",
            "org_unit_ids": "Units", "facility_ids": "Facilities",
            "resource_ids": "Resources", "external_agency_ids": "Agencies",
        }
        for field, label in labels.items():
            values = entry.get(field) or []
            if values:
                resolved = [self._labels.get(field, {}).get(int(value), f"Record {value}") for value in values]
                parts.append(f"{label}: {', '.join(resolved)}")
        return "Unassigned" if not parts else "; ".join(parts)

    def refresh(self) -> None:
        self.model.removeRows(0, self.model.rowCount())
        if not self.incident_id:
            self.status.setText("No active incident")
            return
        try:
            rows = services.list_entries(self.incident_id, self._current_filter())
        except Exception as exc:
            self.status.setText(f"Unable to load entries: {exc}")
            return
        self._entries_by_id = {str(entry.get("id") or ""): entry for entry in rows}
        for entry in rows:
            occurred = str(entry.get("occurred_at") or "")
            try:
                occurred = datetime.fromisoformat(occurred.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            first = QStandardItem(occurred)
            first.setData(str(entry.get("id") or ""), Qt.UserRole)
            text = str(entry.get("text") or "")
            if entry.get("voided"):
                text = f"[VOID] {text}"
            self.model.appendRow([
                first,
                QStandardItem(text),
                QStandardItem(str(entry.get("created_by") or "")),
                QStandardItem(str(entry.get("source") or "")),
                QStandardItem(self._scope_text(entry)),
            ])
        self.status.setText(f"{len(rows)} entries")

    def _selected_entry_id(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return str(self.model.item(rows[0].row(), 0).data(Qt.UserRole) or "") or None

    def _add_entry(self) -> None:
        field = str(self.type_combo.currentData() or "")
        default_id = self.entity_combo.currentData()
        dialog = EntryDialog(
            self, options=self._options, default_field=field,
            default_id=int(default_id) if default_id is not None else None,
        )
        dialog.incident_wide.setChecked(self.incident_wide.isChecked())
        if not dialog.exec():
            return
        try:
            services.create_entry(self.incident_id, EntryCreate(
                text=dialog.text_edit.toPlainText(),
                incident_wide=dialog.incident_wide.isChecked(),
                created_by=_active_user(),
                **dialog.associations(),
            ))
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "ICS-214", f"Could not add entry:\n{exc}")

    def _void_entry(self) -> None:
        entry_id = self._selected_entry_id()
        if not entry_id:
            return
        reason, ok = QInputDialog.getText(self, "Void Entry", "Reason:")
        if not ok or not reason.strip():
            return
        services.void_entry(self.incident_id, entry_id, VoidRequest(
            voided_by=_active_user(), reason=reason.strip(),
        ))
        self.refresh()

    def _correct_entry(self) -> None:
        entry_id = self._selected_entry_id()
        rows = self.table.selectionModel().selectedRows()
        if not entry_id or not rows:
            return
        current = self.model.item(rows[0].row(), 1).text().removeprefix("[VOID] ")
        original = self._entries_by_id.get(entry_id, {})
        initial = {
            field: list(original.get(field) or [])
            for _, field in ASSOCIATION_TYPES if field
        }
        dialog = EntryDialog(
            self, text=current, title="Correct 214 Entry", options=self._options,
            initial_associations=initial,
        )
        dialog.incident_wide.setChecked(bool(original.get("incident_wide")))
        if not dialog.exec():
            return
        reason, ok = QInputDialog.getText(self, "Correction Reason", "Reason:")
        if not ok or not reason.strip():
            return
        services.correct_entry(self.incident_id, entry_id, CorrectionCreate(
            text=dialog.text_edit.toPlainText(),
            incident_wide=dialog.incident_wide.isChecked(),
            created_by=_active_user(), voided_by=_active_user(),
            void_reason=reason.strip(), **dialog.associations(),
        ))
        self.refresh()

    def _reload_definitions(self) -> None:
        try:
            definitions = services.list_log_definitions(self.incident_id)
        except Exception:
            definitions = []
        self._definitions = {str(item["id"]): item for item in definitions}
        self.saved_combo.blockSignals(True)
        self.saved_combo.clear()
        self.saved_combo.addItem("Ad hoc filter", None)
        for item in definitions:
            self.saved_combo.addItem(str(item.get("name") or "Saved log"), str(item["id"]))
        self.saved_combo.blockSignals(False)

    def _reload_options(self) -> None:
        try:
            self._options = services.association_options(self.incident_id) if self.incident_id else {}
            self._periods = services.list_operational_periods(self.incident_id) if self.incident_id else []
        except Exception:
            self._options = {}
            self._periods = []
        self._labels = {
            field: {int(row["id"]): str(row.get("label") or f"Record {row['id']}")
                    for row in rows}
            for field, rows in self._options.items()
        }
        self._association_type_changed()
        self.period_combo.clear()
        self.period_combo.addItem("All operational periods", None)
        for period in self._periods:
            label = f"OP {period.get('number') or period.get('id')}"
            if period.get("name"):
                label += f" — {period['name']}"
            self.period_combo.addItem(label, int(period["id"]))

    def _association_type_changed(self, *_args) -> None:
        field = str(self.type_combo.currentData() or "")
        self.entity_combo.clear()
        self.entity_combo.setEnabled(bool(field))
        if not field:
            return
        for row in self._options.get(field, []):
            label = str(row.get("label") or f"Record {row['id']}")
            if row.get("archived"):
                label = f"{label} (Archived)"
            self.entity_combo.addItem(label, int(row["id"]))

    def _save_filter(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Log", "Log name:")
        if not ok or not name.strip():
            return
        services.create_log_definition(self.incident_id, LogDefinitionCreate(
            name=name.strip(), filters=self._current_filter(), unit_name=name.strip(),
        ))
        self._reload_definitions()

    def _saved_changed(self) -> None:
        definition = self._definitions.get(str(self.saved_combo.currentData() or ""))
        if not definition:
            return
        filters = EntryFilter(**(definition.get("filters") or {}))
        self.incident_wide.setChecked(filters.incident_wide is True)
        self.unassigned.setChecked(filters.unassigned)
        self.include_voided.setChecked(filters.include_voided)
        period_index = self.period_combo.findData(filters.operational_period_id)
        self.period_combo.setCurrentIndex(max(0, period_index))
        for _, field in ASSOCIATION_TYPES:
            if field and getattr(filters, field):
                self.type_combo.setCurrentIndex(self.type_combo.findData(field))
                option_index = self.entity_combo.findData(int(getattr(filters, field)[0]))
                if option_index >= 0:
                    self.entity_combo.setCurrentIndex(option_index)
                break
        else:
            self.type_combo.setCurrentIndex(0)
        self.refresh()

    def _export(self) -> None:
        definition = self._definitions.get(str(self.saved_combo.currentData() or ""))
        unit_name = str((definition or {}).get("unit_name") or "Incident")
        try:
            result = services.export_log(self.incident_id, ExportRequest(
                filters=self._current_filter(), unit_name=unit_name,
            ))
            QMessageBox.information(self, "ICS-214 Export", f"Exported to:\n{result.file_path}")
        except Exception as exc:
            QMessageBox.warning(self, "ICS-214 Export", f"Export failed:\n{exc}")
