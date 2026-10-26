import { version } from "../../package.json";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ChevronRight, LogOut, Settings as SettingsIcon } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { listIncidents } from "../api/endpoints";
import { useSession } from "../auth/SessionContext";
import { useConnectionStatus } from "../realtime/IncidentSocketProvider";
import brandMark from "../assets/branding/arc_horizon_mark.png";
import { findLiveModule, findSectionForPath, MODULE_REGISTRY, type ModuleSection } from "./moduleRegistry";

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

function IncidentChip() {
  const { incidentId } = useSession();
  const { data: incidents = [] } = useQuery({
    queryKey: ["incidents"],
    queryFn: listIncidents,
    staleTime: 60_000,
  });
  const current = incidents.find((i) => i.id === incidentId);
  if (!current) return null;
  return (
    <div className="app-incident-chip">
      <div className="eyebrow">Incident</div>
      <div className="name">
        {current.number} — {current.name}
      </div>
    </div>
  );
}

function BrandPill() {
  return (
    <div className="app-brand-row">
      <div className="app-brand-pill">
        <img className="app-brand-mark" src={brandMark} alt="" />
        <div className="sb-wordmark">
          <span className="title">
            <span className="arc">ARC</span>
            <span className="horizon">HORIZON</span>
          </span>
          <span className="subtitle">Incident Command Assistant</span>
        </div>
      </div>
    </div>
  );
}

function firstNavigableModule(section: ModuleSection) {
  return section.modules.find((m) => m.status === "live") ?? section.modules[0];
}

function NavGroup({
  section,
  isOpen,
  hasActive,
  onToggle,
}: {
  section: ModuleSection;
  isOpen: boolean;
  hasActive: boolean;
  onToggle: () => void;
}) {
  const Icon = section.icon;
  return (
    <div className={"app-nav-group" + (isOpen ? " open" : "") + (hasActive ? " has-active" : "")}>
      <button type="button" className="app-nav-group-btn" onClick={onToggle}>
        <Icon className="icon" />
        <span className="label">{section.section}</span>
        <ChevronRight className="chev" />
      </button>
      <div className="app-nav-children">
        {section.modules.map((mod) =>
          mod.status === "live" ? (
            <NavLink key={mod.key} to={mod.path} className={({ isActive }) => (isActive ? "active" : "")}>
              {mod.label}
            </NavLink>
          ) : (
            <a key={mod.key} className="planned" title="Not built yet">
              {mod.label}
              <span className="soon">Soon</span>
            </a>
          )
        )}
      </div>
    </div>
  );
}

function Sidebar({ activeSection }: { activeSection: ModuleSection | undefined }) {
  const navigate = useNavigate();
  const [openSection, setOpenSection] = useState<string | undefined>(activeSection?.section);

  useEffect(() => {
    if (activeSection) setOpenSection(activeSection.section);
  }, [activeSection?.section]);

  return (
    <aside className="app-sidebar">
      <BrandPill />
      <IncidentChip />
      <nav className="app-nav">
        {MODULE_REGISTRY.map((section) => (
          <NavGroup
            key={section.section}
            section={section}
            isOpen={openSection === section.section}
            hasActive={activeSection?.section === section.section}
            onToggle={() => {
              // Clicking a category opens it and takes the user straight to
              // its dashboard (first live module) — not just an expand/
              // collapse toggle with no destination.
              setOpenSection(section.section);
              const target = firstNavigableModule(section);
              if (target) navigate(target.path);
            }}
          />
        ))}
      </nav>
    </aside>
  );
}

function UserMenu() {
  const { user, logout } = useSession();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [open]);

  const initials = (user?.display_name ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className={"app-usermenu" + (open ? " open" : "")} ref={ref}>
      <button type="button" className="app-usermenu-trigger" onClick={() => setOpen((o) => !o)}>
        <span className="app-usermenu-avatar">{initials}</span>
        <span>{user?.display_name}</span>
      </button>
      <div className="app-usermenu-panel">
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            navigate("/settings");
          }}
        >
          <SettingsIcon size={15} />
          Settings
        </button>
        <div className="divider" />
        <button
          type="button"
          onClick={() => {
            logout();
            navigate("/login");
          }}
        >
          <LogOut size={15} />
          Sign out
        </button>
      </div>
    </div>
  );
}

export default function AppShell() {
  const location = useLocation();
  const activeSection = findSectionForPath(location.pathname);
  const activeModule = findLiveModule(location.pathname);

  return (
    <div className="app-shell">
      <Sidebar activeSection={activeSection} />
      <div className="app-main">
        <header className="app-topbar">
          <div className="app-crumb">
            {activeSection ? <b>{activeSection.section}</b> : <b>SARApp</b>}
            {activeModule && (
              <>
                <span className="sep">/</span>
                {activeModule.label}
              </>
            )}
          </div>
          <div className="app-topbar-right">
            <ConnectionIndicator />
            <UserMenu />
          </div>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
        <footer className="command-version">Web client v{version}</footer>
      </div>
    </div>
  );
}
