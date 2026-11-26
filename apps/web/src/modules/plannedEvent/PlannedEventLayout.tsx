import { NavLink, Outlet } from "react-router-dom";
import "./plannedEvent.css";

const NAV = [
  { to: "/toolkits/planned-event", label: "Overview", end: true },
  { to: "/toolkits/planned-event/schedule", label: "Event schedule", end: false },
  { to: "/toolkits/planned-event/assignments", label: "Assignments", end: false },
  { to: "/toolkits/planned-event/messaging", label: "Messaging", end: false },
  { to: "/toolkits/planned-event/vendors", label: "Vendors", end: false },
  { to: "/toolkits/planned-event/permits", label: "Permits", end: false },
  { to: "/toolkits/planned-event/health", label: "Health", end: false },
];

export default function PlannedEventLayout() {
  return (
    <div className="pe-workspace">
      <header>
        <p className="pe-eyebrow">EVENT PLANNING</p>
        <h2>Planned Event Toolkit</h2>
        <nav className="pe-nav" aria-label="Planned event sections">
          {NAV.map(item => <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? "active" : "")}>{item.label}</NavLink>)}
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
