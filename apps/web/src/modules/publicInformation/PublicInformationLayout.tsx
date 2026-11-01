import { Outlet } from "react-router-dom";
import "./publicInformation.css";
export default function PublicInformationLayout() {
  return <div className="pio-workspace"><header><p className="pio-eyebrow">PUBLIC AFFAIRS</p><h2>Public Information</h2>
    <p>Prepare incident messaging, coordinate media responses, and maintain the public release record.</p></header>
    <Outlet /></div>;
}
