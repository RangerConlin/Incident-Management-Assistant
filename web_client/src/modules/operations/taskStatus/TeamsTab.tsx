import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../../../api/endpoints";
import type { TaskDetail } from "../../../api/types";
import { useAddTaskTeam, useRemoveTaskTeam, useSetTaskTeamPrimary, useSetTaskTeamSortie } from "./hooks";

type SubTab = "teams" | "personnel" | "vehicles";

function parseList(json: string): string[] {
  try {
    const parsed = JSON.parse(json || "[]");
    return Array.isArray(parsed) ? parsed.map((v) => String(v)) : [];
  } catch {
    return [];
  }
}

export default function TeamsTab({ incidentId, task }: { incidentId: string; task: TaskDetail }) {
  const navigate = useNavigate();
  const [subTab, setSubTab] = useState<SubTab>("teams");
  const addTeam = useAddTaskTeam(incidentId);
  const removeTeam = useRemoveTaskTeam(incidentId);
  const setPrimary = useSetTaskTeamPrimary(incidentId);
  const setSortie = useSetTaskTeamSortie(incidentId);

  const assignedTeamIds = task.task_teams.map((tt) => tt.team_id);

  const { data: rosterTeams = [] } = useQuery({
    queryKey: ["incident", incidentId, "teams", "roster-for-task", task.int_id],
    queryFn: () => api.listTeams(incidentId),
    enabled: subTab !== "teams",
  });

  const assignedRosterTeams = rosterTeams.filter((t) => assignedTeamIds.includes(t.int_id));
  const personnelRollup = assignedRosterTeams.flatMap((t) => parseList(t.members_json));
  const vehiclesRollup = assignedRosterTeams.flatMap((t) => parseList(t.vehicles_json));

  return (
    <div>
      <div className="tabs">
        <button className={subTab === "teams" ? undefined : "inactive"} onClick={() => setSubTab("teams")}>
          Teams
        </button>
        <button className={subTab === "personnel" ? undefined : "inactive"} onClick={() => setSubTab("personnel")}>
          Personnel
        </button>
        <button className={subTab === "vehicles" ? undefined : "inactive"} onClick={() => setSubTab("vehicles")}>
          Vehicles
        </button>
      </div>

      {subTab === "teams" && (
        <div>
          <button style={{ width: "auto", marginBottom: 12 }} onClick={() => addTeam.mutate({ taskId: task.int_id })}>
            Add New Team
          </button>
          {task.task_teams.length === 0 && <p style={{ opacity: 0.6 }}>No teams assigned yet.</p>}
          {task.task_teams.map((tt) => (
            <div key={tt.id} className="list-item" style={{ cursor: "default" }}>
              <div>
                <strong onClick={() => navigate(`/ops/teams/${tt.team_id}`)} style={{ cursor: "pointer" }}>
                  {tt.team_name}
                </strong>
                {tt.is_primary && <span className="planned-badge" style={{ marginLeft: 8 }}>primary</span>}
                <div style={{ fontSize: "0.8rem", opacity: 0.8 }}>
                  {tt.team_leader} · {tt.team_leader_phone}
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  style={{ width: 90 }}
                  defaultValue={tt.sortie_id ?? ""}
                  placeholder="Sortie #"
                  onBlur={(e) => setSortie.mutate({ taskId: task.int_id, ttId: tt.id, sortieId: e.target.value })}
                />
                {!tt.is_primary && (
                  <button
                    className="secondary"
                    style={{ width: "auto" }}
                    onClick={() => setPrimary.mutate({ taskId: task.int_id, ttId: tt.id })}
                  >
                    Make Primary
                  </button>
                )}
                <button
                  className="danger"
                  style={{ width: "auto" }}
                  onClick={() => removeTeam.mutate({ taskId: task.int_id, ttId: tt.id })}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {subTab === "personnel" && (
        <div>
          <p style={{ opacity: 0.6 }}>Read-only roll-up across this task's assigned teams; edit on each team's own page.</p>
          {personnelRollup.length === 0 && <p>None.</p>}
          {personnelRollup.map((name, i) => (
            <div key={i} className="list-item" style={{ cursor: "default" }}>
              {name}
            </div>
          ))}
        </div>
      )}

      {subTab === "vehicles" && (
        <div>
          <p style={{ opacity: 0.6 }}>Read-only roll-up across this task's assigned teams; edit on each team's own page.</p>
          {vehiclesRollup.length === 0 && <p>None.</p>}
          {vehiclesRollup.map((v, i) => (
            <div key={i} className="list-item" style={{ cursor: "default" }}>
              {v}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
