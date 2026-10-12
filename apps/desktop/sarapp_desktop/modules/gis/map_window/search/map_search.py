"""MapSearch: debounced local feature search + on-demand geocoder search.

Local search matches against feature labels already loaded from
spatial_repository (fast, no network). Geocoder search only runs when the
user presses Enter or clicks Search (utils.geocoding.geocode_address hits
the API server, so it is deliberately not fired on every keystroke).
Results are grouped by source so the bottom panel's Search Results tab can
render "Local Features" / "Geocoder" sections.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from modules.gis.models.spatial_feature import SpatialFeature
from utils.geocoding import GeocodeResult, geocode_address

_DEBOUNCE_MS = 300


class MapSearchController(QObject):
    localResultsReady = Signal(list)  # list[SpatialFeature]
    geocodeResultReady = Signal(object)  # GeocodeResult | None

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._features: list[SpatialFeature] = []
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._run_local_search)
        self._pending_query = ""

    def set_feature_index(self, features: list[SpatialFeature]) -> None:
        self._features = list(features)

    def query_local_debounced(self, text: str) -> None:
        self._pending_query = text.strip()
        if not self._pending_query:
            self.localResultsReady.emit([])
            self._debounce_timer.stop()
            return
        self._debounce_timer.start()

    def _run_local_search(self) -> None:
        results = self.search_local(self._pending_query)
        self.localResultsReady.emit(results)

    def search_local(self, text: str) -> list[SpatialFeature]:
        needle = text.strip().lower()
        if not needle:
            return []
        return [f for f in self._features if needle in (f.label or "").lower()]

    def search_geocoder(self, text: str) -> GeocodeResult | None:
        text = text.strip()
        if not text:
            self.geocodeResultReady.emit(None)
            return None
        result = geocode_address(text)
        self.geocodeResultReady.emit(result)
        return result
