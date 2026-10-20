import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import FilterBar from "../../components/table/FilterBar";
import type { PioRecord } from "../../api/types";
import { formatDateTime } from "../../utils/formatDateTime";
import { usePioRecords } from "./hooks";
import { RECORD_CONFIG } from "./recordConfig";
import { filterPioRows } from "./model";

export default function RecordsBoardPage() {
  const { section } = useParams(); const config = RECORD_CONFIG[section!];
  return config ? <RecordBoard key={section} section={section!} /> : <p>Unknown workspace. <Link to="/pio">PAO overview</Link></p>;
}
function RecordBoard({ section }: { section: string }) {
  const config = RECORD_CONFIG[section]; const { incidentId } = useSession();
  const query = usePioRecords(incidentId!, config.collection); const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? ""; const status = params.get("status") ?? "";
  const update = (key: string, value: string) => setParams(old => { const next = new URLSearchParams(old); if (value) next.set(key, value); else next.delete(key); return next; }, { replace: true });
  const statusOptions = config.fields.find(f => f.key === "status")?.options;
  const columns: ColumnDef<PioRecord>[] = config.fields.map(f => ({
    key: f.key, header: f.label, defaultWidth: f.key === config.labelKey ? 280 : 170,
    defaultVisible: !["verification_notes", "related_confirmed_facts", "attachments_note", "footer_text", "header_text", "default_font_name", "logo_path", "contact_block", "default_classification_label", "default_footer_disclaimer"].includes(f.key),
    render: r => {
      const text = f.kind === "checkbox" ? (r[f.key] ? "Yes" : "No") : String(r[f.key] ?? "—");
      if (f.key === config.labelKey) return <Link to={`/pio/${section}/${r.id}`}>{text || `Record #${r.id}`}</Link>;
      if (f.key === "message_id" || f.key === "related_message_id") return r[f.key] ? <Link to={`/pio/releases/${r[f.key]}`}>Release #{text}</Link> : "—";
      if (["time", "first_seen", "last_seen", "deadline", "distributed_at"].includes(f.key)) return formatDateTime(String(r[f.key] ?? ""));
      return f.key === "status" ? <span className="pio-status">{text}</span> : text;
    },
  }));
  const sort = params.get("sort") ?? config.labelKey;
  const rows = filterPioRows(query.data ?? [], search, status, config.fields.map(f => f.key), sort, params.get("direction") ?? "asc");
  return <><div className="pio-toolbar"><h3>{config.title}</h3><Link to={`/pio/${section}/new`}>New {config.singular.toLowerCase()}</Link><button className="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh</button></div>
    <FilterBar search={search} onSearchChange={v => update("q", v)} activeFilters={status ? [{ key: "status", label: status }] : []} onClearFilter={key => update(key, "")} onResetAll={() => setParams({})}>
      {statusOptions && <select aria-label="Status filter" value={status} onChange={e => update("status", e.target.value)}><option value="">All statuses</option>{statusOptions.map(s => <option key={s}>{s}</option>)}</select>}
      <select aria-label="Sort records" value={sort} onChange={e => update("sort", e.target.value)}>{config.fields.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}</select>
      <select aria-label="Sort direction" value={params.get("direction") ?? "asc"} onChange={e => update("direction", e.target.value)}><option value="asc">Ascending</option><option value="desc">Descending</option></select>
    </FilterBar>
    {query.isError ? <p className="error" role="alert">Could not load {config.title.toLowerCase()}. Refresh to retry.</p> : query.isPending ? <p role="status">Loading…</p> :
      <DataTable tableId={`pio-${section}`} columns={columns} rows={rows} rowKey={r => r.id} onRowActivate={r => navigate(`/pio/${section}/${r.id}`)} emptyMessage={query.data?.length ? "No records match your filters." : "No records yet."} />}
  </>;
}
