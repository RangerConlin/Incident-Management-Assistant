import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import FilterBar from "../../components/table/FilterBar";
import { formatDateTime } from "../../utils/formatDateTime";
import type { RecordConfig } from "./config";
import { describeError, usePlannedRecords, usePlannedWrites } from "./hooks";
import { toApiTime, toLocalInput, type PlannedRecord } from "./model";
import { ErrorNote, Field } from "./ui";

const metaOf = (r: PlannedRecord, key: string) => String(r.metadata?.[key] ?? "");

export function RecordsBoard({ config }: { config: RecordConfig }) {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const query = usePlannedRecords(incidentId!, config.tool);
  const update = (key: string, value: string) => setParams(old => { const next = new URLSearchParams(old); if (value) next.set(key, value); else next.delete(key); return next; }, { replace: true });
  const all = query.data ?? [];
  const statuses = [...new Set(all.map(r => r.status).filter(Boolean))];
  const q = (params.get("q") ?? "").toLowerCase();
  const status = params.get("status") ?? "";
  const rows = all.filter(r => (!status || r.status === status) && (!q || [r.title, r.summary, r.assigned_to, r.location, ...config.meta.map(m => metaOf(r, m.key))].some(v => (v ?? "").toLowerCase().includes(q))));
  const columns: ColumnDef<PlannedRecord>[] = [
    { key: "title", header: config.singular, defaultWidth: 260, sortable: true, sortValue: r => r.title.toLowerCase(), render: r => <Link to={`${r.id}`}>{r.title || `${config.singular} #${r.id}`}</Link> },
    { key: "status", header: "Status", defaultWidth: 130, sortable: true, sortValue: r => r.status, render: r => r.status || "—" },
    ...config.meta.map(m => ({ key: m.key, header: m.label, defaultWidth: 170, sortable: true, sortValue: (r: PlannedRecord) => metaOf(r, m.key), render: (r: PlannedRecord) => metaOf(r, m.key) || "—" })),
    { key: "scheduled_at", header: config.scheduledLabel, defaultWidth: 160, sortable: true, sortValue: r => r.scheduled_at, render: r => formatDateTime(r.scheduled_at) },
    { key: "assigned_to", header: "Responsible", defaultWidth: 160, sortable: true, sortValue: r => r.assigned_to, render: r => r.assigned_to || "—" },
    { key: "location", header: "Location", defaultWidth: 160, render: r => r.location || "—" },
  ];
  return (
    <>
      <div className="pe-toolbar"><h3>{config.title}</h3><Link to="new">New {config.singular.toLowerCase()}</Link><button className="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh</button></div>
      <p>{config.intro}</p>
      <FilterBar search={params.get("q") ?? ""} onSearchChange={v => update("q", v)} activeFilters={status ? [{ key: "status", label: status }] : []} onClearFilter={k => update(k, "")} onResetAll={() => setParams({})}>
        {statuses.length > 0 && <select aria-label="Status filter" value={status} onChange={e => update("status", e.target.value)}><option value="">All statuses</option>{statuses.map(s => <option key={s}>{s}</option>)}</select>}
      </FilterBar>
      {query.isError ? <p className="error" role="alert">Could not load {config.title.toLowerCase()}. Refresh to retry.</p> : query.isPending ? <p role="status">Loading…</p> :
        <DataTable tableId={`planned-${config.path}`} columns={columns} rows={rows} rowKey={r => r.id} onRowActivate={r => navigate(`${r.id}`)} emptyMessage={all.length ? "Nothing matches your filters." : `No ${config.title.toLowerCase()} yet.`} />}
    </>
  );
}

export function RecordPage({ config }: { config: RecordConfig }) {
  const { recordId } = useParams();
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const query = usePlannedRecords(incidentId!, config.tool);
  const writes = usePlannedWrites(incidentId!, config.tool);
  const isNew = recordId === "new";
  const record = isNew ? undefined : query.data?.find(r => String(r.id) === recordId);
  if (!isNew && query.isError) return <p className="error" role="alert">Could not load this {config.singular.toLowerCase()}. Refresh to retry.</p>;
  if (!isNew && query.isPending) return <p role="status">Loading…</p>;
  if (!isNew && !record) return <p>{config.singular} not found. <Link to={`/toolkits/planned-event/${config.path}`}>Back to {config.title.toLowerCase()}</Link></p>;
  return <RecordForm key={record?.id ?? "new"} config={config} record={record} statuses={[...new Set((query.data ?? []).map(r => r.status).filter(Boolean))]}
    busy={writes.save.isPending || writes.remove.isPending}
    onSave={(body, done, fail) => writes.save.mutate({ recordId: record?.id, body }, { onSuccess: saved => done(saved.id), onError: fail })}
    onDelete={(fail) => record && writes.remove.mutate(record.id, { onSuccess: () => navigate(`/toolkits/planned-event/${config.path}`), onError: fail })} />;
}

function RecordForm({ config, record, statuses, busy, onSave, onDelete }: {
  config: RecordConfig; record?: PlannedRecord; statuses: string[]; busy: boolean;
  onSave: (body: Record<string, unknown>, done: (id: number) => void, fail: (e: unknown) => void) => void; onDelete: (fail: (e: unknown) => void) => void;
}) {
  const navigate = useNavigate();
  const [f, setF] = useState({
    title: record?.title ?? "", status: record?.status ?? config.defaultStatus, assigned_to: record?.assigned_to ?? "", location: record?.location ?? "", zone: record?.zone ?? "",
    scheduled_at: toLocalInput(record?.scheduled_at), summary: record?.summary ?? "",
    meta: Object.fromEntries(config.meta.map(m => [m.key, record ? metaOf(record, m.key) : ""])) as Record<string, string>,
  });
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.title.trim()) return setError("Title is required.");
    setError(null);
    onSave({
      title: f.title.trim(), status: f.status.trim(), assigned_to: f.assigned_to.trim(), location: f.location.trim(), zone: f.zone.trim(),
      scheduled_at: toApiTime(f.scheduled_at), summary: f.summary.trim(), metadata: { ...(record?.metadata ?? {}), ...f.meta },
    }, id => { if (!record) navigate(`/toolkits/planned-event/${config.path}/${id}`, { replace: true }); }, err => setError(describeError(err)));
  };
  return (
    <form className="pe-panel" onSubmit={submit}>
      <div className="pe-toolbar"><h3>{record ? record.title || `${config.singular} #${record.id}` : `New ${config.singular.toLowerCase()}`}</h3><Link to={`/toolkits/planned-event/${config.path}`}>Back to {config.title.toLowerCase()}</Link></div>
      <div className="pe-form">
        <Field label="Title *" htmlFor="pe-rec-title"><input id="pe-rec-title" required value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Status" htmlFor="pe-rec-status">
          <input id="pe-rec-status" list="pe-rec-statuses" value={f.status} onChange={e => setF({ ...f, status: e.target.value })} />
          <datalist id="pe-rec-statuses">{[...new Set([config.defaultStatus, ...statuses])].map(s => <option key={s} value={s} />)}</datalist>
        </Field>
        {config.meta.map(m => (
          <Field key={m.key} label={m.label} htmlFor={`pe-meta-${m.key}`}>
            <input id={`pe-meta-${m.key}`} type={m.kind === "date" ? "date" : "text"} value={f.meta[m.key]} onChange={e => setF({ ...f, meta: { ...f.meta, [m.key]: e.target.value } })} />
          </Field>
        ))}
        <Field label={config.scheduledLabel} htmlFor="pe-rec-when"><input id="pe-rec-when" type="datetime-local" value={f.scheduled_at} onChange={e => setF({ ...f, scheduled_at: e.target.value })} /></Field>
        <Field label="Responsible" htmlFor="pe-rec-who"><input id="pe-rec-who" value={f.assigned_to} onChange={e => setF({ ...f, assigned_to: e.target.value })} /></Field>
        <Field label="Location" htmlFor="pe-rec-loc"><input id="pe-rec-loc" value={f.location} onChange={e => setF({ ...f, location: e.target.value })} /></Field>
        <Field label="Zone" htmlFor="pe-rec-zone"><input id="pe-rec-zone" value={f.zone} onChange={e => setF({ ...f, zone: e.target.value })} /></Field>
        <Field label="Notes" wide htmlFor="pe-rec-notes"><textarea id="pe-rec-notes" value={f.summary} onChange={e => setF({ ...f, summary: e.target.value })} /></Field>
      </div>
      <ErrorNote message={error} />
      <div className="pe-actions">
        <button type="submit" disabled={busy}>{busy ? "Saving…" : record ? "Save changes" : `Create ${config.singular.toLowerCase()}`}</button>
        {record && !confirmDelete && <button type="button" className="secondary" onClick={() => setConfirmDelete(true)}>Delete…</button>}
        {record && confirmDelete && <><span>Delete this {config.singular.toLowerCase()}?</span><button type="button" disabled={busy} onClick={() => onDelete(err => setError(describeError(err)))}>Delete</button><button type="button" className="secondary" onClick={() => setConfirmDelete(false)}>Keep</button></>}
      </div>
    </form>
  );
}
