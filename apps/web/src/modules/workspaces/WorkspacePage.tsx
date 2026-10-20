import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { type Dataset, type RecordData, type Workspace } from "./config";
import { defaultValues, fieldValue, filterRows, localDatetime, payloadFor, recordId } from "./model";
import { useDataset, useRecordActions } from "./hooks";
import "./workspaces.css";

export function displayValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map(v => typeof v === "object" ? Object.values(v ?? {}).join(" · ") : String(v)).join(", ") || "—";
  if (typeof value === "object") return Object.entries(value).map(([k, v]) => `${k.replace(/_/g, " ")}: ${displayValue(k, v)}`).join("; ");
  if (/(?:_at|_time|datetime)$/.test(key) || key === "time") return formatDateTime(String(value));
  return String(value);
}
export default function WorkspacePage({ workspace }: { workspace: Workspace }) {
  const { datasetKey } = useParams();
  const [params, setParams] = useSearchParams();
  const dataset = workspace.datasets.find(d => d.key === datasetKey) ?? (datasetKey ? undefined : workspace.datasets[0]);
  if (!dataset) return <Navigate to={workspace.path} replace />;
  const op = Math.max(1, Math.floor(Number(params.get("op")) || 1));
  const scopedDataset = dataset.opScoped ? { ...dataset, endpoint: `${dataset.endpoint}?op=${op}` } : dataset;
  return <section className="workspace-page">
    <h1>{workspace.title}</h1><p>{workspace.description}</p>
    <nav className="workspace-links" aria-label={`${workspace.title} sections`}>
      {workspace.datasets.map(d => <Link key={d.key} aria-current={d === dataset ? "page" : undefined} to={`${workspace.path}/${d.key}`}>{d.title}</Link>)}
      {workspace.links?.map(link => <Link key={link.to} to={link.to}>{link.label}</Link>)}
    </nav>
    {dataset.opScoped && <label className="field">Operational period number<input type="number" min={1} step={1} value={op} onChange={e => setParams(previous => { const next = new URLSearchParams(previous); next.set("op", e.target.value); return next; })} /></label>}
    <DatasetContent key={`${dataset.key}:${op}`} workspace={workspace} dataset={scopedDataset} />
  </section>;
}
function DatasetContent({ workspace, dataset }: { workspace: Workspace; dataset: Dataset }) {
  const { incidentId } = useSession();
  const { recordId: routeId } = useParams();
  const [params, setParams] = useSearchParams();
  const query = useDataset(dataset, incidentId!);
  const { save, remove } = useRecordActions(dataset, incidentId!);
  const navigate = useNavigate();
  const [values, setValues] = useState<RecordData | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [validationError, setValidationError] = useState("");
  const creating = routeId === "new";
  const row = query.data?.find(r => recordId(dataset, r) === routeId);
  const boardPath = `${workspace.path}/${dataset.key}`;
  const board = `${boardPath}${params.size ? `?${params}` : ""}`;
  useEffect(() => { setValues(null); setConfirmDelete(false); setValidationError(""); save.reset(); remove.reset(); }, [routeId]); // Form draft survives polling.
  const changeParam = (key: string, value: string) => setParams(previous => { const next = new URLSearchParams(previous); value ? next.set(key, value) : next.delete(key); return next; });
  const fields = dataset.columns ?? dataset.fields.filter(f => f.kind !== "textarea" && f.kind !== "list").slice(0, 7).map(f => f.key);
  const filtered = filterRows(query.data ?? [], [...new Set([...fields, ...dataset.fields.map(f => f.key)])], params);
  const columns: ColumnDef<RecordData>[] = fields.map(key => ({ key, header: dataset.fields.find(f => f.key === key)?.label ?? key.replace(/_/g, " "), render: r => ["status", "status_id", "priority", "initial_risk", "residual_risk", "severity"].includes(key) ? <StatusPill statusKey={displayValue(key, fieldValue(r, key))} /> : displayValue(key, fieldValue(r, key)) }));
  columns.unshift({ key: "open", header: "Record", render: r => <Link to={`${boardPath}/${encodeURIComponent(recordId(dataset, r))}${params.size ? `?${params}` : ""}`}>Open</Link>, defaultWidth: 85 });
  const promoted = Boolean(row?.promoted_read_only);
  const editable = creating ? dataset.create : dataset.update && !promoted;
  const current = values ?? (creating ? defaultValues(dataset.fields) : row ?? {});
  const error = query.error ?? save.error ?? remove.error;
  return <>
    <h2>{dataset.title}</h2>{dataset.description && <p>{dataset.description}</p>}
    {error && <p className="error" role="alert">{error.message}</p>}
    {validationError && <p className="error" role="alert">{validationError}</p>}
    {query.isPending ? <p role="status">Loading…</p> : query.isError ? <button onClick={() => query.refetch()}>Retry</button> : routeId ? <>
      <Link to={board}>← Back to {dataset.title.toLowerCase()}</Link>
      {!creating && !row ? <p role="alert">Record not found.</p> : creating && !dataset.create ? <p>This collection does not support creation here.</p> : <>
        <h3>{creating ? "New record" : String(row?.title ?? row?.name ?? row?.label ?? `Record ${routeId}`)}</h3>
        <form className="workspace-form" onSubmit={event => { event.preventDefault(); try { const body = payloadFor(dataset, current, creating, incidentId!); setValidationError(""); save.mutate({ id: creating ? null : routeId!, body }, { onSuccess: () => navigate(board) }); } catch (error) { setValidationError((error as Error).message); } }}>
          {dataset.fields.filter(field => creating ? !field.editOnly : true).map(field => {
            const disabled = !editable || (!creating && field.createOnly) || save.isPending;
            const value = fieldValue(current, field.key);
            return <label className="field" key={field.key}>{field.label}
              {field.options ? <select required={field.required} disabled={disabled} value={String(value ?? "")} onChange={e => setValues({ ...current, [field.key]: e.target.value })}><option value="">Select…</option>
                {Boolean(value) && !field.options.includes(String(value)) && <option>{String(value)}</option>}{field.options.map(option => <option key={option}>{option}</option>)}
              </select> : field.kind === "textarea" || field.kind === "list" ? <textarea rows={4} disabled={disabled} required={field.required} value={Array.isArray(value) ? value.join("\n") : String(value ?? "")} onChange={e => setValues({ ...current, [field.key]: field.kind === "list" ? e.target.value.split("\n") : e.target.value })} />
              : field.kind === "checkbox" ? <input type="checkbox" disabled={disabled} checked={Boolean(value)} onChange={e => setValues({ ...current, [field.key]: e.target.checked })} />
              : <input type={field.kind ?? "text"} disabled={disabled} required={field.required} min={field.min} max={field.max} step={field.kind === "number" ? "any" : field.kind === "datetime-local" ? 1 : undefined} value={field.kind === "datetime-local" ? localDatetime(value) : String(value ?? "")} onChange={e => setValues({ ...current, [field.key]: e.target.value })} />}
            </label>;
          })}
          {editable && <button disabled={save.isPending}>{save.isPending ? "Saving…" : creating ? "Create record" : "Save changes"}</button>}
        </form>
        {!creating && row && <details><summary>Record details</summary><dl className="workspace-record">{Object.entries(row).filter(([key]) => !["_id", "incident_id"].includes(key)).map(([key, value]) => <div key={key}><dt>{key.replace(/_/g, " ")}</dt><dd>{displayValue(key, value)}</dd></div>)}</dl></details>}
        {!creating && dataset.remove && !promoted && <div className="workspace-actions">{confirmDelete ? <><p>Remove this record?</p><button className="danger" disabled={remove.isPending} onClick={() => remove.mutate(routeId!, { onSuccess: () => navigate(board) })}>Confirm removal</button><button className="secondary" onClick={() => setConfirmDelete(false)}>Cancel</button></> : <button className="danger" onClick={() => setConfirmDelete(true)}>Remove record</button>}</div>}
      </>}
    </> : <>
      <div className="workspace-filters">
        <label>Search<input value={params.get("q") ?? ""} onChange={e => changeParam("q", e.target.value)} /></label>
        <label>Status<input value={params.get("status") ?? ""} onChange={e => changeParam("status", e.target.value)} /></label>
        <label>Sort by<select value={params.get("sort") ?? fields[0]} onChange={e => changeParam("sort", e.target.value)}>{fields.map(key => <option key={key} value={key}>{dataset.fields.find(f => f.key === key)?.label ?? key.replace(/_/g, " ")}</option>)}</select></label>
        <label>Order<select value={params.get("direction") ?? "asc"} onChange={e => changeParam("direction", e.target.value)}><option value="asc">Ascending</option><option value="desc">Descending</option></select></label>
        {dataset.create && <Link to={`${boardPath}/new${params.size ? `?${params}` : ""}`}>New record</Link>}
      </div>
      <p>{filtered.length} records</p><DataTable tableId={`workspace-${dataset.collection}`} rows={filtered} columns={columns} rowKey={r => recordId(dataset, r)} onRowActivate={r => navigate(`${boardPath}/${encodeURIComponent(recordId(dataset, r))}${params.size ? `?${params}` : ""}`)} emptyMessage="No matching records." />
    </>}
  </>;
}

