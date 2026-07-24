"""Turns the current WeatherManager state into a form-friendly summary.

Previously read the legacy flat `weather_payload` blob cached on the old
`weather_data` "config" document; rewritten against the new per-location
WeatherManager snapshots (weather_manager.py) since that document shape no
longer exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .weather_manager import WeatherManager


def build_weather_form_payload(manager: "WeatherManager") -> Dict[str, Any]:
    """Return a stable weather payload for form binding (ICS-208 etc).

    The CAP forms expect a top-level ``weather`` object with broad text
    fields like ``conditions`` and segmented current/forecast strings.
    """
    locations = manager.locations()
    summaries = []
    all_alerts: list[str] = []
    for location in locations[:3]:
        reading = manager.normalized_current(location.location_id)
        snap = manager.snapshot(location.location_id)
        current_text = _format_current(location.label, reading)
        forecast_text = _format_forecast(snap.forecast[:1] if snap else [])
        summaries.append({"current": current_text, "forecast": forecast_text})
        if snap:
            all_alerts.extend(a.event for a in snap.advisories if a.event)

    current_local = summaries[0]["current"] if len(summaries) > 0 else ""
    current_enroute = summaries[1]["current"] if len(summaries) > 1 else current_local
    current_area = summaries[2]["current"] if len(summaries) > 2 else current_local
    forecast_local = summaries[0]["forecast"] if len(summaries) > 0 else ""
    forecast_enroute = summaries[1]["forecast"] if len(summaries) > 1 else forecast_local
    forecast_area = summaries[2]["forecast"] if len(summaries) > 2 else forecast_local

    alert_summary = "; ".join(all_alerts[:3])
    conditions_parts = [
        part
        for part in (
            current_local,
            forecast_local,
            f"Alerts: {alert_summary}" if alert_summary else "",
        )
        if part
    ]
    conditions = " | ".join(conditions_parts)
    summary = "\n".join(
        part
        for part in (
            f"Current: {current_local}" if current_local else "",
            f"Forecast: {forecast_local}" if forecast_local else "",
            f"Alerts: {alert_summary}" if alert_summary else "",
        )
        if part
    )

    return {
        "conditions": conditions,
        "summary": summary,
        "alerts": alert_summary,
        "current": {"local": current_local, "enroute": current_enroute, "area_of_operations": current_area},
        "forecast": {"local": forecast_local, "enroute": forecast_enroute, "area_of_operations": forecast_area},
    }


def _format_current(label: str, reading: Dict[str, Any]) -> str:
    parts = [label]
    temp = reading.get("temperature_f")
    if temp is not None:
        parts.append(f"Temp {temp:.0f}F")
    wind = reading.get("wind_speed_kt")
    if wind is not None:
        parts.append(f"Wind {wind:.0f}kt")
    return " | ".join(parts)


def _format_forecast(periods) -> str:
    snippets = []
    for period in periods:
        name = period.name or "Forecast"
        line = name
        if period.temperature is not None:
            line += f" {period.temperature:.0f}F"
        if period.detailed_text:
            line += f" {period.detailed_text}"
        snippets.append(line.strip())
    return "; ".join(snippets)


__all__ = ["build_weather_form_payload"]
