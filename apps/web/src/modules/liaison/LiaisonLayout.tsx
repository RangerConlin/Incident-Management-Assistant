import { Outlet } from "react-router-dom";
import "./liaison.css";
export default function LiaisonLayout() {
  return <div className="liaison-workspace"><header><p className="liaison-eyebrow">AGENCY COORDINATION</p><h2>Liaison</h2>
    <p>Maintain agency relationships, coordinate requests and offers, and prepare updates for external partners.</p></header>
    <Outlet /></div>;
}
