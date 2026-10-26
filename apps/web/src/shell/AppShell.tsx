import { version } from "../../package.json";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Bell, ChevronRight, LogOut, MessageSquare, Settings as SettingsIcon } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  acknowledgeNotification,
  chatSummary,
  dismissNotification,
  listIncidents,
  listNotifications,
  markChatChannelRead,
} from "../api/endpoints";
import { useSession } from "../auth/SessionContext";
import { useConnectionStatus } from "../realtime/IncidentSocketProvider";
import brandMark from "../assets/branding/arc_horizon_mark.png";
import { findLiveModule, findSectionForPath, MODULE_REGISTRY, type ModuleSection } from "./moduleRegistry";
import type { ChatChannelSummary, IncidentNotification } from "../api/types";

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

function formatClock(date: Date, timeZone?: string) {
  return date.toLocaleTimeString("en-US", {
    timeZone,
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function HeaderClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="app-header-clock" title="Local and UTC time">
      <span className="app-header-clock-item">
        <span className="zone">LOCAL</span>
        <span className="time">{formatClock(now)}</span>
      </span>
      <span className="app-header-clock-item">
        <span className="zone">UTC</span>
        <span className="time">{formatClock(now, "UTC")}</span>
      </span>
    </div>
  );
}

function formatHeaderTimestamp(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  return sameDay
    ? date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function useDropdown() {
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

  return { open, setOpen, ref };
}

function NotificationsMenu() {
  const { incidentId, personnel } = useSession();
  const queryClient = useQueryClient();
  const { open, setOpen, ref } = useDropdown();
  const personRecord = personnel?.person_record ?? null;

  const query = useQuery({
    queryKey: ["incident", incidentId, "notifications", "unread", personRecord],
    queryFn: () => listNotifications(incidentId!, personRecord!, true),
    enabled: Boolean(incidentId && personRecord),
    refetchInterval: 20_000,
  });
  const items = query.data ?? [];

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "notifications"] });

  const act = (fn: (incidentId: string, notificationId: number) => Promise<IncidentNotification>, notificationId: number) => {
    if (!incidentId) return;
    fn(incidentId, notificationId).then(invalidate);
  };

  return (
    <div className={"app-headermenu" + (open ? " open" : "")} ref={ref}>
      <button
        type="button"
        className="app-icon-btn"
        title="Notifications"
        aria-label={`${items.length} unread notifications`}
        onClick={() => setOpen((o) => !o)}
      >
        <Bell size={17} />
        {items.length > 0 && <span className="notification-badge">{items.length > 99 ? "99+" : items.length}</span>}
      </button>
      <div className="app-headermenu-panel">
        <div className="app-headermenu-title">Notifications</div>
        {items.length === 0 ? (
          <div className="app-headermenu-empty">You're all caught up.</div>
        ) : (
          <div className="app-headermenu-list">
            {items.map((n) => (
              <div key={n.notification_id} className={`app-headermenu-item severity-${n.severity}`}>
                <div className="app-headermenu-item-main">
                  <div className="app-headermenu-item-title">{n.title}</div>
                  <div className="app-headermenu-item-body">{n.message}</div>
                  <div className="app-headermenu-item-meta">
                    {n.source_label ?? n.category} · {formatHeaderTimestamp(n.created_at)}
                  </div>
                </div>
                <div className="app-headermenu-item-actions">
                  <button type="button" onClick={() => act(acknowledgeNotification, n.notification_id)}>
                    Acknowledge
                  </button>
                  <button type="button" onClick={() => act(dismissNotification, n.notification_id)}>
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function chatChannelLabel(channel: ChatChannelSummary, selfUserId: string | undefined) {
  if (channel.type === "group") return channel.name ?? "Channel";
  const otherId = channel.participant_ids.find((id) => id !== selfUserId);
  return otherId ? `DM: ${otherId}` : channel.name ?? "Direct message";
}

function ChatMenu() {
  const { incidentId, user } = useSession();
  const queryClient = useQueryClient();
  const { open, setOpen, ref } = useDropdown();

  const query = useQuery({
    queryKey: ["incident", incidentId, "messages", "chat-summary", user?.user_id],
    queryFn: () => chatSummary(incidentId!, user!.user_id),
    enabled: Boolean(incidentId && user?.user_id),
    refetchInterval: 20_000,
  });
  const channels = query.data?.items ?? [];
  const totalUnread = channels.reduce((sum, c) => sum + c.unread_count, 0);

  const openChannel = (channel: ChatChannelSummary) => {
    if (!incidentId || !user?.user_id || channel.unread_count === 0) return;
    markChatChannelRead(incidentId, channel.channel_id, user.user_id).then(() =>
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "messages"] })
    );
  };

  return (
    <div className={"app-headermenu" + (open ? " open" : "")} ref={ref}>
      <button
        type="button"
        className="app-icon-btn"
        title="Chat"
        aria-label={`${totalUnread} unread chat messages`}
        onClick={() => setOpen((o) => !o)}
      >
        <MessageSquare size={17} />
        {totalUnread > 0 && <span className="notification-badge">{totalUnread > 99 ? "99+" : totalUnread}</span>}
      </button>
      <div className="app-headermenu-panel">
        <div className="app-headermenu-title">Chat</div>
        {channels.length === 0 ? (
          <div className="app-headermenu-empty">No channels yet.</div>
        ) : (
          <div className="app-headermenu-list">
            {channels.map((c) => (
              <button
                type="button"
                key={c.channel_id}
                className={"app-headermenu-item app-headermenu-item-clickable" + (c.unread_count > 0 ? " unread" : "")}
                onClick={() => openChannel(c)}
              >
                <div className="app-headermenu-item-main">
                  <div className="app-headermenu-item-title">{chatChannelLabel(c, user?.user_id)}</div>
                  <div className="app-headermenu-item-body">
                    {c.last_message ? `${c.last_message.sender_name ?? c.last_message.sender_id}: ${c.last_message.text}` : "No messages yet"}
                  </div>
                </div>
                {c.last_message && <div className="app-headermenu-item-meta">{formatHeaderTimestamp(c.last_message.created_at)}</div>}
                {c.unread_count > 0 && <span className="app-headermenu-item-badge">{c.unread_count}</span>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
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
            <NavLink
              key={mod.key}
              to={mod.path}
              // Exact-match only when this module's own path is a prefix of
              // a sibling's (e.g. "/command" vs "/command/overview") —
              // otherwise NavLink's default prefix matching highlights both
              // the dashboard entry and whichever sub-page is actually
              // active. Leaving it off for paths with no such sibling keeps
              // a board link (e.g. "/ops/teams") highlighted on its own
              // detail sub-routes ("/ops/teams/123"), which NavLink doesn't
              // see as a listed module but should still count as active.
              end={section.modules.some((other) => other.path !== mod.path && other.path.startsWith(`${mod.path}/`))}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
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
          <HeaderClock />
          <div className="app-topbar-right">
            <ConnectionIndicator />
            <ChatMenu />
            <NotificationsMenu />
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
