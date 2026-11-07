import { useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../../components/table/StatusPill";
import { useHazards, useIcs208 } from "./hooks";

// No desktop equivalent — safety/windows.py's get_safety_panel is a
// confirmed one-label placeholder with no content — so this is a fresh
// landing page, same dashboard-first shape as the rest of the shell.
export default function SafetyDashboardPage() {
  const { incidentId } = useSession();
  const [op] = useState(1);
  const { data: hazards = [], isLoading: hazardsLoading } = useHazards(incidentId!, op);
  const { data: ics208, isLoading: ics208Loading } = useIcs208(incidentId!, op);

  if (!incidentId) return null;

  const highRisk = hazards.filter((h) => h.default_spe && (h.default_spe.band === "High" || h.default_spe.band === "Very High"));

  return (
    <div>
      <h2>Safety Dashboard</h2>
      {hazardsLoading || ics208Loading ? (
        <p>Loading…</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
          <section className="planning-panel">
            <h3>Hazard Register</h3>
            <p>
              {hazards.length} hazard{hazards.length === 1 ? "" : "s"} tracked · {highRisk.length} high / very high SPE
            </p>
            {highRisk.slice(0, 3).map((h) => (
              <div key={h.id} className="entry-card">
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <strong>{h.title}</strong>
                  {h.default_spe && <StatusPill domain="spe-band" statusKey={h.default_spe.band} label={h.default_spe.band} />}
                </div>
              </div>
            ))}
            <Link className="panel-link" to="/safety/hazards">
              Open Hazard Dashboard →
            </Link>
          </section>
          <section className="planning-panel">
            <h3>Safety Message (ICS 208)</h3>
            <p>{ics208?.safety_message ? "Drafted for this operational period." : "Not yet authored for this operational period."}</p>
            <Link className="panel-link" to="/safety/208">
              Open Safety Message →
            </Link>
          </section>
          <section className="planning-panel">
            <h3>IWI Reports</h3>
            <p className="muted">Illness/injury (safety incident) reporting.</p>
            <Link className="panel-link" to="/safety/iwi">
              Open IWI Dashboard →
            </Link>
          </section>
          <section className="planning-panel">
            <h3>CAP ORM Worksheet</h3>
            <p className="muted">CAPF 160-style worksheet over the same hazard register.</p>
            <Link className="panel-link" to="/safety/orm">
              Open CAP ORM Worksheet →
            </Link>
          </section>
        </div>
      )}
    </div>
  );
}
