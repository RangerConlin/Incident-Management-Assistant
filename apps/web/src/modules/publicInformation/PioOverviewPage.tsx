import { Link } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import KpiStrip from "../../components/KpiStrip";
import { usePioSummary } from "./hooks";
export default function PioOverviewPage() {
  const { incidentId } = useSession();
  const query = usePioSummary(incidentId!);
  return <><div className="pio-toolbar"><h3>PAO overview</h3><button className="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh</button></div>
    {query.isPending && <p role="status">Loading public information…</p>}
    {query.isError && <p className="error" role="alert">Could not load the PAO summary. Refresh to retry.</p>}
    {query.data && <KpiStrip tiles={Object.entries(query.data).map(([label, value]) => ({ key: label, label, value }))} />}
    <div className="pio-grid">
      <section className="pio-panel"><h3>Release desk</h3><p>Draft, preview, review, approve, and record publication of incident messages.</p><Link to="/pio/releases/new">Write a release</Link><p><Link to="/pio/releases?status=Pending+Approval">Review pending approvals</Link></p></section>
      <section className="pio-panel"><h3>Media coordination</h3><p>Track inquiries, deadlines, responders, and follow-ups. Create response drafts directly from an inquiry.</p><Link to="/pio/media">Open media inquiries</Link></section>
      <section className="pio-panel"><h3>Consistent messaging</h3><p>Maintain approved talking points, restricted information, and reusable letterhead.</p><Link to="/pio/talking-points">Open talking points</Link><p><Link to="/pio/templates">Manage templates</Link></p></section>
      <section className="pio-panel"><h3>Monitor and document</h3><p>Verify rumors, record response decisions and timelines, and log completed distribution.</p><Link to="/pio/misinformation">Track misinformation</Link><p><Link to="/pio/distribution">Open distribution log</Link></p></section>
    </div></>;
}
