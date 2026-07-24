# Weather Module Backlog

## Lightning data (deferred)

No free/public lightning-strike API meets a reliability bar suitable for
operational incident use as of 2026-07. NOAA/NWS publishes no lightning
strike endpoint. Blitzortung.org offers a community-run feed, but its access
model is informal/reciprocal (expects contributing a receiving station) and
is not a stable, sanctioned public API with an SLA — not appropriate for a
tool used to make real incident-safety decisions.

The old module's lightning support was backed by
`data_providers/lightning_stub.py`, which generated **random, fabricated**
strike data. That stub and its model (`models/lightning.py`) were deleted
outright during the module rebuild — no fake data, and no stub reintroduced.

Recommend a paid provider (e.g. Vaisala Xweather, Earth Networks) if/when
lightning is prioritized. Integrate a real provider or leave the capability
absent; do not re-add a stub.

## Runway crosswind data source (resolved 2026-07-22)

Originally planned as a bundled static CSV (OurAirports.com export). Changed
to a **live lookup** instead: `services/runway_api.py` queries NOAA's
Aviation Weather Center `/api/data/airport` endpoint — the same
`aviationweather.gov` host already used for METAR/TAF — so this adds no new
provider, no API key, and no new secret to manage. The lookup runs once, at
station-creation time (`WeatherManager.add_manual_location` /
`sync_auto_locations`), and the result is cached on the `WeatherLocation`
(`runway_ends` field, persisted in `weather_config.locations[]`) — never
re-queried per crosswind computation. If the lookup fails (unknown ICAO
code, network error, unexpected response shape), `runway_ends` stays empty
and the Aviation tab simply omits the crosswind readout rather than
guessing (see `services/crosswind.py`).

AWC's `runways` entries give one `alignment` (true heading) per physical
runway; the reciprocal end is derived as `alignment + 180`, not a second
value the API returns — verify this still matches AWC's live response shape
if their API changes.

## NWS location-code hint caching (minor gap)

The old manager pre-resolved and cached NWS office/grid codes per location
via `services/location_codes.py` (`NwsLocationCodeService`) to speed up
forecast/HWO lookups. The rebuilt `services/weather_manager.py` doesn't wire
this in yet — `NoaaForecastProvider`/`NoaaHwoProvider` still work correctly
without it (they resolve the point lookup directly per request), just
without the caching speedup. Low priority; wire `location_codes.py` back in
if forecast/HWO latency becomes a concern.
