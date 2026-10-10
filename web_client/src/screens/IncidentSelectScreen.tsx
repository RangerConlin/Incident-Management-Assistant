import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../auth/SessionContext";
import { ApiError } from "../api/client";
import { listIncidents } from "../api/endpoints";
import type { Incident } from "../api/types";

export default function IncidentSelectScreen() {
  const { selectIncident, logout } = useSession();
  const navigate = useNavigate();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listIncidents()
      .then(setIncidents)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load incidents."))
      .finally(() => setLoading(false));
  }, []);

  const choose = (incident: Incident) => {
    selectIncident(incident.id);
    navigate("/checkin");
  };

  return (
    <div className="screen">
      <div className="topbar" style={{ margin: "-24px -16px 16px", padding: "12px 16px" }}>
        <h2 style={{ margin: 0 }}>Select Incident</h2>
        <button className="secondary" onClick={logout}>
          Sign Out
        </button>
      </div>
      {loading && <p>Loading incidents…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && incidents.length === 0 && !error && <p>No incidents are available right now.</p>}
      {incidents.map((incident) => (
        <div key={incident.id} className="list-item" onClick={() => choose(incident)}>
          <div>
            <strong>{incident.number}</strong> — {incident.name}
          </div>
          <span>{incident.status || ""}</span>
        </div>
      ))}
    </div>
  );
}
