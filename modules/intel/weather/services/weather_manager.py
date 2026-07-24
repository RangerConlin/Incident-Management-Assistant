"""Weather manager — replaces the old WeatherApiManager.

Responsibilities are deliberately narrower than the old manager:
  - own the incident's location list (loaded from/persisted to the weather
    router via weather_repository_client), including auto-populated stations
  - poll NOAA providers per location on a QTimer
  - emit narrow, typed signals per data class instead of one big blob
  - record each successful poll to weather_history (for the trend chart)
  - emit weather alerts (new advisories) through the shared notifications
    system rather than a bespoke acknowledgement store

Every provider call site produces either a successful callback or an
explicit `fetchError` signal + log — never a bare `except: pass`.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

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

from ..data_providers.noaa_forecast import NoaaForecastProvider
from ..data_providers.noaa_hwo import NoaaHwoProvider
from ..data_providers.noaa_metar_taf import NoaaMetarProvider, NoaaTafProvider
from ..data_providers.noaa_nws_advisories import NoaaNwsAdvisoryProvider
from ..models.advisory import Advisory
from ..models.location import WeatherLocation, WeatherSnapshot
from ..models.readings import MetarReading
from . import history_recorder
from . import runway_api
from . import weather_repository_client as client

LOGGER = logging.getLogger(__name__)


def _normalize_metar_reading(metar: Optional[MetarReading]) -> Dict[str, Any]:
    """Convert AWC's raw METAR JSON (metar.decoded) into canonical units.

    AWC field names: temp/dewp in Celsius, wdir/wspd/wgst in degrees/knots,
    visib in statute miles, altim in hPa, clouds: [{cover, base_ft}, ...].
    Relative humidity isn't reported directly — computed from temp/dewpoint
    via the Magnus approximation (a real calculation, not a fabricated value).
    """
    if metar is None or not metar.decoded:
        return {}
    d = metar.decoded
    temp_c = d.get("temp")
    dewp_c = d.get("dewp")
    out: Dict[str, Any] = {
        "temperature_f": (temp_c * 9.0 / 5.0 + 32.0) if isinstance(temp_c, (int, float)) else None,
        "wind_speed_kt": d.get("wspd"),
        "wind_gust_kt": d.get("wgst"),
        "wind_direction_deg": d.get("wdir") if isinstance(d.get("wdir"), (int, float)) else None,
        "visibility_sm": _coerce_visibility(d.get("visib")),
        "barometric_pressure_hpa": d.get("altim"),
    }
    clouds = d.get("clouds") or []
    ceiling_ft = None
    for layer in clouds:
        if isinstance(layer, dict) and layer.get("cover") in ("BKN", "OVC"):
            base = layer.get("base")
            if isinstance(base, (int, float)):
                ceiling_ft = float(base)
                break
    out["ceiling_ft"] = ceiling_ft
    if isinstance(temp_c, (int, float)) and isinstance(dewp_c, (int, float)):
        try:
            a, b = 17.625, 243.04
            gamma_t = (a * temp_c) / (b + temp_c)
            gamma_td = (a * dewp_c) / (b + dewp_c)
            out["relative_humidity_pct"] = 100.0 * math.exp(gamma_td - gamma_t)
        except (ValueError, ZeroDivisionError):
            out["relative_humidity_pct"] = None
    else:
        out["relative_humidity_pct"] = None
    return out


def _coerce_visibility(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("+", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


class WeatherManager(QObject):
    """Coordinates background weather data fetches and caching for one incident."""

    locationsChanged = Signal(list)  # list[WeatherLocation]
    snapshotUpdated = Signal(str, object)  # location_id, WeatherSnapshot
    alertsUpdated = Signal(str, list)  # location_id, list[Advisory]
    hwoUpdated = Signal(str, str)  # location_id, text
    fetchError = Signal(str, str, str)  # location_id, provider_name, message
    pollStarted = Signal()
    pollFinished = Signal()
    _marshal = Signal(object)  # internal: runs a zero-arg callable on the main thread

    def __init__(self, incident_id: str) -> None:
        super().__init__()
        self.setObjectName(f"weatherManager-{incident_id}")
        self._incident_id = incident_id
        self._metar_provider = NoaaMetarProvider()
        self._taf_provider = NoaaTafProvider()
        self._forecast_provider = NoaaForecastProvider()
        self._hwo_provider = NoaaHwoProvider()
        self._advisory_provider = NoaaNwsAdvisoryProvider()
        self._watchers: List[Any] = []
        # Qt's default AutoConnection becomes a queued connection whenever the
        # emitting thread differs from this QObject's (main-thread) affinity,
        # so this is the thread-safe way for the ThreadPoolExecutor fallback
        # path to marshal a callback onto the main thread — QTimer.singleShot
        # from a worker thread has no event loop of its own to fire on.
        self._marshal.connect(lambda fn: fn())
        self._locations: Dict[str, WeatherLocation] = {}
        self._snapshots: Dict[str, WeatherSnapshot] = {}
        self._thresholds: Dict[str, Any] = {}
        self._seen_advisory_keys: Dict[str, set] = {}
        self._pending_polls = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_all)
        self._load_config()
        self.sync_auto_locations()
        # QTimer.start(interval) only fires *after* the interval elapses —
        # without this, a freshly-opened manager (or a station added just
        # now) would show no data for up to a full polling interval.
        if self._locations:
            self.refresh_all()

    # -- config / locations --------------------------------------------------

    def _load_config(self) -> None:
        try:
            config = client.get_config(self._incident_id)
        except Exception:
            LOGGER.exception("Failed to load weather config for incident %s", self._incident_id)
            config = {}
        self._thresholds = config.get("thresholds") or {}
        self._locations = {
            loc["location_id"]: WeatherLocation.from_api(loc)
            for loc in config.get("locations", [])
            if loc.get("location_id")
        }
        polling_minutes = int(config.get("polling_minutes") or 10)
        self.configure_polling(polling_minutes)
        self.locationsChanged.emit(list(self._locations.values()))

    def configure_polling(self, minutes: int) -> None:
        minutes = max(1, minutes)
        self._polling_minutes = minutes
        self._timer.start(minutes * 60_000)

    def polling_minutes(self) -> int:
        return getattr(self, "_polling_minutes", 10)

    def locations(self) -> List[WeatherLocation]:
        return list(self._locations.values())

    def default_location(self) -> Optional[WeatherLocation]:
        for loc in self._locations.values():
            if loc.is_default:
                return loc
        return next(iter(self._locations.values()), None)

    def thresholds(self) -> Dict[str, Any]:
        return dict(self._thresholds)

    def reload_config(self) -> None:
        """Re-fetch config from the server (call after editing thresholds/polling)."""
        self._load_config()

    def snapshot(self, location_id: str) -> Optional[WeatherSnapshot]:
        return self._snapshots.get(location_id)

    def normalized_current(self, location_id: str) -> Dict[str, Any]:
        """Canonical-unit current reading (temperature_f, wind_gust_kt, etc.) for a location."""
        snap = self._snapshots.get(location_id)
        if snap is None:
            return {}
        return _normalize_metar_reading(snap.metar)

    @staticmethod
    def _fetch_runway_ends(icao_codes: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Query NOAA AWC's airport endpoint once, at station-creation time.

        Never fabricates: any lookup failure returns an empty list, and
        callers simply omit the crosswind readout for that station.
        """
        if not icao_codes:
            return []
        try:
            return [r.to_dict() for r in runway_api.fetch_runways(icao_codes[0])]
        except Exception:
            LOGGER.exception("Runway lookup failed for %s", icao_codes[0])
            return []

    def add_manual_location(
        self,
        *,
        label: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        icao_codes: Optional[List[str]] = None,
        is_default: bool = False,
    ) -> None:
        try:
            config = client.add_location(
                self._incident_id,
                label=label,
                latitude=latitude,
                longitude=longitude,
                icao_codes=icao_codes,
                is_default=is_default,
                runway_ends=self._fetch_runway_ends(icao_codes),
            )
        except Exception:
            LOGGER.exception("Failed to add weather location '%s'", label)
            return
        self._apply_config_locations(config)
        # Poll immediately rather than waiting for the next timer tick, so a
        # newly-added station shows data right away instead of up to
        # `polling_minutes` later.
        self.refresh_all()

    def remove_location(self, location_id: str) -> None:
        try:
            config = client.delete_location(self._incident_id, location_id)
        except Exception:
            LOGGER.exception("Failed to remove weather location %s", location_id)
            return
        self._apply_config_locations(config)

    def set_default_location(self, location_id: str) -> None:
        try:
            config = client.set_default_location(self._incident_id, location_id)
        except Exception:
            LOGGER.exception("Failed to set default weather location %s", location_id)
            return
        self._apply_config_locations(config)

    def _apply_config_locations(self, config: Dict[str, Any]) -> None:
        self._locations = {
            loc["location_id"]: WeatherLocation.from_api(loc)
            for loc in config.get("locations", [])
            if loc.get("location_id")
        }
        self.locationsChanged.emit(list(self._locations.values()))

    def sync_auto_locations(self) -> None:
        """Add/update auto-populated stations from Initial Response and facilities.

        Only real, present data becomes a station — no fabrication. Stations
        auto-populated here are never editable/removable from the Stations
        tab; they retire on the next sync if the source record disappears.
        """
        existing_ref_ids = {
            loc.source_ref_id for loc in self._locations.values() if loc.source_ref_id
        }

        try:
            aircraft_info = client.get_initial_response_aircraft_info(self._incident_id)
        except Exception:
            LOGGER.exception("Failed to read Initial Response aircraft info")
            aircraft_info = {}
        for key, label in (("departure_airport", "Departure"), ("destination_airport", "Destination")):
            code = str(aircraft_info.get(key) or "").strip().upper()
            if not code:
                continue
            ref_id = f"initial_response:{key}"
            if ref_id in existing_ref_ids:
                continue
            try:
                config = client.add_location(
                    self._incident_id,
                    label=f"Overdue A/C — {label} ({code})",
                    icao_codes=[code],
                    source="initial_response",
                    source_ref_id=ref_id,
                    runway_ends=self._fetch_runway_ends([code]),
                )
                self._apply_config_locations(config)
            except Exception:
                LOGGER.exception("Failed to auto-add Initial Response station %s", code)

        try:
            facilities = client.list_airport_facilities(self._incident_id)
        except Exception:
            LOGGER.exception("Failed to read airport/helibase facilities")
            facilities = []
        for facility in facilities:
            facility_id = str(facility.get("id") or "")
            if not facility_id:
                continue
            ref_id = f"facility:{facility_id}"
            if ref_id in existing_ref_ids:
                continue
            icao_code = str(facility.get("icao_code") or "").strip().upper()
            try:
                config = client.add_location(
                    self._incident_id,
                    label=str(facility.get("name") or "Facility"),
                    latitude=facility.get("latitude"),
                    longitude=facility.get("longitude"),
                    icao_codes=[icao_code] if icao_code else [],
                    source="facility",
                    source_ref_id=ref_id,
                    runway_ends=self._fetch_runway_ends([icao_code] if icao_code else []),
                )
                self._apply_config_locations(config)
            except Exception:
                LOGGER.exception("Failed to auto-add facility station %s", facility_id)

    # -- polling --------------------------------------------------------------

    def refresh_all(self) -> None:
        locations = list(self._locations.values())
        if not locations:
            return
        self._pending_polls = len(locations)
        self.pollStarted.emit()
        for location in locations:
            self._poll_location(location)

    def _poll_one_done(self) -> None:
        self._pending_polls = max(0, self._pending_polls - 1)
        if self._pending_polls == 0:
            self.pollFinished.emit()

    def _poll_location(self, location: WeatherLocation) -> None:
        # Each location's poll batch gets its own independent tick closure —
        # never shared mutable state on self, since multiple locations poll
        # concurrently and their async callbacks can interleave.
        remaining = {"count": 0}

        def _tick() -> None:
            remaining["count"] -= 1
            if remaining["count"] <= 0:
                self._poll_one_done()

        jobs: List[Callable[[Callable[[], None]], None]] = []

        if location.icao_codes:
            jobs.append(lambda tick: self._fetch_metar(location, tick))
            jobs.append(lambda tick: self._fetch_taf(location, tick))
        if location.latitude is not None and location.longitude is not None:
            jobs.append(lambda tick: self._fetch_forecast(location, tick))
            jobs.append(lambda tick: self._fetch_advisories(location, tick))
            jobs.append(lambda tick: self._fetch_hwo(location, tick))

        if not jobs:
            self._poll_one_done()
            return

        remaining["count"] = len(jobs)
        for job in jobs:
            job(_tick)

    def _run_async(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        *,
        location_id: str,
        provider_name: str,
        tick: Callable[[], None],
    ) -> None:
        def _on_error(exc: BaseException) -> None:
            LOGGER.exception("Weather fetch failed for %s/%s", location_id, provider_name)
            self.fetchError.emit(location_id, provider_name, str(exc))
            tick()

        def _on_ok(result: Any) -> None:
            try:
                on_success(result)
            finally:
                tick()

        if _HAS_QTCONCURRENT and _qt_run is not None and QFutureWatcher is not None:
            watcher = QFutureWatcher()
            self._watchers.append(watcher)

            def _finished() -> None:
                try:
                    result = watcher.future().result()
                except Exception as exc:  # noqa: BLE001
                    _on_error(exc)
                else:
                    _on_ok(result)
                finally:
                    watcher.deleteLater()
                    if watcher in self._watchers:
                        self._watchers.remove(watcher)

            watcher.finished.connect(_finished)
            future = _qt_run(func)
            watcher.setFuture(future)
            return

        future = _EXECUTOR.submit(func)  # type: ignore[name-defined]

        def _done(f):  # type: ignore[no-redef]
            # Runs in the worker thread (concurrent.futures invokes done-
            # callbacks on whichever thread completes the future) — marshal
            # onto the main thread via the _marshal signal rather than
            # QTimer.singleShot, which has no worker-thread event loop to
            # fire on.
            try:
                result = f.result()
            except Exception as exc:  # noqa: BLE001
                self._marshal.emit(lambda exc=exc: _on_error(exc))
            else:
                self._marshal.emit(lambda: _on_ok(result))

        future.add_done_callback(_done)

    def _fetch_metar(self, location: WeatherLocation, tick: Callable[[], None]) -> None:
        codes = location.icao_codes

        def _on_metar(readings):
            metar = next((r for r in readings if r.station in codes), None) if readings else None
            snap = self._snapshots.setdefault(location.location_id, WeatherSnapshot(location_id=location.location_id))
            snap.metar = metar
            self.snapshotUpdated.emit(location.location_id, snap)
            normalized = _normalize_metar_reading(metar)
            history_recorder.record(self._incident_id, location.location_id, normalized)

        self._run_async(
            lambda: self._metar_provider.fetch_metar(codes),
            _on_metar,
            location_id=location.location_id,
            provider_name="metar",
            tick=tick,
        )

    def _fetch_taf(self, location: WeatherLocation, tick: Callable[[], None]) -> None:
        codes = location.icao_codes

        def _on_taf(readings):
            taf = next((r for r in readings if r.station in codes), None) if readings else None
            snap = self._snapshots.setdefault(location.location_id, WeatherSnapshot(location_id=location.location_id))
            snap.taf = taf
            self.snapshotUpdated.emit(location.location_id, snap)

        self._run_async(
            lambda: self._taf_provider.fetch_taf(codes),
            _on_taf,
            location_id=location.location_id,
            provider_name="taf",
            tick=tick,
        )

    def _fetch_forecast(self, location: WeatherLocation, tick: Callable[[], None]) -> None:
        def _on_forecast(periods):
            snap = self._snapshots.setdefault(location.location_id, WeatherSnapshot(location_id=location.location_id))
            snap.forecast = periods or []
            self.snapshotUpdated.emit(location.location_id, snap)

        self._run_async(
            lambda: self._forecast_provider.fetch_forecast(location.latitude, location.longitude),
            _on_forecast,
            location_id=location.location_id,
            provider_name="forecast",
            tick=tick,
        )

    def _fetch_advisories(self, location: WeatherLocation, tick: Callable[[], None]) -> None:
        def _on_advisories(advisories: List[Advisory]):
            advisories = advisories or []
            snap = self._snapshots.setdefault(location.location_id, WeatherSnapshot(location_id=location.location_id))
            snap.advisories = advisories
            self.snapshotUpdated.emit(location.location_id, snap)
            self.alertsUpdated.emit(location.location_id, advisories)
            self._emit_new_alerts(location, advisories)

        self._run_async(
            lambda: self._advisory_provider.fetch_advisories(location.latitude, location.longitude),
            _on_advisories,
            location_id=location.location_id,
            provider_name="advisories",
            tick=tick,
        )

    def _fetch_hwo(self, location: WeatherLocation, tick: Callable[[], None]) -> None:
        def _on_hwo(payload):
            text = ""
            if isinstance(payload, dict):
                text = str(payload.get("text") or payload.get("raw_text") or "")
            snap = self._snapshots.setdefault(location.location_id, WeatherSnapshot(location_id=location.location_id))
            snap.hwo_text = text or None
            self.snapshotUpdated.emit(location.location_id, snap)
            self.hwoUpdated.emit(location.location_id, text)

        self._run_async(
            lambda: self._hwo_provider.fetch_hwo(location.latitude, location.longitude),
            _on_hwo,
            location_id=location.location_id,
            provider_name="hwo",
            tick=tick,
        )

    def _emit_new_alerts(self, location: WeatherLocation, advisories: List[Advisory]) -> None:
        seen = self._seen_advisory_keys.setdefault(location.location_id, set())
        for advisory in advisories:
            key = f"{advisory.event}|{advisory.headline}|{advisory.start}"
            if key in seen:
                continue
            seen.add(key)
            try:
                client.emit_weather_alert(
                    self._incident_id,
                    title=advisory.event or "Weather advisory",
                    message=advisory.headline or advisory.description or "",
                    source_id=key,
                    severity=(advisory.severity or "routine").lower(),
                )
            except Exception:
                LOGGER.exception("Failed to emit weather alert notification for %s", key)


_managers: Dict[str, WeatherManager] = {}


def get_weather_manager(incident_id: str) -> WeatherManager:
    """Return the cached WeatherManager for this incident, creating it if needed.

    Cached per incident id (not a raw class singleton) to avoid stale data
    bleeding across incident switches.
    """
    manager = _managers.get(incident_id)
    if manager is None:
        manager = WeatherManager(incident_id)
        _managers[incident_id] = manager
    return manager


__all__ = ["WeatherManager", "get_weather_manager"]
