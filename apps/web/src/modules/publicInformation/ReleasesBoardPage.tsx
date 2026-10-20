import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import FilterBar from "../../components/table/FilterBar";
import StatusPill from "../../components/table/StatusPill";
import type { PioMessage } from "../../api/types";
import { formatDateTime } from "../../utils/formatDateTime";
import { usePioMessages } from "./hooks";
import { filterPioRows, MESSAGE_STATUSES } from "./model";
export default function ReleasesBoardPage() {
  const { incidentId } = useSession(); const query = usePioMessages(incidentId!);
  const navigate = useNavigate(); const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? ""; const status = params.get("status") ?? "";
  const update = (key: string, value: string) => setParams(old => { const next = new URLSearchParams(old); if (value) next.set(key, value); else next.delete(key); return next; }, { replace: true });
  const columns: ColumnDef<PioMessage>[] = [
    { key: "title", header: "Release", defaultWidth: 290, render: r => <Link to={`/pio/releases/${r.id}`}>{r.title || `Release #${r.id}`}</Link> },
    { key: "status", header: "Status", defaultWidth: 190, render: r => <StatusPill domain="pio" statusKey={r.status} /> },
    { key: "type", header: "Type", defaultWidth: 170 }, { key: "audience", header: "Audience" }, { key: "priority", header: "Priority" },
    { key: "created_by", header: "Prepared by" }, { key: "updated_at", header: "Updated", render: r => formatDateTime(r.updated_at), defaultWidth: 190 },
  ];
  const rows = filterPioRows(query.data ?? [], search, status, ["title", "subtitle", "body", "type", "created_by"], params.get("sort") ?? "updated_at", params.get("direction") ?? "desc");
  return <><div className="pio-toolbar"><h3>Messages / releases</h3><Link to="/pio/releases/new">New release</Link><button className="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh</button></div>
    <FilterBar search={search} onSearchChange={v => update("q", v)} activeFilters={status ? [{ key: "status", label: status }] : []} onClearFilter={key => update(key, "")} onResetAll={() => setParams({})}>
      <select aria-label="Release status" value={status} onChange={e => update("status", e.target.value)}><option value="">All statuses</option>{MESSAGE_STATUSES.map(s => <option key={s}>{s}</option>)}</select>
      <select aria-label="Sort releases" value={params.get("sort") ?? "updated_at"} onChange={e => update("sort", e.target.value)}><option value="updated_at">Updated</option><option value="title">Title</option><option value="priority">Priority</option><option value="status">Status</option></select>
      <select aria-label="Sort direction" value={params.get("direction") ?? "desc"} onChange={e => update("direction", e.target.value)}><option value="desc">Descending</option><option value="asc">Ascending</option></select>
    </FilterBar>
    {query.isError ? <p className="error" role="alert">Could not load releases. Refresh to retry.</p> : query.isPending ? <p role="status">Loading releases…</p> :
      <DataTable tableId="pio-releases" columns={columns} rows={rows} rowKey={r => r.id} onRowActivate={r => navigate(`/pio/releases/${r.id}`)} emptyMessage={query.data?.length ? "No releases match your filters." : "No releases yet. Create a release to get started."} />}
  </>;
}
