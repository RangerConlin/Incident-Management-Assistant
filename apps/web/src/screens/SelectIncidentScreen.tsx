import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listIncidents } from "../api/endpoints";
import { useSession } from "../auth/SessionContext";

export default function SelectIncidentScreen() {
  const { user, selectIncident, logout } = useSession();
  const navigate = useNavigate();
  const { data: incidents = [], isLoading, error } = useQuery({
    queryKey: ["incidents"],
    queryFn: listIncidents,
  });

  const pick = (id: string) => {
    selectIncident(id);
    navigate("/ops/teams");
  };

  return (
    <div className="screen" style={{ maxWidth: 560 }}>
      <h1>SARApp</h1>
      <p>Signed in as {user?.display_name}. Select an incident to continue.</p>

      {isLoading && <p>Loading incidents…</p>}
      {error && <p className="error">Could not load incidents.</p>}

      {!isLoading && !error && incidents.length === 0 && (
        <p>No incidents yet. Create one from the desktop client, then refresh this page.</p>
      )}

      {incidents.map((incident) => (
        <div key={incident.id} className="list-item" onClick={() => pick(incident.id)}>
          <div>
            <div style={{ fontWeight: 600 }}>{incident.number}</div>
            <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>{incident.name}</div>
          </div>
          <span aria-hidden="true">&rsaquo;</span>
        </div>
      ))}

      <button
        className="secondary"
        style={{ width: "auto", marginTop: 24 }}
        onClick={() => {
          logout();
          navigate("/login");
        }}
      >
        Sign out
      </button>
    </div>
  );
}
