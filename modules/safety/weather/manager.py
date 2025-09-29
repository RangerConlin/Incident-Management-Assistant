from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.settingsmanager import SettingsManager
from utils.state import AppState

from modules.safety import services as safety_services
from modules.safety.models.schemas import SafetyReportCreate

from modules.intel.utils import db_access as intel_db
from modules.intel.models import EnvSnapshot

from .api_clients import (
    HttpClient,
    nws_points,
    nws_forecast,
    nws_current_conditions,
    nws_active_alerts,
    nws_hwo_latest,
    adds_metar,
    adds_taf,
)

try:
    from notifications.services import get_notifier
    from notifications.models.notification import Notification
except Exception:  # Optional during tests
    def get_notifier():  # type: ignore
        class _N:
            def notify(self, *_: object, **__: object) -> None:
                pass

        return _N()
    class Notification:  # type: ignore
        def __init__(self, **_: object) -> None:
            pass


UTC = timezone.utc


@dataclass
class WeatherSettings:
    poll_minutes: int = 10
    play_sound: bool = True
    severity_filter: str = "Severe+"  # All | Moderate+ | Severe/Extreme
    dup_suppress_minutes: int = 30
    auto_log_severe: bool = True
    store_hourly_snapshots: bool = False
    override_role: str = "Safety Officer"
    tz_mode: str = "local"  # local | UTC


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _severe_level(alert: Dict[str, Any]) -> str:
    return (alert.get("properties", {}).get("severity") or "").strip()


def _is_severe(alert: Dict[str, Any]) -> bool:
    sev = _severe_level(alert).lower()
    return sev in {"severe", "extreme"}


class WeatherSafetyManager:
    """Provides live weather intelligence and alerting for Safety.

    Core responsibilities:
    - Fetch NWS forecasts, hourly and current conditions
    - Fetch aviation METAR/TAF for multiple stations
    - Monitor NWS active alerts for severe hazards, emit notifications and auto-log
    - Persist snapshots to the incident intel EnvSnapshot.weather_json
    - Basic caching to prevent duplicate alerts
    """

    def __init__(self, *, settings: Optional[SettingsManager] = None, client: Optional[HttpClient] = None) -> None:
        self._settings = settings or SettingsManager()
        self._client = client or HttpClient()
        self._latlon: Optional[Tuple[float, float]] = None
        self._override_enabled = False
        self._stations: List[str] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._alert_cache: Dict[str, float] = {}  # id -> unix ts
        self._alert_cache_path: Optional[Path] = None
        self._load_settings()

    # ---- Settings ---------------------------------------------------------
    def _load_settings(self) -> None:
        self.cfg = WeatherSettings(
            poll_minutes=int(self._settings.get("weather.pollIntervalMinutes", 10) or 10),
            play_sound=bool(self._settings.get("weather.playSound", True)),
            severity_filter=str(self._settings.get("weather.severityFilter", "Severe+") or "Severe+"),
            dup_suppress_minutes=int(self._settings.get("weather.dupSuppressMinutes", 30) or 30),
            auto_log_severe=bool(self._settings.get("weather.autoLogSevere", True)),
            store_hourly_snapshots=bool(self._settings.get("weather.storeHourlySnapshots", False)),
            override_role=str(self._settings.get("weather.overrideRole", "Safety Officer") or "Safety Officer"),
            tz_mode=str(self._settings.get("weather.tzMode", "local") or "local"),
        )

    def save_settings(self) -> None:
        self._settings.set("weather.pollIntervalMinutes", self.cfg.poll_minutes)
        self._settings.set("weather.playSound", self.cfg.play_sound)
        self._settings.set("weather.severityFilter", self.cfg.severity_filter)
        self._settings.set("weather.dupSuppressMinutes", self.cfg.dup_suppress_minutes)
        self._settings.set("weather.autoLogSevere", self.cfg.auto_log_severe)
        self._settings.set("weather.storeHourlySnapshots", self.cfg.store_hourly_snapshots)
        self._settings.set("weather.overrideRole", self.cfg.override_role)
        self._settings.set("weather.tzMode", self.cfg.tz_mode)

    # ---- Location management ---------------------------------------------
    def set_location_override(self, lat: float, lon: float) -> None:
        self._latlon = (lat, lon)
        self._override_enabled = True
        self._update_cache_path()

    def clear_location_override(self) -> None:
        self._latlon = None
        self._override_enabled = False
        self._update_cache_path()

    def _update_cache_path(self) -> None:
        inc = AppState.get_active_incident()
        if inc:
            root = Path("data") / "incidents"
            root.mkdir(parents=True, exist_ok=True)
            self._alert_cache_path = root / f"{inc}-weather-alert-cache.json"
            self._load_alert_cache()

    def _load_alert_cache(self) -> None:
        p = self._alert_cache_path
        if not p or not p.exists():
            self._alert_cache = {}
            return
        try:
            self._alert_cache = json.loads(p.read_text("utf-8"))
        except Exception:
            self._alert_cache = {}

    def _persist_alert_cache(self) -> None:
        try:
            if self._alert_cache_path:
                self._alert_cache_path.write_text(json.dumps(self._alert_cache), encoding="utf-8")
        except Exception:
            pass

    def get_location(self) -> Optional[Tuple[float, float]]:
        if self._override_enabled and self._latlon:
            return self._latlon
        # Try ICP location from active incident
        try:
            from models.database import get_incident_by_number

            inc_num = AppState.get_active_incident()
            if not inc_num:
                return None
            row = get_incident_by_number(inc_num)
            icp = (row or {}).get("icp_location")
            if isinstance(icp, str) and "," in icp:
                a, b = icp.split(",", 1)
                return float(a.strip()), float(b.strip())
        except Exception:
            pass
        return None

    # ---- Public fetch helpers --------------------------------------------
    def get_aviation(self, stations: List[str]) -> Dict[str, Any]:
        return {
            "metar": adds_metar(self._client, stations),
            "taf": adds_taf(self._client, stations),
        }

    def get_summary(self) -> Dict[str, Any]:
        loc = self.get_location()
        if not loc:
            raise RuntimeError("No location set; configure ICP or override")
        lat, lon = loc
        points = nws_points(self._client, lat, lon)
        current = nws_current_conditions(self._client, points)
        daily = nws_forecast(self._client, points, hourly=False)
        hourly = nws_forecast(self._client, points, hourly=True)
        alerts = nws_active_alerts(self._client, lat, lon)
        hwo = nws_hwo_latest(self._client, points)
        payload = {
            "fetched_at": _now_iso(),
            "lat": lat,
            "lon": lon,
            "nws": {
                "points": points,
                "current": current,
                "daily": daily,
                "hourly": hourly,
                "alerts": alerts,
                "hwo": hwo,
            },
        }
        return payload

    # ---- Persistence ------------------------------------------------------
    def _store_snapshot(self, payload: Dict[str, Any]) -> None:
        intel_db.ensure_incident_schema()
        with intel_db.incident_session() as session:
            snap = EnvSnapshot(op_period=int(AppState.get_active_op_period() or 0), weather_json=json.dumps(payload))
            session.add(snap)
            session.commit()

    # ---- Alert handling ---------------------------------------------------
    def _should_emit(self, alert_id: str) -> bool:
        now = time.time()
        last = self._alert_cache.get(alert_id)
        if last is None:
            self._alert_cache[alert_id] = now
            return True
        if now - last < max(60, self.cfg.dup_suppress_minutes * 60):
            return False
        self._alert_cache[alert_id] = now
        return True

    def _handle_alerts(self, alerts_payload: Dict[str, Any]) -> List[str]:
        emitted: List[str] = []
        features = alerts_payload.get("features") or []
        for f in features:
            aid = f.get("id") or f.get("properties", {}).get("id") or ""
            if not aid:
                continue
            if not _is_severe(f) and self.cfg.severity_filter.lower().startswith("severe"):
                continue
            if not self._should_emit(aid):
                continue
            props = f.get("properties", {})
            headline = props.get("headline") or props.get("event") or "Weather Alert"
            desc = props.get("description") or props.get("instruction") or ""
            eff = props.get("effective") or props.get("onset") or _now_iso()
            area = props.get("areaDesc") or ""

            # Notify UI
            try:
                get_notifier().notify(
                    Notification(
                        title=headline,
                        message=area or desc,
                        severity="error",
                        source="NWS",
                        entity_type="weather.alert",
                        entity_id=aid,
                    )
                )
            except Exception:
                pass

            # Auto-log Safety note
            if self.cfg.auto_log_severe:
                try:
                    inc = str(AppState.get_active_incident() or "")
                    payload = SafetyReportCreate(
                        time=datetime.fromisoformat(eff.replace("Z", "+00:00")),
                        location=area or None,
                        severity=_severe_level(f) or None,
                        notes=f"[AUTO] {headline}\n\n{desc}",
                        flagged=True,
                        reported_by="NWS",
                    )
                    safety_services.create_safety_report(inc, payload)
                except Exception:
                    pass

            emitted.append(aid)
        if emitted:
            self._persist_alert_cache()
        return emitted

    # ---- Poll loop --------------------------------------------------------
    def poll_once(self) -> Dict[str, Any]:
        data = self.get_summary()
        # persist snapshot (optionally hourly only to reduce footprint)
        if self.cfg.store_hourly_snapshots or (datetime.now().minute == 0):
            try:
                self._store_snapshot(data)
            except Exception:
                pass
        try:
            self._handle_alerts(data.get("nws", {}).get("alerts", {}))
        except Exception:
            pass
        return data

    def start_polling(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._update_cache_path()

        def _loop() -> None:
            backoff = 1
            while not self._stop.is_set():
                try:
                    self.poll_once()
                    backoff = 1
                except Exception:
                    # exponential backoff up to 10 minutes
                    backoff = min(backoff * 2, max(600, self.cfg.poll_minutes * 60))
                # sleep for poll interval or backoff
                sleep_for = max(60, self.cfg.poll_minutes * 60)
                if backoff > sleep_for:
                    sleep_for = backoff
                for _ in range(int(sleep_for // 1)):
                    if self._stop.is_set():
                        break
                    time.sleep(1)

        self._thread = threading.Thread(target=_loop, name="WeatherSafetyPoller", daemon=True)
        self._thread.start()

    def stop_polling(self) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2)

    # ---- Utilities --------------------------------------------------------
    def get_briefing_snippet(self, stations: Optional[List[str]] = None) -> str:
        try:
            summary = self.get_summary()
        except Exception as e:
            return f"Weather briefing unavailable: {e}"
        lat = summary.get("lat")
        lon = summary.get("lon")
        daily = summary.get("nws", {}).get("daily", {}).get("properties", {}).get("periods", [])
        alerts = summary.get("nws", {}).get("alerts", {}).get("features", [])
        hwo_text = (summary.get("nws", {}).get("hwo", {}) or {}).get("productText") or ""
        lines = [
            f"Weather Briefing — {datetime.utcnow().isoformat()}Z",
            f"Location: {lat:.4f}, {lon:.4f}",
            "",
            "Short Forecast:",
        ]
        for p in daily[:6]:  # roughly 3 days
            name = p.get("name")
            temp = p.get("temperature")
            unit = p.get("temperatureUnit")
            wind = p.get("windSpeed")
            short = p.get("shortForecast")
            lines.append(f"- {name}: {temp}{unit}, wind {wind}, {short}")
        if stations:
            try:
                av = self.get_aviation(stations)
                met = av.get("metar", {}).get("data", {})
                taf = av.get("taf", {}).get("data", {})
                lines.append("")
                lines.append("Aviation Notes:")
                lines.append(f"- METAR: {json.dumps(met)[:300]}...")
                lines.append(f"- TAF: {json.dumps(taf)[:300]}...")
            except Exception:
                pass
        if alerts:
            lines.append("")
            lines.append("Active Alerts:")
            for a in alerts[:5]:
                props = a.get("properties", {})
                lines.append(f"- {props.get('severity','')}: {props.get('event','')} — {props.get('headline','')}")
        if hwo_text:
            lines.append("")
            lines.append("Hazardous Weather Outlook:")
            lines.append("".join(hwo_text.splitlines()[:10]) + " …")
        return "\n".join(lines)
