import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import type { LiaisonRecord } from "../../api/types";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import FilterBar from "../../components/table/FilterBar";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { CONFIG } from "./config";
import { filterRecords, localDate, PRIORITIES, reportState } from "./model";
import { useLiaisonRecords } from "./hooks";

export default function LiaisonBoardPage() {
  const { section } = useParams();
  return CONFIG[section!] ? <Board key={section} section={section!} /> : <p>Unknown Liaison workspace. <Link to="/liaison">Open overview</Link></p>;
}
function Board({ section }: { section: string }) {
  const config = CONFIG[section]; const { incidentId } = useSession(); const navigate = useNavigate();
  const query = useLiaisonRecords(incidentId!, config.section); const agencies = useLiaisonRecords(incidentId!, "agencies");
  const [params, setParams] = useSearchParams();
  const update = (key: string, value: string) => setParams(old => { const next = new URLSearchParams(old); if (value) next.set(key, value); else next.delete(key); return next; }, { replace: true });
  const agencyName = (id: unknown) => String(agencies.data?.find(a => a.int_id === id)?.name ?? `Agency #${id}`);
  const columns: ColumnDef<LiaisonRecord>[] = config.columns.map(column => ({
    key: column.key, header: column.label, defaultWidth: column.key === config.labelKey ? 280 : 175,
    render: r => {
      if (column.key === config.labelKey) return <Link to={`/liaison/${section}/${r.int_id}`}>{String(r[column.key] || (section === "reporting" ? "Standalone note" : `${config.singular} #${r.int_id}`))}</Link>;
      if (column.key === "agency_id") return <Link to={`/liaison/agencies/${r.agency_id}`}>{agencyName(r.agency_id)}</Link>;
      if (column.key === "current_status") return <StatusPill domain="liaison-agency" statusKey={String(r.current_status)} />;
      if (column.key === "status" && section === "requests") return <StatusPill domain="liaison-request" statusKey={String(r.status)} />;
      if (column.key === "priority") return <StatusPill domain="liaison-priority" statusKey={String(r.priority)} />;
      if (column.key === "report_state") return <StatusPill domain="liaison-report" statusKey={r.ready_to_report ? "ready" : "not_ready"} label={reportState(r)} />;
      if (["updated_at", "last_contact", "next_contact_due", "occurred_at", "followup_due"].includes(column.key)) return formatDateTime(String(r[column.key] ?? ""));
      if (column.key === "due_date") return r.due_date ? new Date(`${String(r.due_date).slice(0, 10)}T12:00:00`).toLocaleDateString() : "—";
      return String(r[column.key] ?? "—");
    },
  }));
  const rows = filterRecords(query.data ?? [], params, [...config.columns.map(c => c.key), "raw_note"], config.statusKey, localDate());
  const chips = ["status", "agency", "priority", "attention"].filter(key => params.get(key)).map(key => ({ key, label: key === "attention" ? "Needs attention" : key === "agency" ? agencyName(Number(params.get(key))) : params.get(key)! }));
  return <><div className="liaison-toolbar"><h3>{config.title}</h3><Link to={`/liaison/${section}/new`}>New {config.singular.toLowerCase()}</Link><button className="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh</button></div>
    <FilterBar search={params.get("q") ?? ""} onSearchChange={v => update("q", v)} activeFilters={chips} onClearFilter={key => update(key, "")} onResetAll={() => setParams({})}>
      {config.statuses.length > 0 && <select aria-label="Status filter" value={params.get("status") ?? ""} onChange={e => update("status", e.target.value)}><option value="">All statuses</option>{config.statuses.map(s => <option key={s}>{s}</option>)}</select>}
      {section !== "agencies" && section !== "reporting" && <select aria-label="Agency filter" value={params.get("agency") ?? ""} onChange={e => update("agency", e.target.value)}><option value="">All agencies</option>{agencies.data?.map(a => <option key={a.int_id} value={a.int_id}>{String(a.name)}</option>)}</select>}
      {["agencies", "requests"].includes(section) && <select aria-label="Priority filter" value={params.get("priority") ?? ""} onChange={e => update("priority", e.target.value)}><option value="">All priorities</option>{PRIORITIES.map(p => <option key={p}>{p}</option>)}</select>}
      {section === "requests" && <label><input type="checkbox" checked={params.get("attention") === "1"} onChange={e => update("attention", e.target.checked ? "1" : "")} /> Needs attention</label>}
      <select aria-label="Sort records" value={params.get("sort") ?? config.columns[0].key} onChange={e => update("sort", e.target.value)}>{config.columns.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}</select>
      <select aria-label="Sort direction" value={params.get("direction") ?? "asc"} onChange={e => update("direction", e.target.value)}><option value="asc">Ascending</option><option value="desc">Descending</option></select>
    </FilterBar>
    {query.isError ? <p className="error" role="alert">Could not load {config.title.toLowerCase()}. Refresh to retry.</p> : query.isPending ? <p role="status">Loading…</p> :
      <DataTable tableId={`liaison-${section}`} columns={columns} rows={rows} rowKey={r => r.int_id} onRowActivate={r => navigate(`/liaison/${section}/${r.int_id}`)} emptyMessage={query.data?.length ? "No records match your filters." : "No records yet."} />}
  </>;
}
