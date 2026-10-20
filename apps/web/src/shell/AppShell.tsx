import { version } from "../../package.json";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { listIncidents } from "../api/endpoints";
import { useSession } from "../auth/SessionContext";
import { useConnectionStatus } from "../realtime/IncidentSocketProvider";
import { applyTheme, getStoredTheme } from "../styles/statusColors";
import { findSectionForPath, MODULE_REGISTRY, type ModuleSection } from "./moduleRegistry";

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

function CurrentIncident() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const { data: incidents = [] } = useQuery({
    queryKey: ["incidents"],
    queryFn: listIncidents,
    staleTime: 60_000,
  });
  const current = incidents.find((i) => i.id === incidentId);

  return (
    <div className="current-incident">
      <span className="current-incident-label">
        {current ? `${current.number} — ${current.name}` : "No incident selected"}
      </span>
      <button className="secondary" style={{ width: "auto" }} onClick={() => navigate("/select-incident")}>
        Switch
      </button>
    </div>
  );
}

function firstNavigableModule(section: ModuleSection) {
  return section.modules.find((m) => m.status === "live") ?? section.modules[0];
}

function ModuleRail({ activeSection }: { activeSection: ModuleSection | undefined }) {
  const navigate = useNavigate();
  return (
    <aside className="app-rail">
      <div className="app-rail-brand">SA</div>
      {MODULE_REGISTRY.map((section) => {
        const hasLiveModule = section.modules.some((m) => m.status === "live");
        const isActive = section.section === activeSection?.section;
        return (
          <button
            key={section.section}
            type="button"
            className={"app-rail-button" + (isActive ? " active" : "") + (hasLiveModule ? "" : " disabled")}
            title={section.section + (hasLiveModule ? "" : " (not built yet)")}
            disabled={!hasLiveModule}
            onClick={() => navigate(firstNavigableModule(section).path)}
          >
            {section.icon}
          </button>
        );
      })}
    </aside>
  );
}

function ModuleTabs({ section }: { section: ModuleSection | undefined }) {
  if (!section) return null;
  return (
    <div className="app-module-tabs">
      <span className="app-module-tabs-label">{section.section}</span>
      {section.modules.map((mod) =>
        mod.status === "live" ? (
          <NavLink
            key={mod.key}
            to={mod.path}
            end={section.modules.some(other => other.path !== mod.path && other.path.startsWith(`${mod.path}/`))}
            className={({ isActive }) => "app-module-tab" + (isActive ? " active" : "")}
          >
            {mod.label}
          </NavLink>
        ) : (
          <span key={mod.key} className="app-module-tab planned" title="Not built yet">
            {mod.label}
          </span>
        )
      )}
    </div>
  );
}

export default function AppShell() {
  const { user, logout } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [theme, setTheme] = useState(getStoredTheme());
  const activeSection = findSectionForPath(location.pathname);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  };

  return (
    <div className="app-shell">
      <ModuleRail activeSection={activeSection} />
      <div className="app-main">
        <header className="app-topbar">
          <CurrentIncident />
          <div className="app-topbar-right">
            <ConnectionIndicator />
            <button className="secondary" style={{ width: "auto" }} onClick={toggleTheme}>
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
            <button className="secondary" style={{ width: "auto" }} onClick={() => navigate("/connection")}>
              Connection
            </button>
            <button className="secondary" style={{ width: "auto" }} onClick={() => navigate("/change-password")}>
              Change Password
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
        <ModuleTabs section={activeSection} />
        <main className="app-content">
          <Outlet />
        </main>
        <footer className="command-version">Web client v{version}</footer>
      </div>
    </div>
  );
}
