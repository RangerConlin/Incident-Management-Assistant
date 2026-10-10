import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { TEAM_STATUS_STEPS } from "../../../api/endpoints";
import { useSession } from "../../../auth/SessionContext";
import ReferenceListEditor from "./ReferenceListEditor";
import TaskPickerDialog from "./TaskPickerDialog";
import {
  TEAM_STATUS_OTHER,
  useAssignTeamToTask,
  useSetTeamStatus,
  useTeamDetail,
  useUpdateTeam,
} from "./hooks";

type Tab = "overview" | "personnel" | "vehicles" | "equipment" | "logistics" | "logs" | "safety";

const TABS: { key: Tab; label: string; stub?: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "personnel", label: "Personnel" },
  { key: "vehicles", label: "Vehicles" },
  { key: "equipment", label: "Equipment" },
  { key: "logistics", label: "Logistics" },
  { key: "logs", label: "Logs", stub: "Coming with the ICS-214 module." },
  { key: "safety", label: "Safety", stub: "Coming with the Safety module." },
];

export default function TeamDetailPage() {
  const { teamId } = useParams();
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [showTaskPicker, setShowTaskPicker] = useState(false);

  const id = Number(teamId);
  const { data: team, isLoading, error } = useTeamDetail(incidentId!, id);
  const updateTeam = useUpdateTeam(incidentId!);
  const setStatus = useSetTeamStatus(incidentId!);
  const assignToTask = useAssignTeamToTask(incidentId!);

  if (!incidentId) return null;
  if (isLoading) return <p>Loading team…</p>;
  if (error || !team) return <p className="error">Could not load this team.</p>;

  const save = (body: Record<string, unknown>) => updateTeam.mutate({ teamId: id, body });

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/ops/teams")}>
        ← Team Status Board
      </button>
      <h2>{team.name || `Team ${team.int_id}`}</h2>

      <div className="detail-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`detail-tab ${tab === t.key ? "active" : ""} ${t.stub ? "disabled" : ""}`}
            disabled={Boolean(t.stub)}
            title={t.stub}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="detail-header">
          <div className="field">
            <label>Team Type</label>
            <input defaultValue={team.team_type ?? ""} onBlur={(e) => save({ team_type: e.target.value })} />
          </div>
          <div className="field">
            <label>Team Name</label>
            <input defaultValue={team.name ?? ""} onBlur={(e) => save({ name: e.target.value })} />
          </div>
          <div className="field">
            <label>Team Leader</label>
            <input value={team.leader_name ?? ""} readOnly />
          </div>
          <div className="field">
            <label>Phone</label>
            <input value={team.leader_phone ?? team.phone ?? ""} readOnly />
          </div>
          <div className="field">
            <label>Status</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <StatusPill domain="team" statusKey={team.status} />
              <select
                value=""
                onChange={(e) => {
                  const key = e.target.value;
                  if (!key) return;
                  if (team.current_task_id == null && TEAM_STATUS_STEPS.some((s) => s.key === key)) {
                    setShowTaskPicker(true);
                    return;
                  }
                  setStatus.mutate({ teamId: id, statusKey: key });
                }}
              >
                <option value="">Change status…</option>
                {[...TEAM_STATUS_STEPS, ...TEAM_STATUS_OTHER].map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Linked Task</label>
            {team.current_task_id != null ? (
              <div style={{ display: "flex", gap: 8 }}>
                <button style={{ width: "auto" }} onClick={() => navigate(`/ops/tasks/${team.current_task_id}`)}>
                  View Task {team.current_task_id}
                </button>
                <button className="secondary" style={{ width: "auto" }} onClick={() => save({ current_task_id: null })}>
                  Unlink
                </button>
              </div>
            ) : (
              <button style={{ width: "auto" }} onClick={() => setShowTaskPicker(true)}>
                Link Task…
              </button>
            )}
          </div>
          <div className="field">
            <label>Location</label>
            <input defaultValue={team.location ?? ""} onBlur={(e) => save({ location: e.target.value })} />
          </div>
          <div className="field">
            <label>Notes</label>
            <textarea defaultValue={team.notes ?? ""} onBlur={(e) => save({ notes: e.target.value })} />
          </div>
          <div className="field">
            <label>Needs Assistance</label>
            <button
              className={team.needs_attention ? "danger" : "secondary"}
              style={{ width: "auto" }}
              onClick={() => save({ needs_attention: !team.needs_attention })}
            >
              {team.needs_attention ? "Clear Needs Assistance" : "Flag Needs Assistance"}
            </button>
          </div>
        </div>
      )}

      {tab === "personnel" && (
        <ReferenceListEditor
          label="Personnel"
          jsonValue={team.members_json}
          onSave={(v) => save({ members_json: v })}
        />
      )}
      {tab === "vehicles" && (
        <ReferenceListEditor
          label="Vehicles"
          jsonValue={team.vehicles_json}
          onSave={(v) => save({ vehicles_json: v })}
        />
      )}
      {tab === "equipment" && (
        <ReferenceListEditor
          label="Equipment"
          jsonValue={team.equipment_json}
          onSave={(v) => save({ equipment_json: v })}
        />
      )}
      {tab === "logistics" && (
        <div>
          <p>
            Check-in status: <strong>{team.ci_status}</strong>
          </p>
          <p style={{ opacity: 0.6 }}>Resource request linking coming soon.</p>
        </div>
      )}
      {(tab === "logs" || tab === "safety") && (
        <p className="detail-tab-placeholder">{TABS.find((t) => t.key === tab)?.stub}</p>
      )}

      {showTaskPicker && (
        <TaskPickerDialog
          incidentId={incidentId}
          onCancel={() => setShowTaskPicker(false)}
          onPick={(taskId) => {
            assignToTask.mutate({ taskId, teamId: id });
            setShowTaskPicker(false);
          }}
        />
      )}
    </div>
  );
}
