import { api } from "./client";
import type {
  Incident,
  LoginResponse,
  Meeting,
  MeetingAttendee,
  MeetingChecklistItem,
  MeetingNote,
  MeetingTemplate,
  Objective,
  ObjectiveAuditEntry,
  ObjectiveTaskLink,
  OperationalPeriod,
  PersonnelSummary,
  Sitrep,
  SitrepDistribution,
  SitrepEvent,
  SitrepOperationalSummary,
  TaskDetail,
  TaskRow,
  TaskTeam,
  TeamAssignmentRow,
  TeamDetail,
  WorkAssignment,
  WorkAssignmentResourceAssignment,
  WorkAssignmentResourceRequirement,
  WorkAssignmentTaskLink,
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

export function changePassword(username: string, currentPassword: string, newPassword: string) {
  return api.post<{ status: string; username: string }>("/api/auth/password/change", {
    username,
    current_password: currentPassword,
    new_password: newPassword,
  });
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

// ---------------------------------------------------------------------------
// Planning — Strategic Objectives (ICS-202 style objectives, task linkage,
// audit trail). Backend: data/db/sarapp_db/api/routers/objectives.py, mounted
// at /api/objectives (incident_id is a query param here, not a path segment,
// unlike the operations endpoints above).
// ---------------------------------------------------------------------------

export const OBJECTIVE_STATUSES: { key: string; label: string }[] = [
  { key: "draft", label: "Draft" },
  { key: "active", label: "Active" },
  { key: "deferred", label: "Deferred" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
];

export const OBJECTIVE_PRIORITIES: { key: string; label: string }[] = [
  { key: "low", label: "Low" },
  { key: "normal", label: "Normal" },
  { key: "high", label: "High" },
  { key: "urgent", label: "Urgent" },
];

export function listObjectives(incidentId: string) {
  return api.get<Objective[]>(`/api/objectives?incident_id=${encodeURIComponent(incidentId)}`);
}

export function getObjective(incidentId: string, objectiveId: string) {
  return api.get<Objective>(
    `/api/objectives/${encodeURIComponent(objectiveId)}?incident_id=${encodeURIComponent(incidentId)}`
  );
}

export function createObjective(
  incidentId: string,
  body: { text: string; priority?: string; status?: string; owner_section?: string; due_time?: string; created_by?: string }
) {
  return api.post<Objective>("/api/objectives", { incident_id: incidentId, ...body });
}

export function updateObjective(
  incidentId: string,
  objectiveId: string,
  body: Partial<{
    text: string;
    priority: string;
    status: string;
    owner_section: string;
    tags: string[];
    op_period_id: string;
    narrative: string;
    updated_by: string;
  }>
) {
  return api.patch<Objective>(
    `/api/objectives/${encodeURIComponent(objectiveId)}?incident_id=${encodeURIComponent(incidentId)}`,
    body
  );
}

export function deleteObjective(incidentId: string, objectiveId: string) {
  return api.delete<void>(
    `/api/objectives/${encodeURIComponent(objectiveId)}?incident_id=${encodeURIComponent(incidentId)}`
  );
}

export function reorderObjectives(incidentId: string, ids: string[]) {
  return api.post<{ ok: boolean }>(`/api/objectives/reorder?incident_id=${encodeURIComponent(incidentId)}`, { ids });
}

export function listObjectiveTaskLinks(incidentId: string, objectiveId: string) {
  return api.get<ObjectiveTaskLink[]>(
    `/api/objectives/${encodeURIComponent(objectiveId)}/tasks?incident_id=${encodeURIComponent(incidentId)}`
  );
}

export function linkObjectiveTask(
  incidentId: string,
  objectiveId: string,
  body: { task_id: number; link_type?: string; created_by?: string }
) {
  return api.post<ObjectiveTaskLink>(
    `/api/objectives/${encodeURIComponent(objectiveId)}/tasks?incident_id=${encodeURIComponent(incidentId)}`,
    body
  );
}

export function unlinkObjectiveTask(incidentId: string, objectiveId: string, linkId: number) {
  return api.delete<void>(
    `/api/objectives/${encodeURIComponent(objectiveId)}/tasks/${linkId}?incident_id=${encodeURIComponent(incidentId)}`
  );
}

export function listObjectiveAudit(incidentId: string, objectiveId: string) {
  return api.get<ObjectiveAuditEntry[]>(
    `/api/objectives/${encodeURIComponent(objectiveId)}/audit?incident_id=${encodeURIComponent(incidentId)}`
  );
}

// ---------------------------------------------------------------------------
// Planning — Operational Periods. Backend: operational_periods.py.
// ---------------------------------------------------------------------------

export function listOperationalPeriods(incidentId: string) {
  return api.get<OperationalPeriod[]>(`/api/incidents/${incidentId}/planning/operational-periods`);
}

export function getActiveOperationalPeriod(incidentId: string) {
  return api.get<OperationalPeriod | null>(`/api/incidents/${incidentId}/planning/operational-periods/active`);
}

export function getOperationalPeriod(incidentId: string, periodId: number) {
  return api.get<OperationalPeriod>(`/api/incidents/${incidentId}/planning/operational-periods/${periodId}`);
}

export function createOperationalPeriod(incidentId: string, body: Record<string, unknown>) {
  return api.post<OperationalPeriod>(`/api/incidents/${incidentId}/planning/operational-periods`, body);
}

export function updateOperationalPeriod(incidentId: string, periodId: number, body: Record<string, unknown>) {
  return api.patch<OperationalPeriod>(`/api/incidents/${incidentId}/planning/operational-periods/${periodId}`, body);
}

export function setActiveOperationalPeriod(incidentId: string, periodId: number) {
  return api.post<OperationalPeriod>(
    `/api/incidents/${incidentId}/planning/operational-periods/${periodId}/set-active`
  );
}

export function cloneOperationalPeriod(incidentId: string, periodId: number) {
  return api.post<OperationalPeriod>(`/api/incidents/${incidentId}/planning/operational-periods/${periodId}/clone`);
}

// ---------------------------------------------------------------------------
// Planning — Meetings. Backend: meetings.py.
// ---------------------------------------------------------------------------

export function listMeetingTemplates() {
  return api.get<MeetingTemplate[]>("/api/master/meeting-templates");
}

export function listMeetings(incidentId: string) {
  return api.get<Meeting[]>(`/api/incidents/${incidentId}/planning/meetings`);
}

export function getMeeting(incidentId: string, meetingId: number) {
  return api.get<Meeting>(`/api/incidents/${incidentId}/planning/meetings/${meetingId}`);
}

export function createMeeting(incidentId: string, body: Record<string, unknown>) {
  return api.post<Meeting>(`/api/incidents/${incidentId}/planning/meetings`, body);
}

export function updateMeeting(incidentId: string, meetingId: number, body: Record<string, unknown>) {
  return api.patch<Meeting>(`/api/incidents/${incidentId}/planning/meetings/${meetingId}`, body);
}

export function deleteMeeting(incidentId: string, meetingId: number) {
  return api.delete<void>(`/api/incidents/${incidentId}/planning/meetings/${meetingId}`);
}

export function addMeetingAttendee(incidentId: string, meetingId: number, body: Record<string, unknown>) {
  return api.post<MeetingAttendee>(`/api/incidents/${incidentId}/planning/meetings/${meetingId}/attendees`, body);
}

export function updateMeetingAttendee(
  incidentId: string,
  meetingId: number,
  attendeeId: number,
  body: Record<string, unknown>
) {
  return api.patch<MeetingAttendee>(
    `/api/incidents/${incidentId}/planning/meetings/${meetingId}/attendees/${attendeeId}`,
    body
  );
}

export function removeMeetingAttendee(incidentId: string, meetingId: number, attendeeId: number) {
  return api.delete<void>(`/api/incidents/${incidentId}/planning/meetings/${meetingId}/attendees/${attendeeId}`);
}

export function addMeetingChecklistItem(incidentId: string, meetingId: number, body: Record<string, unknown>) {
  return api.post<MeetingChecklistItem>(`/api/incidents/${incidentId}/planning/meetings/${meetingId}/checklist`, body);
}

export function updateMeetingChecklistItem(
  incidentId: string,
  meetingId: number,
  itemId: number,
  body: Record<string, unknown>
) {
  return api.patch<MeetingChecklistItem>(
    `/api/incidents/${incidentId}/planning/meetings/${meetingId}/checklist/${itemId}`,
    body
  );
}

export function addMeetingNote(incidentId: string, meetingId: number, body: Record<string, unknown>) {
  return api.post<MeetingNote>(`/api/incidents/${incidentId}/planning/meetings/${meetingId}/notes`, body);
}

// ---------------------------------------------------------------------------
// Planning — Situation Reports (ICS-209-style). Backend: sitrep.py.
// ---------------------------------------------------------------------------

export function listSitreps(incidentId: string) {
  return api.get<Sitrep[]>(`/api/incidents/${incidentId}/sitreps`);
}

export function getSitrep(incidentId: string, sitrepId: string) {
  return api.get<Sitrep>(`/api/incidents/${incidentId}/sitreps/${sitrepId}`);
}

export function getSitrepOperationalSummary(incidentId: string) {
  return api.get<SitrepOperationalSummary>(`/api/incidents/${incidentId}/sitreps/operational-summary`);
}

export function createSitrep(incidentId: string, body: Record<string, unknown>) {
  return api.post<Sitrep>(`/api/incidents/${incidentId}/sitreps`, body);
}

export function updateSitrep(incidentId: string, sitrepId: string, body: Record<string, unknown>) {
  return api.patch<Sitrep>(`/api/incidents/${incidentId}/sitreps/${sitrepId}`, body);
}

export function deleteSitrep(incidentId: string, sitrepId: string) {
  return api.delete<void>(`/api/incidents/${incidentId}/sitreps/${sitrepId}`);
}

export function duplicateSitrep(incidentId: string, sitrepId: string, body?: Record<string, unknown>) {
  return api.post<Sitrep>(`/api/incidents/${incidentId}/sitreps/${sitrepId}/duplicate`, body ?? {});
}

export function refreshSitrep(incidentId: string, sitrepId: string) {
  return api.post<Sitrep>(`/api/incidents/${incidentId}/sitreps/${sitrepId}/refresh`);
}

export function listSitrepEvents(incidentId: string, sitrepId?: string) {
  const qs = sitrepId ? `?sitrep_id=${encodeURIComponent(sitrepId)}` : "";
  return api.get<SitrepEvent[]>(`/api/incidents/${incidentId}/sitrep-events${qs}`);
}

export function createSitrepEvent(incidentId: string, body: Record<string, unknown>) {
  return api.post<SitrepEvent>(`/api/incidents/${incidentId}/sitrep-events`, body);
}

export function updateSitrepEvent(incidentId: string, eventId: string, body: Record<string, unknown>) {
  return api.patch<SitrepEvent>(`/api/incidents/${incidentId}/sitrep-events/${eventId}`, body);
}

export function deleteSitrepEvent(incidentId: string, eventId: string) {
  return api.delete<void>(`/api/incidents/${incidentId}/sitrep-events/${eventId}`);
}

export function listSitrepDistributions(incidentId: string, sitrepId: string) {
  return api.get<SitrepDistribution[]>(`/api/incidents/${incidentId}/sitreps/${sitrepId}/distributions`);
}

export function createSitrepDistribution(incidentId: string, sitrepId: string, body: Record<string, unknown>) {
  return api.post<SitrepDistribution>(`/api/incidents/${incidentId}/sitreps/${sitrepId}/distributions`, body);
}

// ---------------------------------------------------------------------------
// Planning — Work Assignments (ICS-215/204 tactics planner). Backend:
// work_assignments.py. hazards/comms/agency-requests/log-entries/outputs
// exist on the backend doc but have no UI here yet (scope cut to keep this
// a real, working slice rather than a half-built everything).
// ---------------------------------------------------------------------------

export const WA_PLANNING_STATUSES = [
  "Draft", "Under Review", "Approved", "Ready for IAP",
  "Assigned to Operations", "In Progress", "Complete", "Cancelled", "Archived",
];
export const WA_SAFETY_STATUSES = [
  "Unchecked", "Needs Review", "Hazards Identified", "Mitigations Complete", "Safety Approved", "Safety Concern",
];
export const WA_RESOURCE_STATUSES = [
  "Unreviewed", "Needs Identified", "Partially Filled", "Filled", "Overfilled", "Gap Exists", "Logistics Requested",
];

export function listWorkAssignments(incidentId: string) {
  return api.get<WorkAssignment[]>(`/api/incidents/${incidentId}/planning/work-assignments`);
}

export function getWorkAssignment(incidentId: string, waId: number) {
  return api.get<WorkAssignment>(`/api/incidents/${incidentId}/planning/work-assignments/${waId}`);
}

export function createWorkAssignment(incidentId: string, body: Record<string, unknown>) {
  return api.post<WorkAssignment>(`/api/incidents/${incidentId}/planning/work-assignments`, body);
}

export function updateWorkAssignment(incidentId: string, waId: number, body: Record<string, unknown>) {
  return api.patch<WorkAssignment>(`/api/incidents/${incidentId}/planning/work-assignments/${waId}`, body);
}

export function archiveWorkAssignment(incidentId: string, waId: number) {
  return api.patch<WorkAssignment>(`/api/incidents/${incidentId}/planning/work-assignments/${waId}/archive`);
}

export function cloneWorkAssignment(incidentId: string, waId: number) {
  return api.post<WorkAssignment>(`/api/incidents/${incidentId}/planning/work-assignments/${waId}/clone`);
}

export function addWorkAssignmentResource(incidentId: string, waId: number, body: Record<string, unknown>) {
  return api.post<WorkAssignmentResourceRequirement>(
    `/api/incidents/${incidentId}/planning/work-assignments/${waId}/resources`,
    body
  );
}

export function removeWorkAssignmentResource(incidentId: string, waId: number, reqId: number) {
  return api.delete<void>(`/api/incidents/${incidentId}/planning/work-assignments/${waId}/resources/${reqId}`);
}

export function assignWorkAssignmentResource(
  incidentId: string,
  waId: number,
  reqId: number,
  body: Record<string, unknown>
) {
  return api.post<WorkAssignmentResourceAssignment>(
    `/api/incidents/${incidentId}/planning/work-assignments/${waId}/resources/${reqId}/assignments`,
    body
  );
}

export function updateWorkAssignmentAssignment(
  incidentId: string,
  waId: number,
  reqId: number,
  assignmentId: number,
  body: Record<string, unknown>
) {
  return api.patch<WorkAssignmentResourceAssignment>(
    `/api/incidents/${incidentId}/planning/work-assignments/${waId}/resources/${reqId}/assignments/${assignmentId}`,
    body
  );
}

export function removeWorkAssignmentAssignment(incidentId: string, waId: number, reqId: number, assignmentId: number) {
  return api.delete<void>(
    `/api/incidents/${incidentId}/planning/work-assignments/${waId}/resources/${reqId}/assignments/${assignmentId}`
  );
}

export function linkWorkAssignmentTask(incidentId: string, waId: number, body: Record<string, unknown>) {
  return api.post<WorkAssignmentTaskLink>(`/api/incidents/${incidentId}/planning/work-assignments/${waId}/task-links`, body);
}

export function unlinkWorkAssignmentTask(incidentId: string, waId: number, linkId: number) {
  return api.delete<void>(`/api/incidents/${incidentId}/planning/work-assignments/${waId}/task-links/${linkId}`);
}
