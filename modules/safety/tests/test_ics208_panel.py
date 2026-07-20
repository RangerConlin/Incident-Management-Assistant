import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.safety.panels.ics208_panel import ICS208Panel


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_ics208_panel_loads_hazards_and_rebuilds_blocks(monkeypatch) -> None:
    app = _app()

    monkeypatch.setattr(
        "modules.safety.panels.ics208_panel.services.get_ics208",
        lambda incident_id, op: {
            "op_period": op,
            "op_period_from": "2026-07-20 0600",
            "op_period_to": "2026-07-20 1800",
            "prepared_by_name": "J. Smith",
            "prepared_by_position": "Safety Officer",
            "weather_summary": "Thunderstorms possible after 1500.",
            "site_safety_plan_required": True,
            "site_safety_plan_location": "OPS/SAFETY/site-plan-op3.docx",
            "safety_message": "",
        },
    )
    monkeypatch.setattr(
        "modules.safety.panels.ics208_panel.services.list_hazard_zones",
        lambda incident_id: [],
    )

    def fake_get(path, params=None):
        if path.endswith("/safety/hazards"):
            return [
                {
                    "id": 1,
                    "title": "Chainsaw Operations",
                    "location_text": "Division A",
                    "ppe": ["Helmet", "Eye Protection"],
                    "safety_language": "Only trained operators may run saws.",
                    "hazard_zone_ids": [],
                    "default_spe": {"band": "Very High"},
                },
                {
                    "id": 2,
                    "title": "Heat Stress",
                    "location_text": "Branch I",
                    "ppe": ["Hydration Pack"],
                    "safety_language": "Hydrate and rotate crews.",
                    "hazard_zone_ids": [],
                    "default_spe": {"band": "High"},
                },
            ]
        if path.endswith("/weather"):
            return {"weather_payload": {"alerts": [{"headline": "Heat Advisory"}]}}
        return {}

    monkeypatch.setattr("modules.safety.panels.ics208_panel.api_client.get", fake_get)
    monkeypatch.setattr(
        "modules.safety.panels.ics208_panel.build_weather_form_payload",
        lambda payload: {"summary": "Thunderstorms possible after 1500.", "alerts": "Heat Advisory"},
    )

    panel = ICS208Panel(incident_id="INC-1")
    app.processEvents()

    assert panel._total_hazards_value.text() == "2"
    assert panel._high_hazards_value.text() == "2"
    assert "Chainsaw Operations" in panel._hazards_block_edit.toPlainText()
    assert "Helmet" in panel._ppe_block_edit.toPlainText()
    assert "Hydrate and rotate crews." in panel._language_block_edit.toPlainText()
    assert "Heat Advisory" in panel._weather_alert_badges.text()


def test_ics208_panel_inserts_selected_blocks_into_final_message(monkeypatch) -> None:
    app = _app()

    monkeypatch.setattr("modules.safety.panels.ics208_panel.services.get_ics208", lambda *args, **kwargs: {})
    monkeypatch.setattr("modules.safety.panels.ics208_panel.services.list_hazard_zones", lambda incident_id: [])
    monkeypatch.setattr("modules.safety.panels.ics208_panel.api_client.get", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        "modules.safety.panels.ics208_panel.build_weather_form_payload",
        lambda payload: {"summary": "", "alerts": ""},
    )

    panel = ICS208Panel(incident_id="INC-2")
    panel._hazards_block_edit.setPlainText("Hazard summary block")
    panel._ppe_block_edit.setPlainText("PPE block")
    panel._language_block_edit.setPlainText("")
    panel._weather_block_edit.setPlainText("Weather block")
    panel._special_block_edit.setPlainText("Special block")
    panel._special_block_toggle.setChecked(True)
    panel._insert_selected_blocks()
    app.processEvents()

    final_text = panel._safety_message.toPlainText()
    assert "Hazard summary block" in final_text
    assert "PPE block" in final_text
    assert "Weather block" in final_text
    assert "Special block" in final_text
