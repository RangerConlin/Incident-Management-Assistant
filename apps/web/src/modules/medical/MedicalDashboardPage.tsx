import { useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../../components/table/StatusPill";
import { useMedicalAidStations, useMedicalPlan } from "./hooks";

// No desktop equivalent — medical/windows.py exposes only the ICS 206
// builder itself, no separate dashboard — so this is a fresh landing page,
// same dashboard-first shape as Command/Planning/Liaison: a status rollup
// plus quick links into the real page.
export default function MedicalDashboardPage() {
  const { incidentId } = useSession();
  const [op] = useState(1);
  const { data: plan, isLoading, error } = useMedicalPlan(incidentId!, op);
  const { data: aidStations = [] } = useMedicalAidStations(incidentId!, op);

  if (!incidentId) return null;

  return (
    <div>
      <h2>Medical Dashboard</h2>
      {isLoading ? (
        <p>Loading…</p>
      ) : error || !plan ? (
        <p className="error">Could not load the medical plan.</p>
      ) : (
        <div className="panel-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
          <section className="planning-panel">
            <h3>ICS 206 — Medical Plan</h3>
            <p>
              Version {plan.version} · <StatusPill domain="approval" statusKey={plan.approval_status} label={plan.approval_status} />
            </p>
            <p className="muted">
              {plan.signatures?.prepared_by ? `Prepared by ${plan.signatures.prepared_by}` : "Not yet prepared."}
            </p>
            <Link className="panel-link" to="/medical/206">
              Open ICS 206 Builder →
            </Link>
          </section>
          <section className="planning-panel">
            <h3>Aid Stations</h3>
            <p>{aidStations.length} recorded for OP {op}.</p>
            <Link className="panel-link" to="/medical/206">
              View in ICS 206 →
            </Link>
          </section>
          <section className="planning-panel">
            <h3>Hospitals</h3>
            <p>{plan.hospitals.length} on file for OP {op}.</p>
            <Link className="panel-link" to="/medical/206">
              View in ICS 206 →
            </Link>
          </section>
          <section className="planning-panel">
            <h3>Medical Communications</h3>
            <p>{plan.medical_comms.length} channel(s) assigned.</p>
            <Link className="panel-link" to="/medical/206">
              View in ICS 206 →
            </Link>
          </section>
        </div>
      )}
    </div>
  );
}
