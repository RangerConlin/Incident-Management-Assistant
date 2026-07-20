"""ICS-208 Safety Message panel — safety dashboard plus authored briefing."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from modules.intel.weather.services.summary import build_weather_form_payload
from modules.safety import services
from utils.api_client import api_client
from utils.app_signals import app_signals
from utils.itemview_delegates import RowOutlineTableWidget
from utils.state import AppState


class ICS208Panel(QWidget):
    """Safety Message (ICS-208) panel — dashboard-assisted authoring per op period."""

    def __init__(self, incident_id: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._hazard_rows: list[dict[str, Any]] = []
        self._hazard_zone_names: dict[int, str] = {}
        self._weather_alerts: list[str] = []
        self._build_ui()
        self._load()
        app_signals.opPeriodChanged.connect(self._on_op_period_changed)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        root.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_source_inputs_panel())
        splitter.addWidget(self._build_authoring_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([470, 760])
        root.addWidget(splitter, 1)

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._refresh_btn = QPushButton("Refresh")
        self._rebuild_btn = QPushButton("Rebuild Draft Blocks")
        self._insert_blocks_btn = QPushButton("Insert Selected Blocks Into Final Message")
        self._import_weather_btn = QPushButton("Import Cached Weather Summary")
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)

        self._save_btn.clicked.connect(self._save)
        self._refresh_btn.clicked.connect(self._load)
        self._rebuild_btn.clicked.connect(self._rebuild_draft_blocks)
        self._insert_blocks_btn.clicked.connect(self._insert_selected_blocks)
        self._import_weather_btn.clicked.connect(self._import_weather_summary)

        for widget in (
            self._save_btn,
            self._refresh_btn,
            self._rebuild_btn,
            self._insert_blocks_btn,
            self._import_weather_btn,
        ):
            row.addWidget(widget)
        row.addWidget(self._status_lbl, 1)
        return row

    def _build_source_inputs_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Source Inputs")
        layout.addWidget(title)

        layout.addWidget(self._build_operational_period_card())
        layout.addWidget(self._build_snapshot_card())
        layout.addWidget(self._build_hazards_card(), 1)
        layout.addWidget(self._build_weather_site_card())
        layout.addWidget(self._build_attention_card())
        return panel

    def _build_authoring_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Authoring Workspace")
        layout.addWidget(title)
        layout.addWidget(self._build_builder_card())
        layout.addWidget(self._build_final_message_card(), 1)
        layout.addWidget(self._build_footer_meta_card())
        return panel

    def _build_operational_period_card(self) -> QGroupBox:
        box = QGroupBox("Operational Period")
        form = QFormLayout(box)

        self._op_combo = QComboBox()
        for number in range(1, 100):
            self._op_combo.addItem(str(number), number)
        current_op = int(AppState.get_active_op_period() or 1)
        self._op_combo.setCurrentIndex(max(0, current_op - 1))
        self._op_combo.currentIndexChanged.connect(self._load)

        self._op_from = QLineEdit()
        self._op_to = QLineEdit()
        self._prepared_by_name = QLineEdit()
        self._prepared_by_position = QLineEdit()
        self._prepared_by_datetime = QLineEdit()

        form.addRow("Op Period", self._op_combo)
        form.addRow("From", self._op_from)
        form.addRow("To", self._op_to)
        form.addRow("Prepared By", self._prepared_by_name)
        form.addRow("Position", self._prepared_by_position)
        form.addRow("Prepared At", self._prepared_by_datetime)
        return box

    def _build_snapshot_card(self) -> QGroupBox:
        box = QGroupBox("Safety Snapshot")
        grid = QGridLayout(box)

        self._total_hazards_value = QLabel("0")
        self._high_hazards_value = QLabel("0")
        self._unresolved_hazards_value = QLabel("0")
        self._hazard_zones_value = QLabel("0")
        self._weather_alerts_value = QLabel("0")
        self._not_in_briefing_value = QLabel("0")

        stats = [
            ("Total Hazards", self._total_hazards_value),
            ("High SPE", self._high_hazards_value),
            ("Unresolved", self._unresolved_hazards_value),
            ("Hazard Zones", self._hazard_zones_value),
            ("Weather Alerts", self._weather_alerts_value),
            ("Not In Briefing", self._not_in_briefing_value),
        ]
        for index, (label, value) in enumerate(stats):
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            inner = QVBoxLayout(frame)
            inner.setContentsMargins(8, 8, 8, 8)
            inner.addWidget(QLabel(label))
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(value)
            grid.addWidget(frame, index // 3, index % 3)
        return box

    def _build_hazards_card(self) -> QGroupBox:
        box = QGroupBox("Current Hazards For This Operational Period")
        layout = QVBoxLayout(box)

        self._hazards_table = RowOutlineTableWidget(0, 4)
        self._hazards_table.setHorizontalHeaderLabels(["Include", "Hazard", "SPE", "Zone"])
        self._hazards_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._hazards_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._hazards_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hazards_table.verticalHeader().setVisible(False)
        self._hazards_table.verticalHeader().setDefaultSectionSize(34)
        header = self._hazards_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._hazards_table, 1)
        return box

    def _build_weather_site_card(self) -> QGroupBox:
        box = QGroupBox("Weather And Site Safety")
        layout = QVBoxLayout(box)

        self._weather_alert_badges = QLabel("No active alerts cached.")
        self._weather_alert_badges.setWordWrap(True)
        self._weather_summary = QPlainTextEdit()
        self._weather_summary.setPlaceholderText("Weather summary for this operational period.")
        self._weather_summary.setMinimumHeight(90)
        self._site_plan_required = QCheckBox("Site safety plan required")
        self._site_plan_location = QLineEdit()
        self._site_plan_location.setPlaceholderText("Site safety plan location / reference")

        layout.addWidget(self._weather_alert_badges)
        layout.addWidget(self._weather_summary)
        layout.addWidget(self._site_plan_required)
        layout.addWidget(self._site_plan_location)
        return box

    def _build_attention_card(self) -> QGroupBox:
        box = QGroupBox("Attention Needed")
        layout = QVBoxLayout(box)
        self._attention_items = QPlainTextEdit()
        self._attention_items.setReadOnly(True)
        self._attention_items.setMinimumHeight(100)
        layout.addWidget(self._attention_items)
        return box

    def _build_builder_card(self) -> QGroupBox:
        box = QGroupBox("Briefing Builder")
        layout = QVBoxLayout(box)

        self._hazards_block_toggle = QCheckBox("Selected Hazards Summary")
        self._hazards_block_toggle.setChecked(True)
        self._hazards_block_edit = self._builder_edit("Summarize the selected operational hazards.")

        self._ppe_block_toggle = QCheckBox("Required PPE")
        self._ppe_block_toggle.setChecked(True)
        self._ppe_block_edit = self._builder_edit("List common PPE expectations drawn from selected hazards.")

        self._language_block_toggle = QCheckBox("Standard Safety Language")
        self._language_block_toggle.setChecked(True)
        self._language_block_edit = self._builder_edit("Standard safety language from the selected hazards.")

        self._weather_block_toggle = QCheckBox("Weather Advisory")
        self._weather_block_toggle.setChecked(True)
        self._weather_block_edit = self._builder_edit("Weather summary and alert impacts.")

        self._special_block_toggle = QCheckBox("Special Instructions")
        self._special_block_toggle.setChecked(False)
        self._special_block_edit = self._builder_edit("Add any incident-specific safety instructions.")

        blocks = [
            (self._hazards_block_toggle, self._hazards_block_edit),
            (self._ppe_block_toggle, self._ppe_block_edit),
            (self._language_block_toggle, self._language_block_edit),
            (self._weather_block_toggle, self._weather_block_edit),
            (self._special_block_toggle, self._special_block_edit),
        ]
        for toggle, edit in blocks:
            layout.addWidget(toggle)
            layout.addWidget(edit)
        return box

    def _build_final_message_card(self) -> QGroupBox:
        box = QGroupBox("Final Authored Safety Message")
        layout = QVBoxLayout(box)
        self._safety_message = QPlainTextEdit()
        self._safety_message.setPlaceholderText(
            "Write the final operational safety message here. Use the builder blocks as support, but keep the final briefing in the safety officer's own words."
        )
        layout.addWidget(self._safety_message, 1)
        return box

    def _build_footer_meta_card(self) -> QGroupBox:
        box = QGroupBox("Document Status")
        grid = QGridLayout(box)
        self._footer_site_plan = QLabel("")
        self._footer_review_status = QLabel("Draft")
        self._footer_updated = QLabel("")
        grid.addWidget(QLabel("Site Plan"), 0, 0)
        grid.addWidget(self._footer_site_plan, 0, 1)
        grid.addWidget(QLabel("Review Status"), 0, 2)
        grid.addWidget(self._footer_review_status, 0, 3)
        grid.addWidget(QLabel("Last Updated"), 0, 4)
        grid.addWidget(self._footer_updated, 0, 5)
        return box

    def _builder_edit(self, placeholder: str) -> QPlainTextEdit:
        edit = QPlainTextEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMinimumHeight(72)
        return edit

    def _current_op(self) -> int:
        data = self._op_combo.currentData()
        return int(data) if data is not None else 1

    def _on_op_period_changed(self, op_data: object) -> None:
        number = 1
        if isinstance(op_data, dict):
            number = int(op_data.get("number", 1))
        elif isinstance(op_data, int):
            number = op_data
        self._op_combo.blockSignals(True)
        try:
            self._op_combo.setCurrentIndex(max(0, number - 1))
        finally:
            self._op_combo.blockSignals(False)
        self._load()

    def _load(self) -> None:
        if not self._incident_id:
            return
        self._status_lbl.setText("")
        self._load_ics208_doc()
        self._load_supporting_inputs()
        self._rebuild_draft_blocks()
        self._refresh_footer_meta()
        self._refresh_attention_needed()

    def _load_ics208_doc(self) -> None:
        data = services.get_ics208(self._incident_id, self._current_op())
        self._op_from.setText(data.get("op_period_from") or "")
        self._op_to.setText(data.get("op_period_to") or "")
        self._safety_message.setPlainText(data.get("safety_message") or "")
        self._site_plan_required.setChecked(bool(data.get("site_safety_plan_required", False)))
        self._site_plan_location.setText(data.get("site_safety_plan_location") or "")
        self._weather_summary.setPlainText(data.get("weather_summary") or "")
        self._prepared_by_name.setText(data.get("prepared_by_name") or "")
        self._prepared_by_position.setText(data.get("prepared_by_position") or "")
        self._prepared_by_datetime.setText(data.get("prepared_by_datetime") or "")
        self._footer_updated.setText(data.get("updated_at") or "")

    def _load_supporting_inputs(self) -> None:
        self._hazard_rows = self._fetch_incident_hazards()
        self._hazard_zone_names = self._fetch_hazard_zone_names()
        self._weather_alerts = self._fetch_weather_alerts()
        self._populate_hazards_table()
        self._refresh_snapshot()
        self._refresh_weather_badges()

    def _fetch_incident_hazards(self) -> list[dict[str, Any]]:
        if not self._incident_id:
            return []
        try:
            rows = api_client.get(
                f"/api/incidents/{self._incident_id}/safety/hazards",
                params={"op_period": self._current_op()},
            ) or []
        except Exception:
            rows = []

        def rank(row: dict[str, Any]) -> int:
            band = str(((row.get("spe_initial") or row.get("default_spe") or {}).get("band")) or "")
            order = {"Very High": 0, "High": 1, "Substantial": 2, "Possible": 3, "Slight": 4}
            return order.get(band, 5)

        return sorted(rows, key=rank)

    def _fetch_hazard_zone_names(self) -> dict[int, str]:
        if not self._incident_id:
            return {}
        zones = services.list_hazard_zones(self._incident_id)
        names: dict[int, str] = {}
        for zone in zones:
            zone_id = getattr(zone, "id", None)
            if zone_id is not None:
                names[int(zone_id)] = getattr(zone, "name", "") or ""
        return names

    def _fetch_weather_alerts(self) -> list[str]:
        if not self._incident_id:
            return []
        try:
            weather_config = api_client.get(f"/api/incidents/{self._incident_id}/weather") or {}
        except Exception:
            return []
        payload = build_weather_form_payload(weather_config)
        alerts_text = str(payload.get("alerts") or "").strip()
        if not alerts_text:
            return []
        return [line.strip() for line in alerts_text.splitlines() if line.strip()]

    def _populate_hazards_table(self) -> None:
        self._hazards_table.setRowCount(len(self._hazard_rows))
        for row_index, hazard in enumerate(self._hazard_rows):
            include_checkbox = QCheckBox()
            include_checkbox.setChecked(self._hazard_is_selected_by_default(hazard))
            include_checkbox.stateChanged.connect(self._on_hazard_selection_changed)

            zone_name = self._zone_name_for_hazard(hazard)
            spe_band = str(((hazard.get("spe_initial") or hazard.get("default_spe") or {}).get("band")) or "")
            hazard_title = str(hazard.get("title") or "")

            self._hazards_table.setCellWidget(row_index, 0, include_checkbox)
            hazard_item = QTableWidgetItem(hazard_title)
            hazard_item.setData(Qt.ItemDataRole.UserRole, hazard)
            self._hazards_table.setItem(row_index, 1, hazard_item)
            self._hazards_table.setItem(row_index, 2, QTableWidgetItem(spe_band))
            self._hazards_table.setItem(row_index, 3, QTableWidgetItem(zone_name))
        if self._hazard_rows:
            self._hazards_table.selectRow(0)

    def _hazard_is_selected_by_default(self, hazard: dict[str, Any]) -> bool:
        band = str(((hazard.get("spe_initial") or hazard.get("default_spe") or {}).get("band")) or "")
        if band in {"Very High", "High"}:
            return True
        return not bool(hazard.get("spe_residual"))

    def _zone_name_for_hazard(self, hazard: dict[str, Any]) -> str:
        zone_ids = hazard.get("hazard_zone_ids") or []
        if not zone_ids:
            return ""
        names = [self._hazard_zone_names.get(int(zone_id), "") for zone_id in zone_ids if str(zone_id).isdigit()]
        return ", ".join([name for name in names if name])

    def _selected_hazards(self) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for row in range(self._hazards_table.rowCount()):
            checkbox = self._hazards_table.cellWidget(row, 0)
            item = self._hazards_table.item(row, 1)
            if not isinstance(checkbox, QCheckBox) or item is None:
                continue
            if checkbox.isChecked():
                hazard = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(hazard, dict):
                    selected.append(hazard)
        return selected

    def _refresh_snapshot(self) -> None:
        selected = self._selected_hazards()
        unresolved = [h for h in self._hazard_rows if not bool(h.get("spe_residual"))]
        high_hazards = [
            h
            for h in self._hazard_rows
            if str(((h.get("spe_initial") or h.get("default_spe") or {}).get("band")) or "") in {"Very High", "High"}
        ]
        not_in_briefing = [h for h in high_hazards if h not in selected]

        self._total_hazards_value.setText(str(len(self._hazard_rows)))
        self._high_hazards_value.setText(str(len(high_hazards)))
        self._unresolved_hazards_value.setText(str(len(unresolved)))
        self._hazard_zones_value.setText(str(len(self._hazard_zone_names)))
        self._weather_alerts_value.setText(str(len(self._weather_alerts)))
        self._not_in_briefing_value.setText(str(len(not_in_briefing)))

    def _refresh_weather_badges(self) -> None:
        if self._weather_alerts:
            self._weather_alert_badges.setText(" | ".join(self._weather_alerts))
        else:
            self._weather_alert_badges.setText("No active alerts cached.")

    def _refresh_footer_meta(self) -> None:
        self._footer_site_plan.setText(self._site_plan_location.text().strip())
        self._footer_review_status.setText("Draft" if self._safety_message.toPlainText().strip() else "Not Started")

    def _refresh_attention_needed(self) -> None:
        issues: list[str] = []
        selected = self._selected_hazards()
        high_hazards = [
            h
            for h in self._hazard_rows
            if str(((h.get("spe_initial") or h.get("default_spe") or {}).get("band")) or "") in {"Very High", "High"}
        ]
        missing_high = [h for h in high_hazards if h not in selected]
        if missing_high:
            issues.append(f"{len(missing_high)} high-SPE hazards are not included in the briefing selection.")
        if not self._prepared_by_name.text().strip():
            issues.append("Prepared By is blank.")
        if self._site_plan_required.isChecked() and not self._site_plan_location.text().strip():
            issues.append("Site safety plan is marked required but no reference is listed.")
        if self._weather_summary.toPlainText().strip() and not self._weather_block_toggle.isChecked():
            issues.append("Weather summary exists but the Weather Advisory block is not selected.")
        if not issues:
            issues.append("No immediate gaps detected.")
        self._attention_items.setPlainText("\n".join(f"- {issue}" for issue in issues))

    def _rebuild_draft_blocks(self) -> None:
        hazards = self._selected_hazards()
        self._hazards_block_edit.setPlainText(self._build_hazards_summary(hazards))
        self._ppe_block_edit.setPlainText(self._build_ppe_summary(hazards))
        self._language_block_edit.setPlainText(self._build_safety_language_summary(hazards))
        self._weather_block_edit.setPlainText(self._build_weather_block())
        self._refresh_snapshot()
        self._refresh_footer_meta()
        self._refresh_attention_needed()
        self._status_lbl.setText("Draft blocks rebuilt from current source inputs.")

    def _build_hazards_summary(self, hazards: list[dict[str, Any]]) -> str:
        if not hazards:
            return ""
        lines = []
        for hazard in hazards:
            band = str(((hazard.get("spe_initial") or hazard.get("default_spe") or {}).get("band")) or "")
            title = str(hazard.get("title") or "")
            location = str(hazard.get("location_text") or "")
            parts = [title]
            if band:
                parts.append(f"SPE: {band}")
            if location:
                parts.append(location)
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    def _build_ppe_summary(self, hazards: list[dict[str, Any]]) -> str:
        items: list[str] = []
        seen: set[str] = set()
        for hazard in hazards:
            for item in hazard.get("ppe") or []:
                text = str(item).strip()
                if not text:
                    continue
                key = text.casefold()
                if key in seen:
                    continue
                seen.add(key)
                items.append(text)
        return ", ".join(items)

    def _build_safety_language_summary(self, hazards: list[dict[str, Any]]) -> str:
        blocks = []
        for hazard in hazards:
            text = str(hazard.get("safety_language") or "").strip()
            if text:
                blocks.append(text)
        return "\n\n".join(blocks)

    def _build_weather_block(self) -> str:
        text = self._weather_summary.toPlainText().strip()
        if not text:
            return ""
        if self._weather_alerts:
            alerts = "; ".join(self._weather_alerts)
            return f"Alerts: {alerts}\n\n{text}"
        return text

    def _insert_selected_blocks(self) -> None:
        parts: list[str] = []
        for toggle, edit in (
            (self._hazards_block_toggle, self._hazards_block_edit),
            (self._ppe_block_toggle, self._ppe_block_edit),
            (self._language_block_toggle, self._language_block_edit),
            (self._weather_block_toggle, self._weather_block_edit),
            (self._special_block_toggle, self._special_block_edit),
        ):
            if toggle.isChecked():
                text = edit.toPlainText().strip()
                if text:
                    parts.append(text)
        if not parts:
            QMessageBox.information(self, "No Blocks Selected", "Select at least one populated block first.")
            return
        self._safety_message.setPlainText("\n\n".join(parts))
        self._refresh_footer_meta()
        self._status_lbl.setText("Selected blocks inserted into the final authored safety message.")

    def _save(self) -> None:
        if not self._incident_id:
            QMessageBox.warning(self, "No Incident", "Select an incident before saving.")
            return
        payload = {
            "op_period": self._current_op(),
            "op_period_from": self._op_from.text().strip(),
            "op_period_to": self._op_to.text().strip(),
            "safety_message": self._safety_message.toPlainText().strip(),
            "site_safety_plan_required": self._site_plan_required.isChecked(),
            "site_safety_plan_location": self._site_plan_location.text().strip(),
            "weather_summary": self._weather_summary.toPlainText().strip(),
            "prepared_by_name": self._prepared_by_name.text().strip(),
            "prepared_by_position": self._prepared_by_position.text().strip(),
            "prepared_by_datetime": self._prepared_by_datetime.text().strip(),
        }
        try:
            saved = services.save_ics208(self._incident_id, payload)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return
        self._footer_updated.setText(str(saved.get("updated_at") or saved.get("prepared_by_datetime") or ""))
        self._refresh_footer_meta()
        self._status_lbl.setText("Saved.")

    def _import_weather_summary(self) -> None:
        if not self._incident_id:
            return
        try:
            weather_config = api_client.get(f"/api/incidents/{self._incident_id}/weather") or {}
        except Exception:
            QMessageBox.warning(self, "Import Failed", "Could not load incident weather data.")
            return
        weather_payload = build_weather_form_payload(weather_config)
        weather_summary = str(weather_payload.get("summary") or "").strip()
        if not weather_summary:
            QMessageBox.information(self, "No Weather Available", "No cached weather summary is available yet.")
            return
        self._weather_summary.setPlainText(weather_summary)
        alerts_text = str(weather_payload.get("alerts") or "").strip()
        self._weather_alerts = [line.strip() for line in alerts_text.splitlines() if line.strip()]
        self._refresh_weather_badges()
        self._refresh_snapshot()
        self._refresh_attention_needed()
        self._status_lbl.setText("Imported weather summary.")

    def _on_hazard_selection_changed(self) -> None:
        self._refresh_snapshot()
        self._refresh_attention_needed()
