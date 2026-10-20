import { Link } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import KpiStrip from "../../components/KpiStrip";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import type { ResourceStatusRow, ResourceRequest } from "../../api/types";
import { formatDateTime } from "../../utils/formatDateTime";
import { useResourceStatusRows } from "./resourceStatus/hooks";
import { useFacilities, useResourceRequests } from "./hooks";
import { logisticsCounts, TERMINAL } from "./model";
import "./logistics.css";
export default function LogisticsDashboardPage() {
  const { incidentId } = useSession(); const id = incidentId!;
  const resources = useResourceStatusRows(id); const requests = useResourceRequests(id); const facilities = useFacilities(id);
  const queries = [resources,requests,facilities];
  const counts = logisticsCounts(requests.data ?? [], resources.data ?? [], facilities.data ?? [], new Date());
  const metric = (query: { isPending: boolean; isError: boolean }, value: number) => query.isPending || query.isError ? "—" : value;
  const due = (requests.data ?? []).filter(r => !TERMINAL.includes(r.status) && r.needed_by_utc && new Date(r.needed_by_utc).getTime() <= Date.now() + 86_400_000).sort((a,b) => new Date(a.needed_by_utc!).getTime() - new Date(b.needed_by_utc!).getTime());
  const requestColumns: ColumnDef<ResourceRequest>[] = [{ key: "title", header: "Request", defaultWidth: 260, render: r => <Link to={`/logistics/resource-requests/${r.id}`}>{r.title}</Link> }, { key: "status", header: "Status" }, { key: "needed_by_utc", header: "Needed by", render: r => formatDateTime(r.needed_by_utc), defaultWidth: 180 }];
  const resourceColumns: ColumnDef<ResourceStatusRow>[] = [{ key: "resource_name", header: "Resource", defaultWidth: 250, render: r => <Link to={`/logistics/resources/${r.entity_type}/${encodeURIComponent(String(r.record_id))}`}>{r.resource_name}</Link> }, { key: "resource_type", header: "Type" }, { key: "location", header: "Location" }];
  return <div className="logistics-page"><div className="logistics-toolbar"><h2>Logistics</h2><button className="secondary" disabled={queries.some(q => q.isFetching)} onClick={() => void Promise.all(queries.map(q => q.refetch()))}>Refresh</button></div>
    <nav className="logistics-toolbar" aria-label="Logistics workspaces"><Link to="/logistics/resource-requests/new">New request</Link><Link to="/logistics/resource-requests">Resource requests</Link><Link to="/logistics/checkin">Check-In</Link><Link to="/logistics/resources">Resource status</Link><Link to="/logistics/facilities">Facilities</Link></nav>
    {queries.some(q => q.isError) && <p className="error" role="alert">Some logistics data could not be loaded. Affected totals are unavailable.</p>}
    <KpiStrip tiles={[{ key: "open",label: "Open requests",value: metric(requests,counts.open) }, { key: "pending",label: "Awaiting approval",value: metric(requests,counts.pending) }, { key: "checkin",label: "Resources checked in today",value: metric(resources,counts.checkins) }, { key: "vehicles",label: "Available vehicles",value: metric(resources,counts.vehicles) }, { key: "facilities",label: "Active facilities",value: metric(facilities,counts.facilities) }]} />
    <div className="logistics-grid"><section className="logistics-panel"><h3>Requests overdue or needed within 24 hours</h3>{requests.isError ? <p className="error">Request data unavailable.</p> : requests.isPending ? <p>Loading…</p> : <DataTable tableId="logistics-due" columns={requestColumns} rows={due} rowKey={r => r.id} emptyMessage="No open requests due within 24 hours." />}</section>
      <section className="logistics-panel"><h3>Preparing for demobilization</h3>{resources.isError ? <p className="error">Resource data unavailable.</p> : resources.isPending ? <p>Loading…</p> : <DataTable tableId="logistics-demob" columns={resourceColumns} rows={counts.demob} rowKey={r => `${r.entity_type}:${r.record_id}`} emptyMessage="No resources marked as preparing for demobilization." />}</section>
      <section className="logistics-panel"><h3>Facility readiness</h3>{facilities.isError ? <p className="error">Facility data unavailable.</p> : facilities.isPending ? <p>Loading…</p> : <><p>{counts.facilities} active / {facilities.data?.length ?? 0} recorded facilities.</p><Link to="/logistics/facilities">Manage locations, managers, and functions</Link></>}</section>
      <section className="logistics-panel"><h3>Supply and comms stock</h3><p>Stock levels and comms-cache availability are not tracked by the current API. No stock estimates are shown.</p></section>
    </div></div>;
}
