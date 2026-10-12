import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../../../api/endpoints";
import StatusPill from "../../../components/table/StatusPill";
import { useSession } from "../../../auth/SessionContext";
import TeamsTab from "./TeamsTab";
import { TASK_STATUS_OPTIONS, useSetTaskStatus, useTaskDetail, useUpdateTask } from "./hooks";

type Tab =
  | "overview"
  | "teams"
  | "assignment"
  | "safety"
  | "communications"
  | "debriefing"
  | "attachments"
  | "intel"
  | "log"
  | "planning";

const STUB_TABS: { key: Tab; label: string; stub: string }[] = [
  { key: "assignment", label: "Assignment Details", stub: "Coming with the Forms module (ICS204/CAPF109/SAR104)." },
  { key: "safety", label: "Safety", stub: "Coming with the Safety module." },
  { key: "communications", label: "Communications", stub: "Coming with the Communications module." },
  { key: "debriefing", label: "Debriefing", stub: "Coming with the Forms module." },
  { key: "attachments", label: "Attachments", stub: "Coming with the Forms module." },
  { key: "intel", label: "Intel", stub: "Coming with the Intel module." },
  { key: "log", label: "Log", stub: "Coming with the ICS-214 module." },
  { key: "planning", label: "Planning", stub: "Coming with the Planning module." },
];

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "teams", label: "Teams" },
  ...STUB_TABS,
];

export default function TaskDetailPage() {
  const { taskId } = useParams();
  const { incidentId, user, personnel } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [narrativeDraft, setNarrativeDraft] = useState("");

  const id = Number(taskId);
  const { data: task, isLoading, error } = useTaskDetail(incidentId!, id);
  const updateTask = useUpdateTask(incidentId!);
  const setStatus = useSetTaskStatus(incidentId!);

  const { data: narratives = [], refetch: refetchNarratives } = useQuery({
    queryKey: ["incident", incidentId, "tasks", id, "narratives"],
    queryFn: () => api.listNarratives(incidentId!, id),
    enabled: Boolean(incidentId),
  });

  if (!incidentId) return null;
  if (isLoading) return <p>Loading task…</p>;
  if (error || !task) return <p className="error">Could not load this task.</p>;

  const save = (body: Record<string, unknown>) => updateTask.mutate({ taskId: id, body });

  const primaryTeam = task.task_teams.find((tt) => tt.is_primary);

  const submitNarrative = async () => {
    if (!narrativeDraft.trim()) return;
    await api.createNarrative(incidentId, {
      task_id: id,
      timestamp: new Date().toISOString(),
      narrative: narrativeDraft.trim(),
      entered_by: String(personnel?.person_record ?? user?.user_id ?? ""),
    });
    setNarrativeDraft("");
    refetchNarratives();
  };

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/ops/tasks")}>
        ← Task Status Board
      </button>
      <h2>
        {task.task_id} — {task.title}
      </h2>

      <div className="detail-tabs">
        {TABS.map((t) => {
          const stub = STUB_TABS.find((s) => s.key === t.key)?.stub;
          return (
            <button
              key={t.key}
              className={`detail-tab ${tab === t.key ? "active" : ""} ${stub ? "disabled" : ""}`}
              disabled={Boolean(stub)}
              title={stub}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "overview" && (
        <>
          <div className="detail-header">
            <div className="field">
              <label>Category</label>
              <input defaultValue={task.category ?? ""} onBlur={(e) => save({ category: e.target.value })} />
            </div>
            <div className="field">
              <label>Type</label>
              <input defaultValue={task.task_type ?? ""} onBlur={(e) => save({ task_type: e.target.value })} />
            </div>
            <div className="field">
              <label>Priority</label>
              <input defaultValue={task.priority ?? ""} onBlur={(e) => save({ priority: e.target.value })} />
            </div>
            <div className="field">
              <label>Status</label>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <StatusPill domain="task" statusKey={task.status.toLowerCase()} />
                <select
                  value=""
                  onChange={(e) => e.target.value && setStatus.mutate({ taskId: id, statusKey: e.target.value })}
                >
                  <option value="">Change status…</option>
                  {TASK_STATUS_OPTIONS.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="field">
              <label>Task ID</label>
              <input value={task.task_id} readOnly />
            </div>
            <div className="field">
              <label>Primary Team</label>
              <input value={primaryTeam?.team_name ?? "None assigned"} readOnly />
            </div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>Title</label>
              <input defaultValue={task.title} onBlur={(e) => save({ title: e.target.value })} />
            </div>
            <div className="field">
              <label>Location</label>
              <input defaultValue={task.location ?? ""} onBlur={(e) => save({ location: e.target.value })} />
            </div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label>Assignment</label>
              <textarea defaultValue={task.assignment ?? ""} onBlur={(e) => save({ assignment: e.target.value })} />
            </div>
          </div>

          <h3>Narrative</h3>
          <div className="field" style={{ flexDirection: "row", gap: 8 }}>
            <input
              placeholder="Add a narrative entry…"
              value={narrativeDraft}
              onChange={(e) => setNarrativeDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitNarrative()}
            />
            <button style={{ width: "auto" }} disabled={!narrativeDraft.trim()} onClick={submitNarrative}>
              Add
            </button>
          </div>
          <div className="message-list" style={{ maxHeight: 220 }}>
            {narratives.slice(0, 10).map((n) => (
              <div key={n.id} className="message">
                <div className="meta">
                  {n.entered_by_display || n.entered_by} · {new Date(n.timestamp).toLocaleString()}
                </div>
                {n.narrative}
              </div>
            ))}
            {narratives.length === 0 && <p style={{ opacity: 0.6 }}>No narrative entries yet.</p>}
          </div>
        </>
      )}

      {tab === "teams" && <TeamsTab incidentId={incidentId} task={task} />}

      {STUB_TABS.some((s) => s.key === tab) && (
        <p className="detail-tab-placeholder">{STUB_TABS.find((s) => s.key === tab)?.stub}</p>
      )}
    </div>
  );
}
