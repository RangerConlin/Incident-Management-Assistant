"""Central weather API manager used by all UI components."""

from __future__ import annotations

import functools
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

# QtConcurrent.run is not available in some PySide6 builds (e.g., with Python 3.13).
# Provide a compatibility fallback using ThreadPoolExecutor and QTimer.singleShot
# to marshal results back onto the Qt main thread.
try:  # Prefer QtConcurrent when available for QFuture integration
    from PySide6.QtConcurrent import run as _qt_run  # type: ignore
    from PySide6.QtCore import QFutureWatcher  # type: ignore
    _HAS_QTCONCURRENT = True
except Exception:  # pragma: no cover - environment-dependent
    _qt_run = None  # type: ignore
    QFutureWatcher = None  # type: ignore
    _HAS_QTCONCURRENT = False
    import concurrent.futures as _futures
    _EXECUTOR = _futures.ThreadPoolExecutor(max_workers=4)

from ..data_providers.noaa_metar_taf import NoaaMetarProvider, NoaaTafProvider
from ..data_providers.noaa_forecast import NoaaForecastProvider
from ..data_providers.noaa_hwo import NoaaHwoProvider
from ..data_providers.noaa_nws_advisories import NoaaNwsAdvisoryProvider
from ..data_providers.lightning_stub import LightningStub
from ..models.advisory import Advisory
from ..models.lightning import LightningStrike
from ..models.readings import ForecastPeriod, MetarReading, TafReading
from . import cache, settings
from utils.incident_context import get_active_incident_id
from utils.api_client import api_client

LOGGER = logging.getLogger(__name__)


class WeatherApiManager(QObject):
    """Coordinates background weather data fetches and caching."""

    statusChanged = Signal(str)
    dataUpdated = Signal(dict)
    fetchFailed = Signal(str, object)
    alertsUpdated = Signal(list)
    lightningUpdated = Signal(list)
    forecastUpdated = Signal(dict)

    _instance: "WeatherApiManager" | None = None

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("weatherApiManager")
        self._metar_provider = NoaaMetarProvider()
        self._taf_provider = NoaaTafProvider()
        self._forecast_provider = NoaaForecastProvider()
        self._hwo_provider = NoaaHwoProvider()
        self._advisory_provider = NoaaNwsAdvisoryProvider()
        self._lightning_provider = LightningStub()
        self._watchers: List[QFutureWatcher] = [] if _HAS_QTCONCURRENT else []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_all)
        self._metar_cache: Dict[str, MetarReading] = {}
        self._taf_cache: Dict[str, TafReading] = {}
        self._advisory_cache: List[Advisory] = []
        self._lightning_cache: List[LightningStrike] = []
        self._forecast_cache: Dict[str, Dict[str, Any]] = {}
        self._hwo_payload: Dict[str, Any] | None = None
        config_path = Path("modules/intel/weather/settings/api_config.json")
        self._api_config = settings.load_api_config(config_path)
        interval = int(self._api_config.get("polling_minutes", 10))
        self.configure_polling(interval)
        self._load_cached_payloads()
        LOGGER.info("WeatherApiManager initialised with %s minute polling", interval)

    @classmethod
    def instance(cls) -> "WeatherApiManager":
        if cls._instance is None:
            cls._instance = WeatherApiManager()
        return cls._instance

    def configure_polling(self, minutes: int) -> None:
        minutes = max(minutes, 1)
        interval_ms = minutes * 60_000
        self._timer.start(interval_ms)
        self._last_polling_minutes = minutes
        self._save_settings_to_server(polling_minutes=minutes)
        LOGGER.debug("Polling interval set to %s minutes", minutes)

    def station_codes(self) -> list[str]:
        return list(getattr(self, "_last_icao_codes", []))

    def add_station_code(self, code: str) -> list[str]:
        station = code.strip().upper()
        if not station:
            return self.station_codes()
        stations = self.station_codes()
        if station not in stations:
            stations.append(station)
            self._save_settings_to_server(icao_codes=stations)
        return stations

    def remove_station_code(self, code: str) -> list[str]:
        station = code.strip().upper()
        stations = [item for item in self.station_codes() if item != station]
        self._save_settings_to_server(icao_codes=stations)
        self._metar_cache.pop(station, None)
        self._taf_cache.pop(station, None)
        self._publish_data()
        return stations

    def set_default_station(self, code: str) -> list[str]:
        station = code.strip().upper()
        stations = [item for item in self.station_codes() if item != station]
        if station:
            stations.insert(0, station)
        self._save_settings_to_server(icao_codes=stations)
        return stations

    def weather_location(self) -> tuple[Optional[float], Optional[float]]:
        return (
            getattr(self, "_last_latitude", None),
            getattr(self, "_last_longitude", None),
        )

    def location_presets(self) -> list[dict[str, Any]]:
        return list(getattr(self, "_location_presets", []))

    def active_location_preset(self) -> str:
        return str(getattr(self, "_active_location_preset", "") or "")

    def save_location_presets(
        self,
        presets: list[dict[str, Any]],
        *,
        active_preset: str | None = None,
    ) -> None:
        self._location_presets = [dict(item) for item in presets if isinstance(item, dict)]
        if active_preset is not None:
            self._active_location_preset = active_preset
        self._save_settings_to_server()

    def request_metar(self, icao_codes: Iterable[str]) -> None:
        codes = list({code.strip().upper() for code in icao_codes if code})
        if not codes:
            return
        self._save_settings_to_server(icao_codes=self._merge_station_codes(codes))
        LOGGER.debug("Requesting METAR data for %s", codes)
        self._run_async(
            functools.partial(self._metar_provider.fetch_metar, codes),
            self._on_metar_result,
            "metar",
        )

    def request_taf(self, icao_codes: Iterable[str]) -> None:
        codes = list({code.strip().upper() for code in icao_codes if code})
        if not codes:
            return
        self._save_settings_to_server(icao_codes=self._merge_station_codes(codes))
        LOGGER.debug("Requesting TAF data for %s", codes)
        self._run_async(
            functools.partial(self._taf_provider.fetch_taf, codes),
            self._on_taf_result,
            "taf",
        )

    def request_advisories(self, latitude: float, longitude: float) -> None:
        LOGGER.debug("Requesting advisories for lat=%s lon=%s", latitude, longitude)
        self._run_async(
            functools.partial(
                self._advisory_provider.fetch_advisories, latitude, longitude
            ),
            self._on_advisory_result,
            "advisories",
        )
        self._save_settings_to_server(latitude=latitude, longitude=longitude)

    def request_hwo(self, latitude: float, longitude: float) -> None:
        self._run_async(
            functools.partial(self._hwo_provider.fetch_hwo, latitude, longitude),
            self._on_hwo_result,
            "hwo",
        )
        self._save_settings_to_server(latitude=latitude, longitude=longitude)

    def request_forecast(self, latitude: float, longitude: float, label: str = "") -> None:
        location_key = self._forecast_key(latitude, longitude)
        self._run_async(
            functools.partial(self._forecast_provider.fetch_forecast, latitude, longitude),
            functools.partial(
                self._on_forecast_result,
                location_key=location_key,
                label=label,
                latitude=latitude,
                longitude=longitude,
            ),
            "forecast",
        )
        self._save_settings_to_server(latitude=latitude, longitude=longitude)

    def request_lightning(self, latitude: float, longitude: float, radius_nm: float) -> None:
        LOGGER.debug(
            "Requesting lightning for lat=%s lon=%s radius=%s", latitude, longitude, radius_nm
        )
        self._run_async(
            functools.partial(
                self._lightning_provider.fetch_recent_strikes,
                latitude,
                longitude,
                radius_nm,
            ),
            self._on_lightning_result,
            "lightning",
        )
        self._save_settings_to_server(latitude=latitude, longitude=longitude, radius_nm=radius_nm)

    def refresh_all(self) -> None:
        self.statusChanged.emit("Refreshing weather data…")
        LOGGER.info("WeatherApiManager refresh_all invoked")
        if self._metar_cache:
            self.request_metar(self._metar_cache.keys())
        if self._taf_cache:
            self.request_taf(self._taf_cache.keys())
        if self._forecast_cache:
            for item in list(self._forecast_cache.values()):
                self.request_forecast(
                    float(item.get("latitude", 0.0)),
                    float(item.get("longitude", 0.0)),
                    str(item.get("label", "")),
                )
        lat = getattr(self, "_last_latitude", None)
        lon = getattr(self, "_last_longitude", None)
        if lat is not None and lon is not None:
            self.request_hwo(float(lat), float(lon))
        if self._advisory_cache:
            self.alertsUpdated.emit([asdict(item) for item in self._advisory_cache])
        if self._lightning_cache:
            self.lightningUpdated.emit([asdict(item) for item in self._lightning_cache])
        self.statusChanged.emit("Weather data refreshed")
        self._publish_data()

    def _on_metar_result(self, readings: List[MetarReading]) -> None:
        try:
            LOGGER.info("METAR result: %d reading(s): %s", len(readings), ", ".join([r.station for r in readings]))
        except Exception:
            pass
        for reading in readings:
            self._metar_cache[reading.station] = reading
        cache.write_cache(
            "metar", {key: asdict(value) for key, value in self._metar_cache.items()}
        )
        self._publish_data()

    def _on_taf_result(self, tafs: List[TafReading]) -> None:
        try:
            LOGGER.info("TAF result: %d reading(s): %s", len(tafs), ", ".join([t.station for t in tafs]))
        except Exception:
            pass
        for taf in tafs:
            self._taf_cache[taf.station] = taf
        cache.write_cache(
            "taf", {key: asdict(value) for key, value in self._taf_cache.items()}
        )
        self._publish_data()

    def _on_advisory_result(self, advisories: List[Advisory]) -> None:
        self._advisory_cache = advisories
        cache.write_cache("advisories", {str(i): asdict(a) for i, a in enumerate(advisories)})
        self.alertsUpdated.emit([asdict(item) for item in advisories])
        self._publish_data()

    def _on_forecast_result(
        self,
        periods: List[ForecastPeriod],
        *,
        location_key: str,
        label: str,
        latitude: float,
        longitude: float,
    ) -> None:
        entry = {
            "label": label,
            "latitude": latitude,
            "longitude": longitude,
            "periods": [asdict(period) for period in periods],
        }
        self._forecast_cache[location_key] = entry
        cache.write_cache("forecast", self._forecast_cache)
        self.forecastUpdated.emit({location_key: entry})
        self._publish_data()

    def _on_lightning_result(self, strikes: List[LightningStrike]) -> None:
        self._lightning_cache = strikes
        cache.write_cache(
            "lightning", {str(i): asdict(a) for i, a in enumerate(strikes)}
        )
        self.lightningUpdated.emit([asdict(item) for item in strikes])

    def _on_hwo_result(self, payload: Dict[str, Any] | None) -> None:
        self._hwo_payload = payload or None
        cache.write_cache("hwo", payload or {})
        self._publish_data()

    def _publish_data(self) -> None:
        payload: Dict[str, Any] = {
            "metar": {key: asdict(value) for key, value in self._metar_cache.items()},
            "taf": {key: asdict(value) for key, value in self._taf_cache.items()},
            "advisories": [asdict(item) for item in self._advisory_cache],
            "lightning": [asdict(item) for item in self._lightning_cache],
            "forecast": self._forecast_cache,
            "hwo": self._hwo_payload,
        }
        self.dataUpdated.emit(payload)
        try:
            metar_ct = len(payload.get("metar", {}))
            taf_ct = len(payload.get("taf", {}))
            adv_ct = len(payload.get("advisories", []))
            ltg_ct = len(payload.get("lightning", []))
            LOGGER.debug(
                "Publish payload => metar:%d taf:%d adv:%d lightning:%d",
                metar_ct,
                taf_ct,
                adv_ct,
                ltg_ct,
            )
            cache.write_cache("last_payload_debug", payload)
            if metar_ct or taf_ct or adv_ct or ltg_ct:
                cache.write_cache("last_payload_debug_nonempty", payload)
            else:
                cache.write_cache("last_payload_debug_empty", payload)
        except Exception:  # pragma: no cover - debug path only
            pass
        self._save_settings_to_server()

    def _save_settings_to_server(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_nm: Optional[float] = None,
        icao_codes: Optional[list[str]] = None,
        polling_minutes: Optional[int] = None,
        active_location_preset: Optional[str] = None,
        location_presets: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        incident_id = get_active_incident_id()
        if not incident_id:
            return
        
        if latitude is not None:
            self._last_latitude = latitude
        if longitude is not None:
            self._last_longitude = longitude
        if radius_nm is not None:
            self._last_radius_nm = radius_nm
        if icao_codes is not None:
            self._last_icao_codes = icao_codes
        if polling_minutes is not None:
            self._last_polling_minutes = polling_minutes
        if active_location_preset is not None:
            self._active_location_preset = active_location_preset
        if location_presets is not None:
            self._location_presets = [dict(item) for item in location_presets if isinstance(item, dict)]
            
        payload = {
            "latitude": getattr(self, "_last_latitude", 39.8283),
            "longitude": getattr(self, "_last_longitude", -98.5795),
            "radius_nm": getattr(self, "_last_radius_nm", 25.0),
            "icao_codes": getattr(self, "_last_icao_codes", []),
            "polling_minutes": getattr(self, "_last_polling_minutes", 10),
            "active_location_preset": getattr(self, "_active_location_preset", ""),
            "location_presets": getattr(self, "_location_presets", []),
            "weather_payload": {
                "metar": {k: asdict(v) for k, v in self._metar_cache.items()},
                "taf": {k: asdict(v) for k, v in self._taf_cache.items()},
                "advisories": [asdict(item) for item in self._advisory_cache],
                "lightning": [asdict(item) for item in self._lightning_cache],
                "forecast": self._forecast_cache,
                "hwo": self._hwo_payload,
            }
        }
        
        try:
            if _HAS_QTCONCURRENT and _qt_run is not None:
                _qt_run(lambda: api_client.post(f"/api/incidents/{incident_id}/weather", json=payload))
            else:
                _EXECUTOR.submit(lambda: api_client.post(f"/api/incidents/{incident_id}/weather", json=payload))
        except Exception:
            LOGGER.exception("Failed to post weather config to server")

    def _load_cached_payloads(self) -> None:
        incident_id = get_active_incident_id()
        if incident_id:
            try:
                config = api_client.get(f"/api/incidents/{incident_id}/weather")
                if config:
                    self._last_latitude = config.get("latitude")
                    self._last_longitude = config.get("longitude")
                    self._last_radius_nm = config.get("radius_nm", 25.0)
                    self._last_icao_codes = config.get("icao_codes", [])
                    self._last_polling_minutes = config.get("polling_minutes", 10)
                    self._active_location_preset = str(config.get("active_location_preset") or "")
                    self._location_presets = [
                        dict(item)
                        for item in (config.get("location_presets") or [])
                        if isinstance(item, dict)
                    ]
            except Exception:
                LOGGER.warning("Could not load weather settings from server, using local fallback")

        cached_metar = cache.read_cache("metar") or {}
        for key, payload in cached_metar.items():
            self._metar_cache[key] = MetarReading(
                station=key,
                raw_text=payload.get("raw_text", ""),
            )
        cached_taf = cache.read_cache("taf") or {}
        for key, payload in cached_taf.items():
            self._taf_cache[key] = TafReading(
                station=key,
                raw_text=payload.get("raw_text", ""),
            )
        cached_adv = cache.read_cache("advisories") or {}
        self._advisory_cache = [
            Advisory(
                event=item.get("event", ""),
                severity=item.get("severity"),
                start=self._deserialize_datetime(item.get("start")),
                end=self._deserialize_datetime(item.get("end")),
                headline=item.get("headline"),
                description=item.get("description"),
                certainty=item.get("certainty"),
                urgency=item.get("urgency"),
                affected_areas=item.get("affected_areas"),
            )
            for item in cached_adv.values()
        ]
        cached_forecast = cache.read_cache("forecast") or {}
        self._forecast_cache = {
            str(key): value
            for key, value in cached_forecast.items()
            if isinstance(value, dict)
        }
        cached_hwo = cache.read_cache("hwo") or {}
        self._hwo_payload = cached_hwo if isinstance(cached_hwo, dict) and cached_hwo else None
        cached_lightning = cache.read_cache("lightning") or {}
        self._lightning_cache = []
        for item in cached_lightning.values():
            try:
                ts_str = item.get("timestamp")
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.now(timezone.utc)
                self._lightning_cache.append(
                    LightningStrike(
                        timestamp=ts,
                        latitude=float(item.get("latitude", 0.0)),
                        longitude=float(item.get("longitude", 0.0)),
                        amplitude=item.get("amplitude"),
                    )
                )
            except Exception:
                LOGGER.exception("Failed to parse cached lightning strike: %s", item)
        if self._metar_cache or self._taf_cache or self._advisory_cache or self._lightning_cache or self._forecast_cache or self._hwo_payload:
            self._publish_data()

    def _run_async(
        self,
        func: Callable[[], Any],
        callback: Callable[[Any], None],
        context: str,
    ) -> None:
        if _HAS_QTCONCURRENT and _qt_run is not None and QFutureWatcher is not None:
            watcher = QFutureWatcher()
            self._watchers.append(watcher)

            def _finished() -> None:
                try:
                    result = watcher.future().result()
                    callback(result)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("Weather fetch failed for %s", context)
                    self.fetchFailed.emit(context, exc)
                finally:
                    watcher.deleteLater()
                    if watcher in self._watchers:
                        self._watchers.remove(watcher)

            watcher.finished.connect(_finished)
            future = _qt_run(func)
            watcher.setFuture(future)
            return

        # Fallback path: use a thread pool and marshal results back to the UI thread
        future = _EXECUTOR.submit(func)  # type: ignore[name-defined]

        def _done(f):  # type: ignore[no-redef]
            try:
                result = f.result()
                QTimer.singleShot(0, lambda: callback(result))
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Weather fetch failed for %s", context)
                QTimer.singleShot(0, lambda: self.fetchFailed.emit(context, exc))

        future.add_done_callback(_done)

    def _merge_station_codes(self, icao_codes: Iterable[str]) -> list[str]:
        merged = self.station_codes()
        for code in icao_codes:
            station = code.strip().upper()
            if station and station not in merged:
                merged.append(station)
        return merged

    @staticmethod
    def _forecast_key(latitude: float, longitude: float) -> str:
        return f"{latitude:.4f},{longitude:.4f}"

    @staticmethod
    def _deserialize_datetime(value: Any) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:  # pragma: no cover - defensive
            return None


__all__ = ["WeatherApiManager"]
