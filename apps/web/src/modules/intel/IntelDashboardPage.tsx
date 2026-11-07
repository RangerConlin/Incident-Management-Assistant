import { Link } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import KpiStrip from "../../components/KpiStrip";
import EntryCard from "../command/EntryCard";
import { intelPriorityVar } from "../../styles/statusColors";
import { formatDateTime } from "../../utils/formatDateTime";
import { useIntelDashboard } from "./hooks";

// No desktop equivalent for a landing page — desktop's IntelWindow opens
// straight to its Dashboard *tab*, not a separate window — but this mockup
// section follows the same dashboard-first shape Command/Planning/Medical
// use on the web: a KPI rollup plus quick-glance panels that link into the
// real boards. Reuses command.css's .command-panel/.command-grid and the
// shared EntryCard accordion instead of inventing new dashboard markup.
export default function IntelDashboardPage() {
  const { incidentId } = useSession();
  const { data, isLoading, error } = useIntelDashboard(incidentId!);

  if (!incidentId) return null;

  return (
    <div>
      <h2>Intel Dashboard</h2>
      {error && <p className="error">Could not load the Intel dashboard.</p>}
      {isLoading || !data ? (
        <p>Loading…</p>
      ) : (
        <>
          <KpiStrip
            tiles={[
              { key: "critical", value: data.critical_items, label: "Critical Intel Items", accent: intelPriorityVar("Critical").bg },
              { key: "assessments", value: data.open_assessments, label: "Open Assessments", accent: "var(--status-severity-warning-bg)" },
              { key: "worsening", value: data.worsening_items, label: "Worsening Trends", accent: "var(--status-intel-trend-worsening-bg)" },
              { key: "leads", value: data.open_leads, label: "Open Leads", accent: "var(--status-severity-info-bg)" },
            ]}
          />

          <div className="command-grid">
            <section className="command-panel">
              <h3>Recent Activity</h3>
              {data.recent_activity.length === 0 ? (
                <p className="entry-empty">No activity logged yet.</p>
              ) : (
                data.recent_activity.slice(0, 8).map((a, i) => (
                  <p key={i} style={{ fontSize: "0.86rem", margin: "6px 0" }}>
                    <span style={{ opacity: 0.6, fontFamily: "monospace" }}>{formatDateTime(a.timestamp)}</span>{" "}
                    {a.summary}
                  </p>
                ))
              )}
              <Link className="panel-link" to="/intel/log">
                View Intel Log →
              </Link>
            </section>

            <section className="command-panel">
              <h3>Critical Intel Items</h3>
              {data.critical_item_list.length === 0 ? (
                <p className="entry-empty">No critical intel items.</p>
              ) : (
                data.critical_item_list.map((item, i) => (
                  <EntryCard
                    key={i}
                    severity="critical"
                    flag={item.priority}
                    title={item.title || "(untitled)"}
                    when={formatDateTime(item.updated_at)}
                    summary={`${item.item_type} · Trend: ${item.trend}`}
                  >
                    <Link className="panel-link" to="/intel/items">
                      Go to Intel Items →
                    </Link>
                  </EntryCard>
                ))
              )}
              <Link className="panel-link" to="/intel/items">
                Go to Intel Items →
              </Link>
            </section>

            <section className="command-panel">
              <h3>Open Leads</h3>
              {data.open_lead_list.length === 0 ? (
                <p className="entry-empty">No open leads.</p>
              ) : (
                data.open_lead_list.map((lead, i) => (
                  <EntryCard
                    key={i}
                    title={lead.title || "(untitled)"}
                    summary={`${lead.assigned_to || "Unassigned"} · ${lead.source_type || "Unknown source"} · ${lead.status}`}
                  >
                    <Link className="panel-link" to="/intel/leads">
                      View All Leads →
                    </Link>
                  </EntryCard>
                ))
              )}
              <Link className="panel-link" to="/intel/leads">
                View All Leads →
              </Link>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
