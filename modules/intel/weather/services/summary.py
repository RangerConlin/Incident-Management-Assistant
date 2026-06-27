"""Helpers for turning cached incident weather payloads into form-friendly summaries."""

from __future__ import annotations

from typing import Any, Iterable


def build_weather_form_payload(config: dict[str, Any] | None) -> dict[str, Any]:
    """Return a stable weather payload for form binding.

    The CAP forms expect a top-level ``weather`` object with broad text fields
    like ``conditions`` and segmented current/forecast strings.
    """

    config = config or {}
    payload = config.get("weather_payload") or {}
    metar_entries = payload.get("metar") or {}
    forecast_entries = payload.get("forecast") or {}
    advisories = payload.get("advisories") or []

    ordered_metars = _ordered_metar_entries(metar_entries, config.get("icao_codes") or [])
    ordered_forecasts = _ordered_forecast_entries(forecast_entries)

    current_local = _format_metar_summary(ordered_metars[0]) if len(ordered_metars) > 0 else ""
    current_enroute = _format_metar_summary(ordered_metars[1]) if len(ordered_metars) > 1 else current_local
    current_area = _format_metar_summary(ordered_metars[2]) if len(ordered_metars) > 2 else current_local

    forecast_local = _format_forecast_summary(ordered_forecasts[0]) if len(ordered_forecasts) > 0 else ""
    forecast_enroute = _format_forecast_summary(ordered_forecasts[1]) if len(ordered_forecasts) > 1 else forecast_local
    forecast_area = _format_forecast_summary(ordered_forecasts[2]) if len(ordered_forecasts) > 2 else forecast_local

    alert_summary = _format_alert_summary(advisories)
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
        "current": {
            "local": current_local,
            "enroute": current_enroute,
            "area_of_operations": current_area,
        },
        "forecast": {
            "local": forecast_local,
            "enroute": forecast_enroute,
            "area_of_operations": forecast_area,
        },
    }


def _ordered_metar_entries(metar_entries: dict[str, Any], ordered_codes: Iterable[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for code in ordered_codes:
        station = str(code).strip().upper()
        entry = metar_entries.get(station)
        if isinstance(entry, dict):
            results.append(entry)
            seen.add(station)
    for station, entry in metar_entries.items():
        station_code = str(station).strip().upper()
        if station_code in seen or not isinstance(entry, dict):
            continue
        results.append(entry)
    return results


def _ordered_forecast_entries(forecast_entries: dict[str, Any]) -> list[dict[str, Any]]:
    return [entry for entry in forecast_entries.values() if isinstance(entry, dict)]


def _format_metar_summary(entry: dict[str, Any] | None) -> str:
    if not entry:
        return ""
    station = str(entry.get("station") or "").strip()
    raw = str(entry.get("raw_text") or "").strip()
    decoded = entry.get("decoded") or {}
    if raw:
        return f"{station}: {raw}" if station else raw

    parts = []
    if station:
        parts.append(station)
    for key in ("temperature", "temp", "tempC"):
        value = decoded.get(key)
        if value not in (None, ""):
            parts.append(f"Temp {value}")
            break
    for key in ("windSpeed", "wspd"):
        value = decoded.get(key)
        if value not in (None, ""):
            parts.append(f"Wind {value}")
            break
    return " | ".join(parts)


def _format_forecast_summary(entry: dict[str, Any] | None) -> str:
    if not entry:
        return ""
    label = str(entry.get("label") or "").strip()
    periods = entry.get("periods") or []
    snippets: list[str] = []
    for item in periods[:2]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        temperature = item.get("temperature")
        details = str(item.get("detailed_text") or "").strip()
        line = name or "Forecast"
        if temperature not in (None, ""):
            line += f" {temperature}F"
        if details:
            line += f" {details}"
        snippets.append(line.strip())
    body = "; ".join(snippets)
    if label and body:
        return f"{label}: {body}"
    return label or body


def _format_alert_summary(advisories: list[Any]) -> str:
    labels: list[str] = []
    for entry in advisories[:3]:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("event") or entry.get("headline") or "").strip()
        if text:
            labels.append(text)
    return "; ".join(labels)


__all__ = ["build_weather_form_payload"]
