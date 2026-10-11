import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import KpiStrip from "../../components/KpiStrip";
import StatusPill from "../../components/table/StatusPill";
import { objectiveStatusVar } from "../../styles/statusColors";
import { useSession } from "../../auth/SessionContext";
import { useObjectiveRows } from "./objectives/hooks";

export default function PlanningDashboardPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const { data: rows = [], isLoading } = useObjectiveRows(incidentId!);

  const kpiTiles = useMemo(() => {
    const count = (pred: (o: (typeof rows)[number]) => boolean) => rows.filter(pred).length;
    return [
      { key: "total", value: rows.length, label: "Objectives" },
      { key: "active", value: count((o) => o.status === "active"), label: "Active", accent: objectiveStatusVar("active").bg },
      { key: "draft", value: count((o) => o.status === "draft"), label: "Draft", accent: objectiveStatusVar("draft").bg },
      {
        key: "completed",
        value: count((o) => o.status === "completed"),
        label: "Completed",
        accent: objectiveStatusVar("completed").bg,
      },
    ];
  }, [rows]);

  const upcoming = useMemo(() => {
    return rows
      .filter((o) => o.due_time && o.status !== "completed" && o.status !== "cancelled")
      .sort((a, b) => new Date(a.due_time!).getTime() - new Date(b.due_time!).getTime())
      .slice(0, 5);
  }, [rows]);

  if (!incidentId) return null;

  return (
    <div>
      <h2>Planning</h2>
      <p style={{ opacity: 0.7 }}>Strategic objectives, task tracking, IAP inputs, and planning logs.</p>

      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <>
          <KpiStrip tiles={kpiTiles} />

          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            <button style={{ width: "auto" }} onClick={() => navigate("/planning/objectives")}>
              Open Strategic Objectives
            </button>
          </div>

          <h3>Upcoming Due Dates</h3>
          {upcoming.length === 0 ? (
            <p style={{ opacity: 0.6 }}>No objectives with an upcoming due date.</p>
          ) : (
            upcoming.map((o) => (
              <div
                key={o._id}
                className="list-item"
                onClick={() => navigate(`/planning/objectives/${o._id}`)}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {o.code} — {o.text}
                  </div>
                  <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                    Due {new Date(o.due_time!).toLocaleString()}
                  </div>
                </div>
                <StatusPill domain="objective" statusKey={o.status} />
              </div>
            ))
          )}
        </>
      )}
    </div>
  );
}
