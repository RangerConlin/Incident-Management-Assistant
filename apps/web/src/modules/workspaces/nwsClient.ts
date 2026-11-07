// Thin client for the public National Weather Service API (api.weather.gov)
// — called directly from the browser, not proxied through our backend.
// Confirmed working cross-origin (tested from an unrelated origin): points
// lookup, gridpoint forecast, station observations (includes rawMessage,
// the raw METAR text), active alerts, and HWO text products all return
// real data with no CORS block. aviationweather.gov's METAR/TAF API was
// also tested and does NOT allow cross-origin browser fetches (confirmed
// "Failed to fetch" from a neutral origin) — that's why Aviation below
// uses api.weather.gov's own station observations (which include the raw
// METAR) instead, and has no TAF at all: no CORS-accessible public source
// for it was found.

const NWS_HEADERS = { Accept: "application/geo+json" };

export interface NwsGridPoint {
  gridId: string;
  gridX: number;
  gridY: number;
  forecastUrl: string;
  observationStationsUrl: string;
  officeId: string; // 4-letter, e.g. "KSLC" — used for HWO product lookups
}

export async function nwsGetGridPoint(lat: number, lon: number): Promise<NwsGridPoint> {
  const res = await fetch(`https://api.weather.gov/points/${lat.toFixed(4)},${lon.toFixed(4)}`, { headers: NWS_HEADERS });
  if (!res.ok) throw new Error(`NWS points lookup failed (${res.status})`);
  const data = await res.json();
  const p = data.properties ?? {};
  return {
    gridId: p.gridId,
    gridX: p.gridX,
    gridY: p.gridY,
    forecastUrl: p.forecast,
    observationStationsUrl: p.observationStations,
    officeId: `K${p.gridId}`,
  };
}

export interface NwsForecastPeriod {
  name: string;
  shortForecast: string;
  temperature: number;
  temperatureUnit: string;
  windSpeed: string;
  windDirection: string;
  probabilityOfPrecipitation: number | null;
}

export async function nwsGetForecastPeriods(forecastUrl: string): Promise<NwsForecastPeriod[]> {
  const res = await fetch(forecastUrl, { headers: NWS_HEADERS });
  if (!res.ok) throw new Error(`NWS forecast fetch failed (${res.status})`);
  const data = await res.json();
  const periods = (data.properties?.periods ?? []) as Array<Record<string, unknown>>;
  return periods.map((p) => ({
    name: String(p.name ?? ""),
    shortForecast: String(p.shortForecast ?? ""),
    temperature: Number(p.temperature ?? 0),
    temperatureUnit: String(p.temperatureUnit ?? "F"),
    windSpeed: String(p.windSpeed ?? ""),
    windDirection: String(p.windDirection ?? ""),
    probabilityOfPrecipitation: (p.probabilityOfPrecipitation as { value: number | null } | undefined)?.value ?? null,
  }));
}

function unitValue(field: unknown): number | null {
  const v = (field as { value?: number | null } | undefined)?.value;
  return typeof v === "number" ? v : null;
}
const cToF = (c: number | null) => (c === null ? null : (c * 9) / 5 + 32);
const kmhToMph = (v: number | null) => (v === null ? null : v * 0.621371);
const mToMiles = (v: number | null) => (v === null ? null : v / 1609.344);
const mToFeet = (v: number | null) => (v === null ? null : v * 3.28084);
const paToInHg = (v: number | null) => (v === null ? null : v * 0.0002953);

export interface NwsObservation {
  stationId: string;
  stationName: string;
  timestamp: string;
  rawMessage: string;
  textDescription: string;
  temperatureF: number | null;
  heatIndexF: number | null;
  windChillF: number | null;
  windSpeedMph: number | null;
  windGustMph: number | null;
  windDirection: number | null;
  visibilityMi: number | null;
  ceilingFt: number | null;
  relativeHumidityPct: number | null;
  barometricPressureInHg: number | null;
}

function parseObservation(stationId: string, data: Record<string, unknown>): NwsObservation {
  const props = (data.properties ?? data) as Record<string, unknown>;
  const cloudLayers = (props.cloudLayers as Array<{ base?: { value?: number | null } }> | undefined) ?? [];
  const lowestCeiling = cloudLayers.map((l) => unitValue(l.base)).filter((v): v is number => v !== null)[0] ?? null;
  return {
    stationId,
    stationName: String(props.stationName ?? stationId),
    timestamp: String(props.timestamp ?? ""),
    rawMessage: String(props.rawMessage ?? ""),
    textDescription: String(props.textDescription ?? ""),
    temperatureF: cToF(unitValue(props.temperature)),
    heatIndexF: cToF(unitValue(props.heatIndex)),
    windChillF: cToF(unitValue(props.windChill)),
    windSpeedMph: kmhToMph(unitValue(props.windSpeed)),
    windGustMph: kmhToMph(unitValue(props.windGust)),
    windDirection: unitValue(props.windDirection),
    visibilityMi: mToMiles(unitValue(props.visibility)),
    ceilingFt: mToFeet(lowestCeiling),
    relativeHumidityPct: unitValue(props.relativeHumidity),
    barometricPressureInHg: paToInHg(unitValue(props.barometricPressure)),
  };
}

export async function nwsGetNearestStationObservation(observationStationsUrl: string): Promise<NwsObservation | null> {
  const stationsRes = await fetch(observationStationsUrl, { headers: NWS_HEADERS });
  if (!stationsRes.ok) throw new Error(`NWS stations lookup failed (${stationsRes.status})`);
  const stationsData = await stationsRes.json();
  const first = (stationsData.features ?? [])[0];
  if (!first) return null;
  const stationId = String(first.properties?.stationIdentifier ?? "");
  return nwsGetStationObservation(stationId);
}

export async function nwsGetStationObservation(icaoCode: string): Promise<NwsObservation | null> {
  const res = await fetch(`https://api.weather.gov/stations/${encodeURIComponent(icaoCode)}/observations/latest`, { headers: NWS_HEADERS });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`NWS observation fetch failed for ${icaoCode} (${res.status})`);
  const data = await res.json();
  return parseObservation(icaoCode, data);
}

export interface NwsAlert {
  id: string;
  event: string;
  headline: string;
  severity: string;
  effective: string;
  expires: string;
}

export async function nwsGetActiveAlerts(lat: number, lon: number): Promise<NwsAlert[]> {
  const res = await fetch(`https://api.weather.gov/alerts/active?point=${lat.toFixed(4)},${lon.toFixed(4)}`, { headers: NWS_HEADERS });
  if (!res.ok) throw new Error(`NWS alerts fetch failed (${res.status})`);
  const data = await res.json();
  const features = (data.features ?? []) as Array<{ id: string; properties: Record<string, unknown> }>;
  return features.map((f) => ({
    id: f.id,
    event: String(f.properties.event ?? ""),
    headline: String(f.properties.headline ?? ""),
    severity: String(f.properties.severity ?? ""),
    effective: String(f.properties.effective ?? ""),
    expires: String(f.properties.expires ?? ""),
  }));
}

export async function nwsGetLatestHwo(officeId: string): Promise<string | null> {
  const listRes = await fetch(`https://api.weather.gov/products?type=HWO&location=${encodeURIComponent(officeId)}&limit=1`, {
    headers: { Accept: "application/ld+json" },
  });
  if (!listRes.ok) throw new Error(`NWS HWO list fetch failed (${listRes.status})`);
  const listData = await listRes.json();
  const first = (listData["@graph"] ?? [])[0];
  if (!first) return null;
  const productRes = await fetch(`https://api.weather.gov/products/${first.id}`, { headers: { Accept: "application/ld+json" } });
  if (!productRes.ok) throw new Error(`NWS HWO product fetch failed (${productRes.status})`);
  const productData = await productRes.json();
  return String(productData.productText ?? "") || null;
}
