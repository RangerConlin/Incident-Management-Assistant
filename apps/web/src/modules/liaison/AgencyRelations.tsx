import { Link, useSearchParams } from "react-router-dom";
import type { LiaisonRecord } from "../../api/types";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import { formatDateTime } from "../../utils/formatDateTime";
import { useAgencyDetail } from "./hooks";
const SECTIONS = ["contacts", "interactions", "restrictions", "agreements", "feedback", "followups", "requests", "offers"] as const;
const labels: Record<string, string> = { contacts: "Contacts", interactions: "Interactions", restrictions: "Restrictions", agreements: "Agreements", feedback: "Recorded feedback", followups: "Recorded follow-ups", requests: "Earlier external requests", offers: "Earlier resource offers" };
export default function AgencyRelations({ incidentId, agencyId }: { incidentId: string; agencyId: number }) {
  const query = useAgencyDetail(incidentId, agencyId); const [params, setParams] = useSearchParams();
  const requested = params.get("tab") ?? "contacts";
  const tab = SECTIONS.includes(requested as typeof SECTIONS[number]) ? requested as typeof SECTIONS[number] : "contacts";
  const rows = query.data?.[tab] ?? [];
  const keys = [...new Set(rows.flatMap(r => Object.keys(r)))].filter(key => !["_id", "incident_id", "agency_id", "deleted"].includes(key));
  const columns: ColumnDef<LiaisonRecord>[] = keys.map(key => ({ key, header: key.replace(/_/g, " "), defaultWidth: key === "summary" || key === "notes" ? 300 : 180, render: row => {
    const value = row[key];
    if (key.endsWith("_at") || key.endsWith("_ts") || key.endsWith("_due")) return formatDateTime(String(value ?? ""));
    if (value === null || value === undefined) return "—";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    return typeof value === "object" ? JSON.stringify(value) : String(value);
  } }));
  return <section className="liaison-panel"><div className="liaison-toolbar"><h3>Agency records</h3><Link to={`/liaison/agencies/${agencyId}/contacts/new`}>Add contact</Link><Link to={`/liaison/interactions/new?agency=${agencyId}`}>Log interaction</Link><Link to={`/liaison/requests?agency=${agencyId}`}>Current requests / offers</Link></div>
    <nav className="liaison-toolbar" aria-label="Agency record categories">{SECTIONS.map(key => <button key={key} className={tab === key ? "" : "secondary"} onClick={() => setParams(old => { const next = new URLSearchParams(old); next.set("tab", key); return next; }, { replace: true })}>{labels[key]}</button>)}</nav>
    {query.isError ? <p className="error" role="alert">Could not load agency records. <button onClick={() => void query.refetch()}>Retry</button></p> : query.isPending ? <p role="status">Loading agency records…</p> :
      <DataTable tableId={`liaison-agency-${tab}`} columns={columns.length ? columns : [{ key: "name", header: labels[tab] }]} rows={rows} rowKey={r => r.int_id} emptyMessage={`No ${labels[tab].toLowerCase()} recorded.`} />}
    <p>These related records are read-only. Contacts and interactions can be added using the actions above.</p>
    {(tab === "requests" || tab === "offers") && <p>These are the earlier agency-specific records. Current requests and offers are managed together on the Requests / Offers board.</p>}
  </section>;
}
