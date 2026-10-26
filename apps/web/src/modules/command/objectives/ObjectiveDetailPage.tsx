import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { OBJECTIVE_PRIORITIES, OBJECTIVE_STATUSES } from "../../../api/endpoints";
import { useSession } from "../../../auth/SessionContext";
import {
  useLinkObjectiveTask,
  useObjectiveDetail,
  useUnlinkObjectiveTask,
  useUpdateObjective,
} from "./hooks";

type Tab = "overview" | "tasks" | "audit";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "tasks", label: "Linked Tasks" },
  { key: "audit", label: "Audit Trail" },
];

export default function ObjectiveDetailPage() {
  const { objectiveId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [taskIdInput, setTaskIdInput] = useState("");

  const id = objectiveId!;
  const { data: objective, isLoading, error } = useObjectiveDetail(incidentId!, id);
  const updateObjective = useUpdateObjective(incidentId!);
  const linkTask = useLinkObjectiveTask(incidentId!, id);
  const unlinkTask = useUnlinkObjectiveTask(incidentId!, id);

  if (!incidentId) return null;
  if (isLoading) return <p>Loading objective…</p>;
  if (error || !objective) return <p className="error">Could not load this objective.</p>;

  const save = (body: Record<string, unknown>) =>
    updateObjective.mutate({ objectiveId: id, body: { ...body, updated_by: user?.username } });

  return (
    <div className="detail-page">
      <button
        className="secondary"
        style={{ width: "auto", marginBottom: 12 }}
        onClick={() => navigate("/command/objectives")}
      >
        ← Incident Objectives
      </button>
      <h2>
        {objective.code} — {objective.text}
      </h2>

      <div className="detail-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`detail-tab ${tab === t.key ? "active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="detail-header">
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="objective-text-field">Objective</label>
            <textarea
              id="objective-text-field"
              defaultValue={objective.text}
              onBlur={(e) => e.target.value !== objective.text && save({ text: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Status</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <StatusPill domain="objective" statusKey={objective.status} />
              <select value={objective.status} onChange={(e) => save({ status: e.target.value })}>
                {OBJECTIVE_STATUSES.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Priority</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <StatusPill domain="objective-priority" statusKey={objective.priority} />
              <select value={objective.priority} onChange={(e) => save({ priority: e.target.value })}>
                {OBJECTIVE_PRIORITIES.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="objective-owner-field">Owner Section</label>
            <input
              id="objective-owner-field"
              defaultValue={objective.owner_section ?? ""}
              onBlur={(e) => save({ owner_section: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Tasks</label>
            <input value={`${objective.open_tasks} open / ${objective.total_tasks} total`} readOnly />
          </div>
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="objective-narrative-field">Narrative</label>
            <textarea
              id="objective-narrative-field"
              defaultValue={objective.narrative ?? ""}
              placeholder="Progress notes, context, rationale…"
              onBlur={(e) => save({ narrative: e.target.value })}
            />
          </div>
        </div>
      )}

      {tab === "tasks" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              style={{ maxWidth: 200 }}
              placeholder="Task ID (numeric)"
              value={taskIdInput}
              onChange={(e) => setTaskIdInput(e.target.value)}
            />
            <button
              style={{ width: "auto" }}
              disabled={!taskIdInput.trim() || linkTask.isPending}
              onClick={() => {
                const taskId = Number(taskIdInput);
                if (!Number.isFinite(taskId)) return;
                linkTask.mutate({ task_id: taskId, created_by: user?.username }, { onSuccess: () => setTaskIdInput("") });
              }}
            >
              Link Task
            </button>
          </div>
          {objective.task_links.length === 0 ? (
            <p style={{ opacity: 0.6 }}>No tasks linked to this objective yet.</p>
          ) : (
            objective.task_links.map((link) => (
              <div key={link.id} className="list-item" style={{ cursor: "default" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    <a href={`#/ops/tasks/${link.task_id}`}>Task #{link.task_id}</a>
                  </div>
                  <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                    {link.link_type} · linked {new Date(link.created_at).toLocaleString()}
                  </div>
                </div>
                <button className="secondary" style={{ width: "auto" }} onClick={() => unlinkTask.mutate(link.id)}>
                  Unlink
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "audit" && (
        <div>
          {objective.audit.length === 0 ? (
            <p style={{ opacity: 0.6 }}>No audit entries yet.</p>
          ) : (
            objective.audit
              .slice()
              .reverse()
              .map((entry, i) => (
                <div key={i} className="list-item" style={{ cursor: "default" }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>
                      {entry.action}
                      {entry.field ? ` — ${entry.field}` : ""}
                    </div>
                    <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                      {new Date(entry.ts).toLocaleString()} · {entry.user_id ?? "unknown"}
                      {entry.field ? ` · ${String(entry.old_value)} → ${String(entry.new_value)}` : ""}
                    </div>
                  </div>
                </div>
              ))
          )}
        </div>
      )}
    </div>
  );
}
