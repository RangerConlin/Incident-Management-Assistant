import { api } from "./client";
import type {
  Incident,
  LoginResponse,
  PersonnelSummary,
  TaskDetail,
  TaskRow,
  TaskTeam,
  TeamAssignmentRow,
  TeamDetail,
} from "./types";

export function lookupPerson(personId: string) {
  return api.get<{ status: "found" | "not_found" | "ambiguous"; person: PersonnelSummary | null }>(
    `/api/auth/lookup?person_id=${encodeURIComponent(personId)}`
  );
}

export function registerPerson(personId: string, firstName: string, lastName: string) {
  return api.post<{ status: string; person: PersonnelSummary }>("/api/auth/register", {
    person_id: personId,
    first_name: firstName,
    last_name: lastName,
  });
}

export function setPassword(username: string, password: string) {
  return api.post<{ status: string; username: string }>("/api/auth/password/set", {
    username,
    password,
  });
}

export function login(username: string, password: string) {
  return api.post<LoginResponse>("/api/auth/login", { username, password, device_name: "web" });
}

export function listIncidents() {
  return api.get<Incident[]>("/api/incidents");
}

// ---------------------------------------------------------------------------
// Team status board + team detail
// ---------------------------------------------------------------------------

export function fetchTeamAssignmentRows(incidentId: string) {
  return api.get<TeamAssignmentRow[]>(`/api/incidents/${incidentId}/operations/team-assignment-rows`);
}

export function getTeam(incidentId: string, teamId: number) {
  return api.get<TeamDetail>(`/api/incidents/${incidentId}/operations/teams/${teamId}`);
}

export function createTeam(incidentId: string, body: Partial<TeamDetail>) {
  return api.post<TeamDetail>(`/api/incidents/${incidentId}/operations/teams`, body);
}

export function listTeams(incidentId: string) {
  return api.get<TeamDetail[]>(`/api/incidents/${incidentId}/operations/teams`);
}

export function updateTeam(incidentId: string, teamId: number, body: Record<string, unknown>) {
  return api.patch<TeamDetail>(`/api/incidents/${incidentId}/operations/teams/${teamId}`, body);
}

export function setTeamStatus(incidentId: string, teamId: number, statusKey: string) {
  return api.patch<TeamDetail>(`/api/incidents/${incidentId}/operations/teams/${teamId}/status`, {
    status_key: statusKey,
  });
}

export function resetTeamCommPing(incidentId: string, teamId: number) {
  return api.patch<TeamDetail>(`/api/incidents/${incidentId}/operations/teams/${teamId}/comm-ping`, {});
}

// Team status progression, ascending — mirrors operations.py's
// _TT_STATUS_COL_ORDER (reversed) and TEAM_STATUS_DISPLAY.
export const TEAM_STATUS_STEPS: { key: string; label: string }[] = [
  { key: "assigned", label: "Assigned" },
  { key: "briefed", label: "Briefed" },
  { key: "enroute", label: "En Route" },
  { key: "arrival", label: "On Scene" },
  { key: "find", label: "Find" },
  { key: "complete", label: "Complete" },
  { key: "returning", label: "Returning" },
];

// ---------------------------------------------------------------------------
// Task status board + task detail
// ---------------------------------------------------------------------------

export function fetchTaskRows(incidentId: string) {
  return api.get<TaskRow[]>(`/api/incidents/${incidentId}/operations/task-rows`);
}

export interface TaskAssignmentOption {
  id: number;
  task_id: string;
  title: string;
  status: string;
  priority: string;
  location: string;
}

export function listTasksForAssignment(incidentId: string) {
  return api.get<TaskAssignmentOption[]>(`/api/incidents/${incidentId}/operations/tasks-for-assignment`);
}

export function getTask(incidentId: string, taskId: number) {
  return api.get<TaskDetail>(`/api/incidents/${incidentId}/operations/tasks/${taskId}`);
}

export function createTask(incidentId: string, body: Partial<TaskDetail>) {
  return api.post<TaskDetail>(`/api/incidents/${incidentId}/operations/tasks`, body);
}

export function updateTask(incidentId: string, taskId: number, body: Record<string, unknown>) {
  return api.patch<TaskDetail>(`/api/incidents/${incidentId}/operations/tasks/${taskId}`, body);
}

export function setTaskStatus(incidentId: string, taskId: number, statusKey: string) {
  return api.patch<TaskDetail>(`/api/incidents/${incidentId}/operations/tasks/${taskId}/status`, {
    status_key: statusKey,
  });
}

export function listTaskTeams(incidentId: string, taskId: number) {
  return api.get<TaskTeam[]>(`/api/incidents/${incidentId}/operations/tasks/${taskId}/teams`);
}

export function addTaskTeam(incidentId: string, taskId: number, teamId?: number) {
  return api.post<TaskTeam>(`/api/incidents/${incidentId}/operations/tasks/${taskId}/teams`, {
    team_id: teamId,
  });
}

export function removeTaskTeam(incidentId: string, taskId: number, ttId: number) {
  return api.delete<{ ok: boolean }>(`/api/incidents/${incidentId}/operations/tasks/${taskId}/teams/${ttId}`);
}

export function setTaskTeamPrimary(incidentId: string, taskId: number, ttId: number) {
  return api.patch(`/api/incidents/${incidentId}/operations/tasks/${taskId}/teams/${ttId}/primary`);
}

export function setTaskTeamSortie(incidentId: string, taskId: number, ttId: number, sortieId: string) {
  return api.patch(`/api/incidents/${incidentId}/operations/tasks/${taskId}/teams/${ttId}/sortie`, {
    sortie_id: sortieId,
  });
}

export interface NarrativeEntry {
  id: string;
  task_id: number;
  timestamp: string;
  narrative: string;
  entered_by: string;
  entered_by_display?: string;
  team_num: string | null;
  critical: number;
}

export function listNarratives(incidentId: string, taskId: number) {
  return api.get<NarrativeEntry[]>(`/api/incidents/${incidentId}/narratives?task_id=${taskId}`);
}

export function createNarrative(
  incidentId: string,
  body: { task_id: number; timestamp: string; narrative: string; entered_by?: string; team_num?: string; critical?: 0 | 1 }
) {
  return api.post<NarrativeEntry>(`/api/incidents/${incidentId}/narratives`, body);
}
