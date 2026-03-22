"""Central weather API manager used by all UI components."""

from __future__ import annotations

import functools
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

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
from ..data_providers.noaa_nws_advisories import NoaaNwsAdvisoryProvider
from ..data_providers.lightning_stub import LightningStub
from ..models.advisory import Advisory
from ..models.lightning import LightningStrike
from ..models.readings import MetarReading, TafReading
from . import cache, settings

LOGGER = logging.getLogger(__name__)


class WeatherApiManager(QObject):
    """Coordinates background weather data fetches and caching."""

    statusChanged = Signal(str)
    dataUpdated = Signal(dict)
    fetchFailed = Signal(str, object)
    alertsUpdated = Signal(list)
    lightningUpdated = Signal(list)

    _instance: "WeatherApiManager" | None = None

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("weatherApiManager")
        self._metar_provider = NoaaMetarProvider()
        self._taf_provider = NoaaTafProvider()
        self._advisory_provider = NoaaNwsAdvisoryProvider()
        self._lightning_provider = LightningStub()
        self._watchers: List[QFutureWatcher] = [] if _HAS_QTCONCURRENT else []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_all)
        self._metar_cache: Dict[str, MetarReading] = {}
        self._taf_cache: Dict[str, TafReading] = {}
        self._advisory_cache: List[Advisory] = []
        self._lightning_cache: List[LightningStrike] = []
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
        interval_ms = max(minutes, 1) * 60_000
        self._timer.start(interval_ms)
        LOGGER.debug("Polling interval set to %s minutes", minutes)

    def request_metar(self, icao_codes: Iterable[str]) -> None:
        codes = list({code.strip().upper() for code in icao_codes if code})
        if not codes:
            return
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

    def refresh_all(self) -> None:
        self.statusChanged.emit("Refreshing weather data…")
        LOGGER.info("WeatherApiManager refresh_all invoked")
        if self._metar_cache:
            self.request_metar(self._metar_cache.keys())
        if self._taf_cache:
            self.request_taf(self._taf_cache.keys())
        if self._advisory_cache:
            self.alertsUpdated.emit([asdict(item) for item in self._advisory_cache])
        if self._lightning_cache:
            self.lightningUpdated.emit([asdict(item) for item in self._lightning_cache])
        self.statusChanged.emit("Weather data refreshed")
        self._publish_data()

    def _on_metar_result(self, readings: List[MetarReading]) -> None:
        for reading in readings:
            self._metar_cache[reading.station] = reading
        cache.write_cache(
            "metar", {key: asdict(value) for key, value in self._metar_cache.items()}
        )
        self._publish_data()

    def _on_taf_result(self, tafs: List[TafReading]) -> None:
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

    def _on_lightning_result(self, strikes: List[LightningStrike]) -> None:
        self._lightning_cache = strikes
        cache.write_cache(
            "lightning", {str(i): asdict(a) for i, a in enumerate(strikes)}
        )
        self.lightningUpdated.emit([asdict(item) for item in strikes])

    def _publish_data(self) -> None:
        payload: Dict[str, Any] = {
            "metar": {key: asdict(value) for key, value in self._metar_cache.items()},
            "taf": {key: asdict(value) for key, value in self._taf_cache.items()},
            "advisories": [asdict(item) for item in self._advisory_cache],
            "lightning": [asdict(item) for item in self._lightning_cache],
            "hwo": self._hwo_payload,
        }
        self.dataUpdated.emit(payload)

    def _load_cached_payloads(self) -> None:
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
                start=item.get("start"),
                end=item.get("end"),
                headline=item.get("headline"),
                description=item.get("description"),
                certainty=item.get("certainty"),
                urgency=item.get("urgency"),
                affected_areas=item.get("affected_areas"),
            )
            for item in cached_adv.values()
        ]
        cached_lightning = cache.read_cache("lightning") or {}
        self._lightning_cache = []
        for _ in cached_lightning.values():
            # Placeholder; actual reconstruction requires timestamp parsing.
            continue
        if self._metar_cache or self._taf_cache or self._advisory_cache:
            self._publish_data()

    def _run_async(
        self,
        func: callable,
        callback: callable,
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


__all__ = ["WeatherApiManager"]
