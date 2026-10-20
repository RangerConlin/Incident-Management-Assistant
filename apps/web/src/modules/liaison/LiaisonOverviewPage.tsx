import { Link } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import KpiStrip from "../../components/KpiStrip";
import { useLiaisonRecords } from "./hooks";
import { localDate, needsAttention } from "./model";
export default function LiaisonOverviewPage() {
  const { incidentId } = useSession();
  const agencies = useLiaisonRecords(incidentId!, "agencies");
  const requests = useLiaisonRecords(incidentId!, "requests");
  const reports = useLiaisonRecords(incidentId!, "reporting-digests");
  const queries = [agencies, requests, reports];
  const count = (query: { isPending: boolean; isError: boolean }, number: number) => query.isPending || query.isError ? "—" : number;
  return <><div className="liaison-toolbar"><h3>Coordination overview</h3><button className="secondary" disabled={queries.some(q => q.isFetching)} onClick={() => void Promise.all(queries.map(q => q.refetch()))}>Refresh</button></div>
    {queries.some(q => q.isError) && <p className="error" role="alert">Some coordination data could not be loaded. Affected totals are unavailable. Refresh to retry.</p>}
    <KpiStrip tiles={[
      { key: "agencies", label: "Agencies", value: count(agencies, agencies.data?.length ?? 0) },
      { key: "requests", label: "Open requests / offers", value: count(requests, requests.data?.filter(r => ["Open", "In Progress"].includes(String(r.status))).length ?? 0) },
      { key: "attention", label: "Requests needing attention", value: count(requests, requests.data?.filter(r => needsAttention(r, localDate())).length ?? 0) },
      { key: "ready", label: "Ready to report", value: count(reports, reports.data?.filter(r => r.ready_to_report).length ?? 0) },
    ]} />
    <div className="liaison-grid"><section className="liaison-panel"><h3>Agency coordination</h3><p>Maintain agency codes, representatives, contact status, and the next planned contact.</p><Link to="/liaison/agencies">Agency directory</Link><p><Link to="/liaison/interactions/new">Log an interaction</Link></p></section>
      <section className="liaison-panel"><h3>Requests and offers</h3><p>Link outside-agency requests to objectives, tasks, and resource requests. Maintain a narrative of updates and feedback.</p><Link to="/liaison/requests">Open requests / offers</Link><p><Link to="/liaison/requests?attention=1">Review requests needing attention</Link></p></section>
      <section className="liaison-panel"><h3>Reporting desk</h3><p>Keep internal source notes separate from summaries prepared for external agencies. Mark a summary ready when it can be shared.</p><Link to="/liaison/reporting">Reporting board</Link><p><Link to="/liaison/reporting?status=Ready">Ready to report</Link></p></section>
      <section className="liaison-panel"><h3>Available records</h3><p>Agency details include contacts, interactions, earlier requests/offers, feedback, follow-ups, agreements, and restrictions.</p><p>Agreements and restrictions are read-only. A unified Liaison activity log and automated delivery do not yet have backing APIs.</p></section>
    </div></>;
}
