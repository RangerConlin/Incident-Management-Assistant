import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import type { Facility } from "../../api/types";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import FilterBar from "../../components/table/FilterBar";
import StatusPill from "../../components/table/StatusPill";
import { useFacilities } from "./hooks";
import { FACILITY_TYPES, label } from "./model";
import "./logistics.css";
export default function FacilitiesBoardPage() {
  const { incidentId } = useSession(); const query = useFacilities(incidentId!); const navigate = useNavigate(); const [params,setParams] = useSearchParams();
  const update = (key: string,value: string) => setParams(old => { const next = new URLSearchParams(old); if (value) next.set(key,value); else next.delete(key); return next; },{ replace: true });
  const q = (params.get("q") ?? "").trim().toLowerCase(); const sort = params.get("sort") ?? "name";
  const rows = (query.data ?? []).filter(f => (!params.get("type") || f.facility_type === params.get("type")) && (!params.get("status") || f.status === params.get("status")) && `${f.name} ${f.address} ${f.manager_name} ${f.function_tags.join(" ")}`.toLowerCase().includes(q)).sort((a,b) => String(a[sort] ?? "").localeCompare(String(b[sort] ?? "")) * (params.get("direction") === "desc" ? -1 : 1));
  const columns: ColumnDef<Facility>[] = [
    { key: "name",header: "Facility",defaultWidth: 250,render: f => <Link to={`/logistics/facilities/${f.id}`}>{f.name}{f.is_primary ? " · Primary" : ""}</Link> },
    { key: "facility_type",header: "Type",render: f => label(f.facility_type) },
    { key: "status",header: "Status",render: f => <StatusPill domain="facility" statusKey={f.status} label={label(f.status)} /> },
    { key: "address",header: "Address",defaultWidth: 260 },{ key: "manager_name",header: "Manager" },{ key: "contact_phone",header: "Contact phone" },
    { key: "function_tags",header: "Functions",render: f => f.function_tags.join(", ") },{ key: "served_sections",header: "Served sections",render: f => f.served_sections.join(", ") },
  ];
  return <div className="logistics-page"><Link to="/logistics">Logistics overview</Link><div className="logistics-toolbar"><h2>Facilities</h2><Link to="/logistics/facilities/new">New facility</Link><button className="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh</button></div>
    <FilterBar search={params.get("q") ?? ""} onSearchChange={v => update("q",v)} activeFilters={["type","status"].filter(k => params.get(k)).map(key => ({ key,label: label(params.get(key)!) }))} onClearFilter={key => update(key,"")} onResetAll={() => setParams({})}>
      <select aria-label="Facility type" value={params.get("type") ?? ""} onChange={e => update("type",e.target.value)}><option value="">All types</option>{FACILITY_TYPES.map(s => <option key={s} value={s}>{label(s)}</option>)}</select>
      <select aria-label="Facility status" value={params.get("status") ?? ""} onChange={e => update("status",e.target.value)}><option value="">All statuses</option>{["active","planned","closed"].map(s => <option key={s} value={s}>{label(s)}</option>)}</select>
      <select aria-label="Sort facilities" value={sort} onChange={e => update("sort",e.target.value)}>{["name","facility_type","status","manager_name"].map(s => <option key={s} value={s}>{label(s)}</option>)}</select>
      <select aria-label="Sort direction" value={params.get("direction") ?? "asc"} onChange={e => update("direction",e.target.value)}><option value="asc">Ascending</option><option value="desc">Descending</option></select>
    </FilterBar>{query.isError ? <p className="error" role="alert">Could not load facilities. Refresh to retry.</p> : query.isPending ? <p>Loading facilities…</p> : <DataTable tableId="logistics-facilities" columns={columns} rows={rows} rowKey={f => f.id} onRowActivate={f => navigate(`/logistics/facilities/${f.id}`)} emptyMessage="No facilities match this view." />}
  </div>;
}
