import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { listIncidents } from "../api/endpoints";
import { useSession } from "../auth/SessionContext";
import { useConnectionStatus } from "../realtime/IncidentSocketProvider";
import { applyTheme, getStoredTheme } from "../styles/statusColors";
import { MODULE_REGISTRY } from "./moduleRegistry";

function ConnectionIndicator() {
  const status = useConnectionStatus();
  const color = status === "connected" ? "#2f6d34" : status === "connecting" ? "#a88f1a" : "#8c2f2f";
  const label = status === "connected" ? "Live" : status === "connecting" ? "Connecting…" : "Polling";
  return (
    <span className="connection-indicator" title={`Incident updates: ${label}`}>
      <span className="connection-dot" style={{ background: color }} />
      {label}
    </span>
  );
}

function IncidentSwitcher() {
  const { incidentId, selectIncident } = useSession();
  const { data: incidents = [] } = useQuery({
    queryKey: ["incidents"],
    queryFn: listIncidents,
    staleTime: 60_000,
  });

  return (
    <select
      className="incident-switcher"
      value={incidentId ?? ""}
      onChange={(e) => selectIncident(e.target.value || null)}
    >
      <option value="" disabled>
        Select incident…
      </option>
      {incidents.map((incident) => (
        <option key={incident.id} value={incident.id}>
          {incident.number} — {incident.name}
        </option>
      ))}
    </select>
  );
}

export default function AppShell() {
  const { user, logout } = useSession();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(getStoredTheme());

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  };

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-sidebar-title">SARApp</div>
        {MODULE_REGISTRY.map((section) => (
          <div key={section.section} className="app-sidebar-section">
            <div className="app-sidebar-section-label">{section.section}</div>
            {section.modules.map((mod) =>
              mod.status === "live" ? (
                <NavLink
                  key={mod.key}
                  to={mod.path}
                  className={({ isActive }) => "app-sidebar-link" + (isActive ? " active" : "")}
                >
                  {mod.label}
                </NavLink>
              ) : (
                <span key={mod.key} className="app-sidebar-link planned" title="Not built yet">
                  {mod.label}
                  <span className="planned-badge">planned</span>
                </span>
              )
            )}
          </div>
        ))}
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <IncidentSwitcher />
          <div className="app-topbar-right">
            <ConnectionIndicator />
            <button className="secondary" style={{ width: "auto" }} onClick={toggleTheme}>
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
            <span>{user?.display_name}</span>
            <button
              className="secondary"
              style={{ width: "auto" }}
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Sign Out
            </button>
          </div>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
