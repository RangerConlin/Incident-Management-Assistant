import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { addWeatherLocation, getWeatherConfig, removeWeatherLocation, setWeatherDefault, updateWeatherConfig, weatherHistory } from "../../api/endpoints";
import { useSession } from "../../auth/SessionContext";
import DataTable from "../../components/table/DataTable";
import type { RecordData } from "./config";
import type { WeatherLocation, WeatherThresholds } from "../../api/types";
import { formatDateTime } from "../../utils/formatDateTime";
import {
  nwsGetActiveAlerts,
  nwsGetForecastPeriods,
  nwsGetGridPoint,
  nwsGetLatestHwo,
  nwsGetNearestStationObservation,
  nwsGetStationObservation,
  type NwsObservation,
} from "./nwsClient";
import "./workspaces.css";

type Tab = "current" | "aviation" | "alerts" | "stations" | "thresholds" | "history";

type ThresholdLevel = "go" | "marginal" | "nogo";
function thresholdLevel(value: number | null, marginal: number, nogo: number, higherIsWorse: boolean): ThresholdLevel | null {
  if (value === null) return null;
  if (higherIsWorse) return value >= nogo ? "nogo" : value >= marginal ? "marginal" : "go";
  return value <= nogo ? "nogo" : value <= marginal ? "marginal" : "go";
}
const LEVEL_COLOR: Record<ThresholdLevel, string> = { go: "var(--status-severity-good-bg)", marginal: "var(--status-severity-warning-bg)", nogo: "var(--status-severity-critical-bg)" };
const LEVEL_FG: Record<ThresholdLevel, string> = { go: "var(--status-severity-good-fg)", marginal: "var(--status-severity-warning-fg)", nogo: "var(--status-severity-critical-fg)" };

function ThresholdTile({ label, value, unit, level }: { label: string; value: number | string | null; unit: string; level: ThresholdLevel | null }) {
  const style = level ? { background: LEVEL_COLOR[level], color: LEVEL_FG[level] } : undefined;
  return (
    <div className="planning-panel" style={style}>
      <h3 style={{ margin: 0 }}>{value === null ? "—" : `${value}${unit}`}</h3>
      <p style={{ margin: 0 }}>{label}{level ? ` — ${level === "nogo" ? "No-Go" : level === "marginal" ? "Marginal" : "Go"}` : ""}</p>
    </div>
  );
}

function useLocationGridPoint(loc: WeatherLocation | undefined) {
  return useQuery({
    queryKey: ["nws", "gridpoint", loc?.latitude, loc?.longitude],
    queryFn: () => nwsGetGridPoint(loc!.latitude!, loc!.longitude!),
    enabled: Boolean(loc?.latitude != null && loc?.longitude != null),
    staleTime: 60 * 60_000,
  });
}

function CurrentForecastTab({ loc, thresholds }: { loc: WeatherLocation | undefined; thresholds: WeatherThresholds | undefined }) {
  const gridPoint = useLocationGridPoint(loc);
  const forecast = useQuery({
    queryKey: ["nws", "forecast", gridPoint.data?.forecastUrl],
    queryFn: () => nwsGetForecastPeriods(gridPoint.data!.forecastUrl),
    enabled: Boolean(gridPoint.data?.forecastUrl),
    staleTime: 30 * 60_000,
  });
  const observation = useQuery({
    queryKey: ["nws", "observation", gridPoint.data?.observationStationsUrl],
    queryFn: () => nwsGetNearestStationObservation(gridPoint.data!.observationStationsUrl),
    enabled: Boolean(gridPoint.data?.observationStationsUrl),
    staleTime: 10 * 60_000,
  });

  if (!loc) return <p className="muted">Add a monitoring location with coordinates on the Stations tab to see live conditions and forecast.</p>;
  if (!loc.latitude || !loc.longitude) return <p className="muted">This location has no latitude/longitude on file — live NWS data needs coordinates.</p>;
  if (gridPoint.isPending) return <p>Loading…</p>;
  if (gridPoint.isError) return <p className="error">{(gridPoint.error as Error).message}</p>;

  const obs = observation.data ?? null;
  const g = thresholds?.ground;

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 16 }}>
        <ThresholdTile label="Wind Gust" value={obs?.windGustMph != null ? Math.round(obs.windGustMph) : null} unit=" mph" level={g ? thresholdLevel(obs?.windGustMph ?? null, g.wind_gust_marginal_mph, g.wind_gust_nogo_mph, true) : null} />
        <ThresholdTile label="Visibility" value={obs?.visibilityMi != null ? obs.visibilityMi.toFixed(1) : null} unit=" mi" level={g ? thresholdLevel(obs?.visibilityMi ?? null, g.visibility_marginal_mi, g.visibility_nogo_mi, false) : null} />
        <ThresholdTile label="Cloud Ceiling" value={obs?.ceilingFt != null ? Math.round(obs.ceilingFt) : null} unit=" ft" level={g ? thresholdLevel(obs?.ceilingFt ?? null, g.ceiling_marginal_ft, g.ceiling_nogo_ft, false) : null} />
        <ThresholdTile label="Heat Index" value={obs?.heatIndexF != null ? Math.round(obs.heatIndexF) : obs?.temperatureF != null ? Math.round(obs.temperatureF) : null} unit="°F" level={g ? thresholdLevel(obs?.heatIndexF ?? obs?.temperatureF ?? null, g.heat_index_marginal_f, g.heat_index_nogo_f, true) : null} />
      </div>

      <h3>Current Conditions{obs ? ` — ${obs.stationName} (${obs.stationId})` : ""}</h3>
      {observation.isPending ? (
        <p>Loading…</p>
      ) : !obs ? (
        <p className="muted">No nearby observation station reported recent data.</p>
      ) : (
        <div className="detail-header">
          <div className="field"><label>Temperature</label><input readOnly value={obs.temperatureF != null ? `${Math.round(obs.temperatureF)}°F` : "—"} /></div>
          <div className="field"><label>Feels Like</label><input readOnly value={obs.heatIndexF != null ? `${Math.round(obs.heatIndexF)}°F` : obs.windChillF != null ? `${Math.round(obs.windChillF)}°F` : "—"} /></div>
          <div className="field"><label>Wind</label><input readOnly value={obs.windSpeedMph != null ? `${Math.round(obs.windSpeedMph)} mph${obs.windGustMph ? `, gusting ${Math.round(obs.windGustMph)} mph` : ""}` : "—"} /></div>
          <div className="field"><label>Visibility</label><input readOnly value={obs.visibilityMi != null ? `${obs.visibilityMi.toFixed(1)} mi` : "—"} /></div>
          <div className="field"><label>Sky Condition</label><input readOnly value={obs.textDescription || "—"} /></div>
          <div className="field"><label>Humidity</label><input readOnly value={obs.relativeHumidityPct != null ? `${Math.round(obs.relativeHumidityPct)}%` : "—"} /></div>
          <div className="field"><label>Barometric Pressure</label><input readOnly value={obs.barometricPressureInHg != null ? `${obs.barometricPressureInHg.toFixed(2)} in` : "—"} /></div>
          <div className="field"><label>Observed</label><input readOnly value={obs.timestamp ? formatDateTime(obs.timestamp) : "—"} /></div>
        </div>
      )}

      <h3>Forecast</h3>
      {forecast.isPending ? (
        <p>Loading…</p>
      ) : forecast.isError ? (
        <p className="error">{(forecast.error as Error).message}</p>
      ) : (
        <DataTable
          tableId="weather-forecast"
          rows={forecast.data ?? []}
          rowKey={(r) => r.name}
          columns={[
            { key: "name", header: "Period" },
            { key: "shortForecast", header: "Conditions" },
            { key: "temperature", header: "Temp", render: (r) => `${r.temperature}°${r.temperatureUnit}` },
            { key: "probabilityOfPrecipitation", header: "Chance of Rain", render: (r) => (r.probabilityOfPrecipitation != null ? `${r.probabilityOfPrecipitation}%` : "—") },
            { key: "wind", header: "Wind", render: (r) => `${r.windSpeed} ${r.windDirection}` },
          ]}
        />
      )}
    </div>
  );
}

function AviationTab({ loc }: { loc: WeatherLocation | undefined }) {
  const codes = useMemo(() => loc?.icao_codes ?? [], [loc?.icao_codes]);
  const stations = useQuery({
    queryKey: ["nws", "station-obs-batch", codes.join(",")],
    queryFn: async () => {
      const results = await Promise.all(codes.map((code) => nwsGetStationObservation(code).catch(() => null)));
      return codes.map((code, i) => ({ code, observation: results[i] as NwsObservation | null }));
    },
    enabled: codes.length > 0,
    staleTime: 10 * 60_000,
  });

  if (!loc) return <p className="muted">Add a monitoring location on the Stations tab to see aviation weather.</p>;
  if (codes.length === 0) return <p className="muted">This location has no ICAO stations on file — add one on the Stations tab.</p>;

  return (
    <div>
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        METAR comes from NWS's own station network (api.weather.gov) — there's no TAF here, since the only public TAF source
        (aviationweather.gov) doesn't allow direct browser requests from other sites.
      </p>
      {stations.isPending ? (
        <p>Loading…</p>
      ) : stations.isError ? (
        <p className="error">{(stations.error as Error).message}</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {stations.data!.map(({ code, observation }) => (
            <div key={code} className="planning-panel">
              <h3 style={{ marginTop: 0 }}>{code}</h3>
              {!observation ? (
                <p className="muted">No recent observation for this station.</p>
              ) : (
                <>
                  <p>
                    Wind {observation.windDirection != null ? `${Math.round(observation.windDirection)}°` : "—"} at {observation.windSpeedMph != null ? `${Math.round(observation.windSpeedMph)} mph` : "—"}
                    {observation.windGustMph ? `, gusting ${Math.round(observation.windGustMph)} mph` : ""} · Visibility {observation.visibilityMi != null ? `${observation.visibilityMi.toFixed(1)} mi` : "—"} · {observation.textDescription || "—"}
                  </p>
                  <p className="muted" style={{ fontFamily: "monospace", fontSize: "0.82rem" }}>{observation.rawMessage}</p>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AlertsHwoTab({ loc }: { loc: WeatherLocation | undefined }) {
  const gridPoint = useLocationGridPoint(loc);
  const alerts = useQuery({
    queryKey: ["nws", "alerts", loc?.latitude, loc?.longitude],
    queryFn: () => nwsGetActiveAlerts(loc!.latitude!, loc!.longitude!),
    enabled: Boolean(loc?.latitude != null && loc?.longitude != null),
    staleTime: 5 * 60_000,
  });
  const hwo = useQuery({
    queryKey: ["nws", "hwo", gridPoint.data?.officeId],
    queryFn: () => nwsGetLatestHwo(gridPoint.data!.officeId),
    enabled: Boolean(gridPoint.data?.officeId),
    staleTime: 30 * 60_000,
  });

  if (!loc) return <p className="muted">Add a monitoring location with coordinates to see alerts and the Hazardous Weather Outlook.</p>;
  if (!loc.latitude || !loc.longitude) return <p className="muted">This location has no latitude/longitude on file.</p>;

  return (
    <div style={{ display: "flex", gap: 20, flexWrap: "wrap", alignItems: "flex-start" }}>
      <div style={{ flex: "1 1 320px" }}>
        <h3>Active Advisories</h3>
        {alerts.isPending ? (
          <p>Loading…</p>
        ) : alerts.isError ? (
          <p className="error">{(alerts.error as Error).message}</p>
        ) : (alerts.data ?? []).length === 0 ? (
          <p className="muted">No active NWS alerts for this location.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {alerts.data!.map((a) => (
              <div key={a.id} className="entry-card">
                <strong>{a.event}</strong> <span className="muted">({a.severity})</span>
                <p style={{ margin: "4px 0 0" }}>{a.headline}</p>
              </div>
            ))}
          </div>
        )}
      </div>
      <div style={{ flex: "2 1 420px" }}>
        <h3>Hazardous Weather Outlook</h3>
        {gridPoint.isPending || hwo.isPending ? (
          <p>Loading…</p>
        ) : hwo.isError ? (
          <p className="error">{(hwo.error as Error).message}</p>
        ) : !hwo.data ? (
          <p className="muted">No Hazardous Weather Outlook currently issued for this office.</p>
        ) : (
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: "0.82rem" }}>{hwo.data}</pre>
        )}
      </div>
    </div>
  );
}

// Desktop's WeatherDetailPanel has 5 tabs (Current & Forecast/Aviation/
// Alerts & HWO/History/Stations); the first three pull live forecast/METAR/
// TAF/HWO directly from NWS client-side (confirmed in routers/weather.py's
// own docstring: this backend only stores locations/thresholds/history, it
// never proxies live weather). Confirmed by hand (fetching from a neutral
// origin, not weather.gov itself) that api.weather.gov allows direct
// browser calls for points/forecast/station-observations/alerts/HWO text
// products, so those are wired for real below. aviationweather.gov's own
// METAR/TAF API does NOT allow cross-origin browser calls (confirmed
// "Failed to fetch" the same way) — Aviation uses api.weather.gov's station
// observations instead (includes the raw METAR text) and has no TAF.
export default function WeatherPage() {
  const { incidentId } = useSession();
  const [tab, setTab] = useState<Tab>("current");
  const [params, setParams] = useSearchParams();
  const historyLocation = params.get("location") ?? "";
  const [label, setLabel] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [codes, setCodes] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [activeLocationId, setActiveLocationId] = useState("");
  const client = useQueryClient();
  const key = ["incident", incidentId, "weather_config"];
  const query = useQuery({ queryKey: key, queryFn: () => getWeatherConfig(incidentId!), refetchInterval: 20_000 });
  const history = useQuery({ queryKey: ["incident", incidentId, "weather_history", historyLocation], queryFn: () => weatherHistory(incidentId!, historyLocation), enabled: !!historyLocation, refetchInterval: 20_000 });
  const mutation = useMutation({
    mutationFn: ({ action, id }: { action: "add" | "remove" | "default"; id?: string }) =>
      action === "remove"
        ? removeWeatherLocation(incidentId!, id!)
        : action === "default"
          ? setWeatherDefault(incidentId!, id!)
          : addWeatherLocation(incidentId!, { label: label.trim(), latitude: lat ? Number(lat) : null, longitude: lon ? Number(lon) : null, icao_codes: codes.split(/[\s,]+/).filter(Boolean).map(c => c.toUpperCase()) }),
    onSuccess: async (_, variables) => {
      if (variables.action === "add") { setLabel(""); setLat(""); setLon(""); setCodes(""); }
      if (variables.action === "remove" && variables.id === historyLocation) setParams({});
      setRemoving(null);
      await client.invalidateQueries({ queryKey: key });
    },
  });
  const thresholdsMutation = useMutation({
    mutationFn: (thresholds: WeatherThresholds) => updateWeatherConfig(incidentId!, { thresholds }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: key }); },
  });

  const [thresholdsForm, setThresholdsForm] = useState<WeatherThresholds | null>(null);
  useEffect(() => {
    if (query.data?.thresholds) setThresholdsForm(query.data.thresholds);
  }, [query.data?.thresholds]);

  const locations = useMemo(() => query.data?.locations ?? [], [query.data?.locations]);
  useEffect(() => {
    if (activeLocationId || locations.length === 0) return;
    setActiveLocationId(locations.find((l) => l.is_default)?.location_id ?? locations[0].location_id);
  }, [locations, activeLocationId]);
  const activeLocation = locations.find((l) => l.location_id === activeLocationId);

  const locationsForTable = locations as unknown as RecordData[];
  const error = query.error ?? history.error ?? mutation.error ?? thresholdsMutation.error;

  const locationPicker = locations.length > 0 && (
    <label className="field" style={{ maxWidth: 320, marginBottom: 16 }}>
      Location
      <select value={activeLocationId} onChange={(e) => setActiveLocationId(e.target.value)}>
        {locations.map((l) => (
          <option key={l.location_id} value={l.location_id}>{l.label}{l.is_default ? " (default)" : ""}</option>
        ))}
      </select>
    </label>
  );

  return (
    <section className="workspace-page">
      <h1>Weather</h1>
      <p>Live conditions, forecast, and alerts for the incident's monitoring locations, plus Go/No-Go thresholds and recorded history.</p>
      {error && <p role="alert" className="error">{error.message}</p>}

      <div className="detail-tabs" style={{ marginBottom: 16 }}>
        <button className={`detail-tab ${tab === "current" ? "active" : ""}`} onClick={() => setTab("current")}>Current &amp; Forecast</button>
        <button className={`detail-tab ${tab === "aviation" ? "active" : ""}`} onClick={() => setTab("aviation")}>Aviation</button>
        <button className={`detail-tab ${tab === "alerts" ? "active" : ""}`} onClick={() => setTab("alerts")}>Alerts &amp; HWO</button>
        <button className={`detail-tab ${tab === "history" ? "active" : ""}`} onClick={() => setTab("history")}>History</button>
        <button className={`detail-tab ${tab === "stations" ? "active" : ""}`} onClick={() => setTab("stations")}>Stations</button>
        <button className={`detail-tab ${tab === "thresholds" ? "active" : ""}`} onClick={() => setTab("thresholds")}>Thresholds</button>
      </div>

      {(tab === "current" || tab === "aviation" || tab === "alerts") && locationPicker}
      {tab === "current" && <CurrentForecastTab loc={activeLocation} thresholds={query.data?.thresholds} />}
      {tab === "aviation" && <AviationTab loc={activeLocation} />}
      {tab === "alerts" && <AlertsHwoTab loc={activeLocation} />}

      {tab === "stations" && (
        <>
          {query.isPending && <p>Loading locations…</p>}
          <DataTable tableId="weather-locations" rows={locationsForTable} rowKey={r => String(r.location_id)} columns={[
            { key: "label", header: "Location" }, { key: "latitude", header: "Latitude" }, { key: "longitude", header: "Longitude" }, { key: "icao_codes", header: "Stations", render: r => (r.icao_codes as string[]).join(", ") },
            { key: "source", header: "Source" }, { key: "is_default", header: "Default", render: r => r.is_default ? "Yes" : "No" },
            { key: "actions", header: "Actions", render: r => <div className="workspace-actions"><button disabled={mutation.isPending} onClick={() => { setParams({ location: String(r.location_id) }); setTab("history"); }}>History</button><button className="secondary" disabled={mutation.isPending || !!r.is_default} onClick={() => mutation.mutate({ action: "default", id: String(r.location_id) })}>Set default</button>{r.source === "manual" && <button className="danger" disabled={mutation.isPending} onClick={() => setRemoving(String(r.location_id))}>Remove</button>}</div> },
          ]} />
          {removing && <div className="workspace-actions"><p>Remove this monitoring location?</p><button className="danger" disabled={mutation.isPending} onClick={() => mutation.mutate({ action: "remove", id: removing })}>Confirm removal</button><button className="secondary" onClick={() => setRemoving(null)}>Cancel</button></div>}
          <h2>Add monitoring location</h2>
          <form className="workspace-form" onSubmit={e => { e.preventDefault(); mutation.mutate({ action: "add" }); }}>
            <label className="field">Location name<input required value={label} onChange={e => setLabel(e.target.value)} /></label>
            <label className="field">Latitude<input type="number" step="any" min={-90} max={90} value={lat} onChange={e => setLat(e.target.value)} /></label>
            <label className="field">Longitude<input type="number" step="any" min={-180} max={180} value={lon} onChange={e => setLon(e.target.value)} /></label>
            <label className="field">ICAO stations (comma separated)<input value={codes} onChange={e => setCodes(e.target.value)} /></label>
            <button disabled={mutation.isPending || !label.trim()}>Add location</button>
          </form>
        </>
      )}

      {tab === "thresholds" && (
        <>
          {query.isPending || !thresholdsForm ? (
            <p>Loading thresholds…</p>
          ) : (
            <>
              <p className="muted">Polling interval: {query.data?.polling_minutes ?? 10} min.</p>
              <h2>Ground Go/No-Go Thresholds</h2>
              <div className="detail-header">
                {([
                  ["wind_gust_marginal_mph", "Wind Gust — Marginal (mph)"],
                  ["wind_gust_nogo_mph", "Wind Gust — No-Go (mph)"],
                  ["visibility_marginal_mi", "Visibility — Marginal (mi)"],
                  ["visibility_nogo_mi", "Visibility — No-Go (mi)"],
                  ["ceiling_marginal_ft", "Cloud Ceiling — Marginal (ft)"],
                  ["ceiling_nogo_ft", "Cloud Ceiling — No-Go (ft)"],
                  ["heat_index_marginal_f", "Heat Index — Marginal (°F)"],
                  ["heat_index_nogo_f", "Heat Index — No-Go (°F)"],
                ] as const).map(([key, label]) => (
                  <div className="field" key={key}>
                    <label>{label}</label>
                    <input
                      type="number"
                      value={thresholdsForm.ground[key]}
                      onChange={(e) => setThresholdsForm({ ...thresholdsForm, ground: { ...thresholdsForm.ground, [key]: Number(e.target.value) } })}
                    />
                  </div>
                ))}
              </div>

              <h2>Aviation Go/No-Go Thresholds</h2>
              <div className="detail-header">
                {([
                  ["wind_gust_marginal_kt", "Wind Gust — Marginal (kt)"],
                  ["wind_gust_nogo_kt", "Wind Gust — No-Go (kt)"],
                  ["visibility_marginal_sm", "Visibility — Marginal (sm)"],
                  ["visibility_nogo_sm", "Visibility — No-Go (sm)"],
                  ["ceiling_marginal_ft_agl", "Cloud Ceiling — Marginal (ft AGL)"],
                  ["ceiling_nogo_ft_agl", "Cloud Ceiling — No-Go (ft AGL)"],
                  ["crosswind_marginal_kt", "Crosswind — Marginal (kt)"],
                  ["crosswind_nogo_kt", "Crosswind — No-Go (kt)"],
                ] as const).map(([key, label]) => (
                  <div className="field" key={key}>
                    <label>{label}</label>
                    <input
                      type="number"
                      value={thresholdsForm.aviation[key]}
                      onChange={(e) => setThresholdsForm({ ...thresholdsForm, aviation: { ...thresholdsForm.aviation, [key]: Number(e.target.value) } })}
                    />
                  </div>
                ))}
              </div>

              <button type="button" disabled={thresholdsMutation.isPending} onClick={() => thresholdsMutation.mutate(thresholdsForm)}>
                {thresholdsMutation.isPending ? "Saving…" : "Save Thresholds"}
              </button>
            </>
          )}
        </>
      )}

      {tab === "history" && (
        <>
          {!historyLocation ? (
            <p className="muted">Pick a location from the Stations tab's "History" button to see its recorded observations.</p>
          ) : (
            <>
              <h2>Observation history — {String(locations.find(r => r.location_id === historyLocation)?.label ?? historyLocation)}</h2>
              {history.isPending && <p>Loading observations…</p>}
              <DataTable tableId="weather-history" rows={history.data?.samples ?? []} rowKey={r => String(r._id)} columns={[
                { key: "recorded_at", header: "Recorded", render: r => formatDateTime(String(r.recorded_at)) }, { key: "temperature_f", header: "Temperature °F" }, { key: "wind_speed_kt", header: "Wind kt" }, { key: "wind_gust_kt", header: "Gust kt" }, { key: "visibility_sm", header: "Visibility mi" }, { key: "ceiling_ft", header: "Ceiling ft" }, { key: "source", header: "Source" },
              ]} emptyMessage="No recorded observations for this location." />
            </>
          )}
        </>
      )}
    </section>
  );
}
