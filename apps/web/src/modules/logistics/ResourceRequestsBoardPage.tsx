import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import type { ResourceRequest } from "../../api/types";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import FilterBar from "../../components/table/FilterBar";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { useResourceRequests } from "./hooks";
import { filterRequests, label, PRIORITIES, TRANSITIONS } from "./model";
import "./logistics.css";
export default function ResourceRequestsBoardPage() {
  const { incidentId } = useSession(); const query = useResourceRequests(incidentId!); const navigate = useNavigate();
  const [params, setParams] = useSearchParams(); const update = (key: string, value: string) => setParams(old => { const next = new URLSearchParams(old); if (value) next.set(key, value); else next.delete(key); return next; }, { replace: true });
  const columns: ColumnDef<ResourceRequest>[] = [
    { key: "title", header: "Request", defaultWidth: 300, render: r => <Link to={`/logistics/resource-requests/${r.id}`}>{r.title || r.id}</Link> },
    { key: "status", header: "Status", render: r => <StatusPill domain="logistics-request" statusKey={r.status} label={label(r.status)} /> },
    { key: "priority", header: "Priority", render: r => <StatusPill domain="logistics-priority" statusKey={r.priority} label={label(r.priority)} /> },
    { key: "requesting_section", header: "Requesting section", defaultWidth: 190 },
    { key: "needed_by_utc", header: "Needed by", defaultWidth: 190, render: r => formatDateTime(r.needed_by_utc) },
    { key: "last_updated_utc", header: "Updated", defaultWidth: 190, render: r => formatDateTime(r.last_updated_utc) },
  ];
  return <div className="logistics-page"><Link to="/logistics">Logistics overview</Link><div className="logistics-toolbar"><h2>Resource Requests</h2><Link to="/logistics/resource-requests/new">New request</Link><button className="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh</button></div>
    <p>Record what is needed, when, and where. Add detail as the request develops.</p>
    <FilterBar search={params.get("q") ?? ""} onSearchChange={v => update("q",v)} activeFilters={["status", "priority"].filter(k => params.get(k)).map(key => ({ key, label: label(params.get(key)!) }))} onClearFilter={key => update(key, "")} onResetAll={() => setParams({})}>
      <select aria-label="Request status" value={params.get("status") ?? ""} onChange={e => update("status", e.target.value)}><option value="">All statuses</option>{Object.keys(TRANSITIONS).map(s => <option key={s} value={s}>{label(s)}</option>)}</select>
      <select aria-label="Request priority" value={params.get("priority") ?? ""} onChange={e => update("priority", e.target.value)}><option value="">All priorities</option>{PRIORITIES.map(s => <option key={s} value={s}>{label(s)}</option>)}</select>
      <select aria-label="Sort requests" value={params.get("sort") ?? "last_updated_utc"} onChange={e => update("sort",e.target.value)}>{["last_updated_utc", "needed_by_utc", "title", "priority", "status"].map(s => <option key={s} value={s}>{label(s)}</option>)}</select>
      <select aria-label="Sort direction" value={params.get("direction") ?? "desc"} onChange={e => update("direction",e.target.value)}><option value="desc">Descending</option><option value="asc">Ascending</option></select>
    </FilterBar>{query.isError ? <p className="error" role="alert">Could not load requests. Refresh to retry.</p> : query.isPending ? <p role="status">Loading requests…</p> : <DataTable tableId="logistics-requests" columns={columns} rows={filterRequests(query.data ?? [],params)} rowKey={r => r.id} onRowActivate={r => navigate(`/logistics/resource-requests/${r.id}`)} emptyMessage="No requests match this view." />}
  </div>;
}
