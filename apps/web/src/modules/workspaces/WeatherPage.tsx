import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { addWeatherLocation, getWeatherConfig, removeWeatherLocation, setWeatherDefault, weatherHistory } from "../../api/endpoints";
import { useSession } from "../../auth/SessionContext";
import DataTable from "../../components/table/DataTable";
import type { RecordData } from "./config";
import { formatDateTime } from "../../utils/formatDateTime";
import "./workspaces.css";

export default function WeatherPage() {
  const { incidentId } = useSession();
  const [params, setParams] = useSearchParams();
  const location = params.get("location") ?? "";
  const [label, setLabel] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [codes, setCodes] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const client = useQueryClient();
  const key = ["incident", incidentId, "weather_config"];
  const query = useQuery({ queryKey: key, queryFn: () => getWeatherConfig(incidentId!), refetchInterval: 20_000 });
  const history = useQuery({ queryKey: ["incident", incidentId, "weather_history", location], queryFn: () => weatherHistory(incidentId!, location), enabled: !!location, refetchInterval: 20_000 });
  const mutation = useMutation({ mutationFn: ({ action, id }: { action: "add" | "remove" | "default"; id?: string }) => action === "remove" ? removeWeatherLocation(incidentId!, id!) : action === "default" ? setWeatherDefault(incidentId!, id!) : addWeatherLocation(incidentId!, { label: label.trim(), latitude: lat ? Number(lat) : null, longitude: lon ? Number(lon) : null, icao_codes: codes.split(/[\s,]+/).filter(Boolean).map(c => c.toUpperCase()) }),
    onSuccess: async (_, variables) => { if (variables.action === "add") { setLabel(""); setLat(""); setLon(""); setCodes(""); } if (variables.action === "remove" && variables.id === location) setParams({}); setRemoving(null); await client.invalidateQueries({ queryKey: key }); } });
  const locations = (query.data?.locations ?? []) as RecordData[];
  const error = query.error ?? history.error ?? mutation.error;
  return <section className="workspace-page"><h1>Weather</h1><p>Incident monitoring locations and recorded weather observations. History shows samples already collected by connected clients.</p>
    {error && <p role="alert" className="error">{error.message}</p>}{query.isPending && <p>Loading locations…</p>}
    <DataTable tableId="weather-locations" rows={locations} rowKey={r => String(r.location_id)} columns={[
      { key: "label", header: "Location" }, { key: "latitude", header: "Latitude" }, { key: "longitude", header: "Longitude" }, { key: "icao_codes", header: "Stations", render: r => (r.icao_codes as string[]).join(", ") },
      { key: "source", header: "Source" }, { key: "is_default", header: "Default", render: r => r.is_default ? "Yes" : "No" },
      { key: "actions", header: "Actions", render: r => <div className="workspace-actions"><button disabled={mutation.isPending} onClick={() => setParams({ location: String(r.location_id) })}>History</button><button className="secondary" disabled={mutation.isPending || !!r.is_default} onClick={() => mutation.mutate({ action: "default", id: String(r.location_id) })}>Set default</button>{r.source === "manual" && <button className="danger" disabled={mutation.isPending} onClick={() => setRemoving(String(r.location_id))}>Remove</button>}</div> },
    ]} />
    {removing && <div className="workspace-actions"><p>Remove this monitoring location?</p><button className="danger" disabled={mutation.isPending} onClick={() => mutation.mutate({ action: "remove", id: removing })}>Confirm removal</button><button className="secondary" onClick={() => setRemoving(null)}>Cancel</button></div>}
    <h2>Add monitoring location</h2><form className="workspace-form" onSubmit={e => { e.preventDefault(); mutation.mutate({ action: "add" }); }}>
      <label className="field">Location name<input required value={label} onChange={e => setLabel(e.target.value)} /></label>
      <label className="field">Latitude<input type="number" step="any" min={-90} max={90} value={lat} onChange={e => setLat(e.target.value)} /></label>
      <label className="field">Longitude<input type="number" step="any" min={-180} max={180} value={lon} onChange={e => setLon(e.target.value)} /></label>
      <label className="field">ICAO stations (comma separated)<input value={codes} onChange={e => setCodes(e.target.value)} /></label>
      <button disabled={mutation.isPending || !label.trim()}>Add location</button>
    </form>
    {location && <><h2>Observation history — {String(locations.find(r => r.location_id === location)?.label ?? location)}</h2>{history.isPending && <p>Loading observations…</p>}<DataTable tableId="weather-history" rows={history.data?.samples ?? []} rowKey={r => String(r._id)} columns={[
      { key: "recorded_at", header: "Recorded", render: r => formatDateTime(String(r.recorded_at)) }, { key: "temperature_f", header: "Temperature °F" }, { key: "wind_speed_kt", header: "Wind kt" }, { key: "wind_gust_kt", header: "Gust kt" }, { key: "visibility_sm", header: "Visibility mi" }, { key: "ceiling_ft", header: "Ceiling ft" }, { key: "source", header: "Source" },
    ]} emptyMessage="No recorded observations for this location." /></>}
  </section>;
}
