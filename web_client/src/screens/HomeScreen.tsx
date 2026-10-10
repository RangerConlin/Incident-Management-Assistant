import { useState } from "react";
import { useSession } from "../auth/SessionContext";
import StatusUpdateScreen from "./StatusUpdateScreen";
import AdminCheckInScreen from "./AdminCheckInScreen";
import MessagingScreen from "./MessagingScreen";

type Tab = "primary" | "messages";

export default function HomeScreen() {
  const { checkin, logout } = useSession();
  const isCommand = checkin?.role_on_team === "Command Staff";
  const [tab, setTab] = useState<Tab>("primary");

  return (
    <div className="screen">
      <div className="topbar" style={{ margin: "-24px -16px 16px", padding: "12px 16px" }}>
        <h2 style={{ margin: 0 }}>{isCommand ? "Command" : "Field"}</h2>
        <button className="secondary" onClick={logout}>
          Sign Out
        </button>
      </div>
      <div className="tabs">
        <button className={tab === "primary" ? undefined : "inactive"} onClick={() => setTab("primary")}>
          {isCommand ? "Admin Check-In" : "Status"}
        </button>
        <button className={tab === "messages" ? undefined : "inactive"} onClick={() => setTab("messages")}>
          Messages
        </button>
      </div>
      {tab === "primary" ? isCommand ? <AdminCheckInScreen /> : <StatusUpdateScreen /> : <MessagingScreen />}
    </div>
  );
}
