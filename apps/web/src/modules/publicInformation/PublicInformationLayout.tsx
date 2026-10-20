import { NavLink, Outlet } from "react-router-dom";
import "./publicInformation.css";
export default function PublicInformationLayout() {
  return <div className="pio-workspace"><header><p className="pio-eyebrow">PUBLIC AFFAIRS</p><h2>Public Information</h2>
    <p>Prepare incident messaging, coordinate media responses, and maintain the public release record.</p></header>
    <nav className="pio-nav" aria-label="Public Information workspaces">
      {[["", "Overview"], ["releases", "Messages / releases"], ["media", "Media inquiries"], ["talking-points", "Talking points"], ["misinformation", "Misinformation"], ["templates", "Templates"], ["distribution", "Distribution"]].map(([path, label]) =>
        <NavLink key={path} to={`/pio${path ? `/${path}` : ""}`} end={!path}>{label}</NavLink>)}
    </nav><Outlet /></div>;
}
