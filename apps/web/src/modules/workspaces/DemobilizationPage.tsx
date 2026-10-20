import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable from "../../components/table/DataTable";
import { useResourceStatusRows } from "../logistics/resourceStatus/hooks";
import "./workspaces.css";

export default function DemobilizationPage() {
  const { incidentId } = useSession();
  const [params, setParams] = useSearchParams();
  const query = useResourceStatusRows(incidentId!, "");
  const q = (params.get("q") ?? "").toLowerCase();
  const rows = (query.data ?? []).filter(r => (params.get("all") === "1" || ["Preparing for Demobilization", "Demobilized"].includes(r.status)) && `${r.resource_name} ${r.resource_type} ${r.location ?? ""}`.toLowerCase().includes(q))
    .sort((a, b) => a.resource_name.localeCompare(b.resource_name));
  return <section className="workspace-page"><h1>Demobilization</h1><p>Review resources preparing for release. Open a resource to update its status, destination, and notes through the existing resource workflow. A dedicated ICS 221 checkout checklist is not yet available.</p>
    <div className="workspace-filters"><label>Search<input value={params.get("q") ?? ""} onChange={e => setParams(previous => { const next = new URLSearchParams(previous); next.set("q", e.target.value); return next; })} /></label>
      <label><input type="checkbox" checked={params.get("all") === "1"} onChange={e => setParams(previous => { const next = new URLSearchParams(previous); e.target.checked ? next.set("all", "1") : next.delete("all"); return next; })} /> Show all resources</label></div>
    {query.isLoading && <p>Loading resources…</p>}{query.error && <p role="alert" className="error">{query.error.message}</p>}
    <DataTable tableId="demobilization-resources" rows={rows} rowKey={r => `${r.entity_type}:${r.record_id}`} columns={[
      { key: "resource_name", header: "Resource", render: r => <Link to={`/logistics/resources/${encodeURIComponent(r.entity_type)}/${encodeURIComponent(String(r.record_id))}`}>{r.resource_name}</Link> },
      { key: "resource_type", header: "Type" }, { key: "status", header: "Status" }, { key: "assigned_to", header: "Assignment" }, { key: "location", header: "Location" },
    ]} emptyMessage="No resources match the demobilization filter." />
  </section>;
}
