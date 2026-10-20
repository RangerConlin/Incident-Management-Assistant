import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import type { PioTimelineEvent } from "../../api/types";
import { formatDateTime } from "../../utils/formatDateTime";
import { usePioRecords, usePioTimeline, usePioWrites } from "./hooks";
import { localTimestamp, utcTimestamp } from "./model";
import { RECORD_CONFIG, recordDefaults } from "./recordConfig";

const timelineColumns: ColumnDef<PioTimelineEvent>[] = [
  { key: "event_time", header: "When", render: r => formatDateTime(r.event_time), defaultWidth: 180 },
  { key: "event_text", header: "Event", defaultWidth: 360 }, { key: "created_by", header: "Recorded by" },
];
export default function RecordDetailPage() {
  const { section, recordId } = useParams(); const { incidentId } = useSession();
  return RECORD_CONFIG[section!] ? <RecordEditor key={`${incidentId}:${section}:${recordId}`} section={section!} recordId={recordId!} /> : <p>Unknown workspace. <Link to="/pio">PAO overview</Link></p>;
}
function RecordEditor({ section, recordId }: { section: string; recordId: string }) {
  const config = RECORD_CONFIG[section]; const isNew = recordId === "new"; const itemId = Number(recordId);
  const { incidentId, user } = useSession(); const author = user?.display_name || user?.username || "";
  const query = usePioRecords(incidentId!, config.collection); const writes = usePioWrites(incidentId!);
  const timeline = usePioTimeline(incidentId!, itemId, section === "misinformation" && !isNew);
  const [params] = useSearchParams(); const navigate = useNavigate();
  const [patch, setPatch] = useState<Record<string, unknown>>({}); const [event, setEvent] = useState("");
  const [failure, setFailure] = useState(""); const [notice, setNotice] = useState("");
  const existing = query.data?.find(r => r.id === itemId);
  const defaults = recordDefaults(config);
  if (section === "distribution" && isNew) defaults.message_id = params.get("message") ? Number(params.get("message")) : "";
  const values: Record<string, unknown> = { ...defaults, ...(isNew ? {} : existing), ...patch };
  const dirty = Object.keys(patch).length > 0;
  useEffect(() => { if (!dirty) return; const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  const update = (key: string, value: unknown) => { setPatch(old => ({ ...old, [key]: value })); setNotice(""); };
  const busy = writes.record.isPending || writes.response.isPending || writes.timeline.isPending;
  const run = async (action: () => Promise<unknown>) => { setFailure(""); setNotice(""); try { await action(); } catch (e) { setFailure(e instanceof Error ? e.message : "Request failed. Your edits remain available."); } };
  const save = async () => {
    const body: Record<string, unknown> = {};
    for (const field of config.fields) body[field.key] = values[field.key];
    if (!isNew) { body.id = itemId; if (existing?.created_at) body.created_at = existing.created_at; }
    if (section === "misinformation") body.timeline = timeline.data ?? existing?.timeline ?? [];
    if (config.timestamp) body[config.timestamp] = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    const saved = await writes.record.mutateAsync({ collection: config.collection, body });
    setPatch({}); setNotice("Saved."); if (isNew) navigate(`/pio/${section}/${saved.id}`, { replace: true });
  };
  if (!isNew && (!Number.isInteger(itemId) || itemId < 1)) return <p className="error">Invalid record ID.</p>;
  if (!isNew && query.isPending) return <p role="status">Loading record…</p>;
  if (!isNew && (query.isError || !existing)) return <p className="error" role="alert">{query.isError ? "Could not load this record." : "Record not found."} <Link to={`/pio/${section}`}>Back to {config.title.toLowerCase()}</Link>{query.isError && <button onClick={() => void query.refetch()}>Retry</button>}</p>;
  return <><Link to={`/pio/${section}`}>Back to {config.title.toLowerCase()}</Link><div className="pio-toolbar"><h3>{isNew ? `New ${config.singular.toLowerCase()}` : String(values[config.labelKey] || config.singular)}</h3>{dirty && <span>Unsaved changes</span>}</div>
    {failure && <p className="error" role="alert">{failure}</p>}{notice && <p role="status">{notice}</p>}
    <form onSubmit={e => { e.preventDefault(); void run(save); }}><fieldset className="pio-form pio-panel" disabled={busy}>
      <legend>{config.singular}</legend>
      {config.fields.map(field => <div className={`field ${field.kind === "textarea" ? "pio-wide" : ""}`} key={field.key}>
        <label htmlFor={`pio-record-${field.key}`}>{field.label}{field.required ? " *" : ""}</label>
        {field.kind === "textarea" ? <textarea id={`pio-record-${field.key}`} value={String(values[field.key] ?? "")} required={field.required} onChange={e => update(field.key, e.target.value)} /> :
         field.kind === "checkbox" ? <input id={`pio-record-${field.key}`} type="checkbox" checked={Boolean(values[field.key])} onChange={e => update(field.key, e.target.checked ? 1 : 0)} /> :
         field.kind === "select" ? <select id={`pio-record-${field.key}`} value={String(values[field.key] ?? "")} onChange={e => update(field.key, e.target.value)}>{[...new Set([...(field.options ?? []), String(values[field.key] ?? "")])].map(s => <option key={s}>{s}</option>)}</select> :
         ["time", "deadline", "first_seen", "last_seen", "distributed_at"].includes(field.key) ? <input id={`pio-record-${field.key}`} type="datetime-local" step="1" value={localTimestamp(values[field.key])} onChange={e => update(field.key, utcTimestamp(e.target.value))} /> :
         <input id={`pio-record-${field.key}`} type={field.kind === "number" ? "number" : "text"} min={field.kind === "number" ? 1 : undefined} step={field.kind === "number" ? 1 : undefined} required={field.required} value={String(values[field.key] ?? "")} placeholder={["time", "deadline", "first_seen", "last_seen", "distributed_at"].includes(field.key) ? "YYYY-MM-DD HH:MM:SS with timezone" : undefined} onChange={e => update(field.key, field.kind === "number" && e.target.value ? Number(e.target.value) : e.target.value)} />}
      </div>)}<div className="pio-wide pio-toolbar"><button type="submit">{busy ? "Saving…" : "Save"}</button>
      {!isNew && <button type="button" className="danger" onClick={() => { if (window.confirm(`Delete this ${config.singular.toLowerCase()}?`)) void run(async () => { await writes.record.mutateAsync({ collection: config.collection, body: { ...existing, deleted: true } }); navigate(`/pio/${section}`); }); }}>Delete record</button>}</div>
    </fieldset></form>
    {section === "templates" && <p>Header, footer and contact blocks support fields such as {"{incident_name}"}, {"{incident_number}"}, {"{release_title}"}, {"{prepared_by}"}, and {"{agency_name}"}. Select a template in the release editor to preview it. Logo paths are references; the browser preview is text-based.</p>}
    {section === "media" && !isNew && <section className="pio-panel"><h3>Response</h3>{values.related_message_id ? <Link to={`/pio/releases/${values.related_message_id}`}>Open linked release #{String(values.related_message_id)}</Link> : <button disabled={busy || dirty} onClick={() => void run(async () => { const draft = await writes.response.mutateAsync({ mediaId: itemId, user: author }); navigate(`/pio/releases/${draft.id}`); })}>Create response draft</button>}{dirty && <p>Save the inquiry before creating a response draft.</p>}</section>}
    {section === "misinformation" && !isNew && <section className="pio-panel"><h3>Verification / response timeline</h3>
      {timeline.isError ? <p className="error">Could not load the timeline.</p> : timeline.isPending ? <p>Loading timeline…</p> : <DataTable tableId="pio-misinformation-timeline" columns={timelineColumns} rows={timeline.data ?? []} rowKey={r => r.id} emptyMessage="No events recorded." />}
      <form onSubmit={e => { e.preventDefault(); void run(async () => { await writes.timeline.mutateAsync({ itemId, text: event.trim(), user: author }); setEvent(""); setNotice("Timeline event added."); }); }}><div className="field"><label htmlFor="pio-event">New timeline event</label><textarea id="pio-event" value={event} onChange={e => setEvent(e.target.value)} /></div><button disabled={busy || !event.trim()}>Add event</button></form>
    </section>}
  </>;
}
