import { api } from "./client";
import type { Dataset, RecordData } from "../modules/workspaces/config";
const datasetUrl=(d:Dataset,id:string)=>d.master?d.endpoint:`/api/incidents/${encodeURIComponent(id)}/${d.endpoint}`;
const recordUrl=(d:Dataset,id:string,rid:string)=>`${datasetUrl(d,id).split("?")[0]}/${encodeURIComponent(rid)}`;

export const listWorkspaceRecords = (d:Dataset,id:string)=>api.get<RecordData[]>(datasetUrl(d,id));
export const saveWorkspaceRecord = (d:Dataset,id:string,rid:string|null,body:RecordData)=>{if(rid===null){if(!d.create)throw new Error("Creation is unavailable for this collection.");return api.post<RecordData>(datasetUrl(d,id).split("?")[0],body);}if(!d.update)throw new Error("Editing is unavailable for this collection.");return api[d.update]<RecordData>(recordUrl(d,id,rid),body);};
export const deleteWorkspaceRecord = (d:Dataset,id:string,rid:string)=>{if(!d.remove)throw new Error("Removal is unavailable for this collection.");return api.delete<void>(recordUrl(d,id,rid));};
export const pendingApprovals=(id:string,p:number)=>api.get<RecordData[]>(`/api/incidents/${encodeURIComponent(id)}/approvals/pending/${p}`);
export const listCertificationTypes=()=>api.get<RecordData[]>("/api/master/certification-types");
export const listPersonCertifications=(p:string)=>api.get<RecordData[]>(`/api/master/certifications/personnel/${encodeURIComponent(p)}`);
export const assignPersonCertification=(p:string,c:string,l:number)=>api.post<RecordData>(`/api/master/certifications/personnel/${encodeURIComponent(p)}/${encodeURIComponent(c)}`,{level:l});
export const removePersonCertification=(p:string,c:string)=>api.delete<void>(`/api/master/certifications/personnel/${encodeURIComponent(p)}/${encodeURIComponent(c)}`);
export const getWeatherConfig=(id:string)=>api.get<WeatherConfig>(`/api/incidents/${encodeURIComponent(id)}/weather/config`);
export const updateWeatherConfig=(id:string,b:Record<string,unknown>)=>api.put<WeatherConfig>(`/api/incidents/${encodeURIComponent(id)}/weather/config`,b);
export const addWeatherLocation=(id:string,b:RecordData)=>api.post<RecordData>(`/api/incidents/${encodeURIComponent(id)}/weather/locations`,b);
export const removeWeatherLocation=(id:string,l:string)=>api.delete<RecordData>(`/api/incidents/${encodeURIComponent(id)}/weather/locations/${encodeURIComponent(l)}`);
export const setWeatherDefault=(id:string,l:string)=>api.patch<RecordData>(`/api/incidents/${encodeURIComponent(id)}/weather/locations/${encodeURIComponent(l)}/default`,{});
export const weatherHistory=(id:string,l:string)=>api.get<{samples:RecordData[]}>(`/api/incidents/${encodeURIComponent(id)}/weather/history?location_id=${encodeURIComponent(l)}`);
import type {
  ChannelsPlanValidation,
  CheckinRosterRow,
  CheckinTeamRow,
  CheckinHistoryItem,
  CommsContact,
  CommsLogEntry,
  CommunicationsPlan,
  ApprovalInstance,
  ApprovalPreviewRow,
  Incident,
  IncidentNotification,
  ChatChannelSummary,
  FormExportDefinition,
  FormExportRequest,
  IncidentChannel,
  MasterChannel,
  ResourceRequest,
  ResourceRequestDetail,
  RequestItem,
  Facility,
  LiaisonRecord,
  LiaisonRequest,
  LiaisonAgencyDetail,
  MasterAircraft,
  MasterEquipment,
  MasterPersonnelSummary,
  MasterVehicle,
  PioMessage,
  PioApproval,
  PioRecord,
  PioTimelineEvent,
  LoginResponse,
  CapOrmForm,
  CapOrmHazard,
  Hazard,
  Ics208,
  IwiReport,
  WeatherConfig,
  MedicalPlan,
  MedicalPlanAidStation,
  MedicalPlanTable,
  MedicalPlanVersionSummary,
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
  ResourceStatusRow,
  Sitrep,
  SitrepDistribution,
  SitrepEvent,
  SitrepOperationalSummary,
  TaskDetail,
  TaskRow,
  TaskTeam,
  TaskWorkAssignmentLink,
  TeamAssignmentRow,
  TeamDetail,
  WorkAssignment,
  WorkAssignmentResourceAssignment,
  WorkAssignmentResourceRequirement,
  WorkAssignmentTaskLink,
  IncidentProfile, OrgAssignment, OrgPosition, OrgTemplate, IapPackage,
  TeamTypeDefinition, ResourceType, SpatialFeature,
  IntelSubject, IntelLead, IntelItem, IntelAssessment, IntelLogEntry, IntelDashboard,
} from "./types";

export function lookupPerson(personId: string) {
  return api.get<{ status: "found" | "not_found" | "ambiguous"; person: PersonnelSummary | null }>(
    `/api/auth/lookup?person_id=${encodeURIComponent(personId)}`
  );
}

const commandBase=(id:string)=>`/api/incidents/${encodeURIComponent(id)}`;
export const getIncidentProfile=(id:string)=>api.get<IncidentProfile>(`${commandBase(id)}/profile`);
export const updateIncidentProfile=(id:string,b:Record<string,unknown>)=>api.patch<IncidentProfile>(`${commandBase(id)}/profile`,b);
export const listOrgPositions=(id:string)=>api.get<OrgPosition[]>(`${commandBase(id)}/org/positions`);
export const saveOrgPosition=(id:string,b:Record<string,unknown>)=>api.post<{position_id:number}>(`${commandBase(id)}/org/positions`,b);
export const deleteOrgPosition=(id:string,p:number)=>api.delete<{ok:boolean}>(`${commandBase(id)}/org/positions/${p}`);
export const moveOrgPosition=(id:string,p:number,parentPositionId:number|null)=>api.patch<{ok:boolean}>(`${commandBase(id)}/org/positions/${p}/move`,{parent_position_id:parentPositionId});
export const listOrgAssignments=(id:string)=>api.get<OrgAssignment[]>(`${commandBase(id)}/org/assignments`);
export const addOrgAssignment=(id:string,b:Record<string,unknown>)=>api.post<{assignment_id:string}>(`${commandBase(id)}/org/assignments`,b);
export const endOrgAssignment=(id:string,a:string)=>api.patch<{ok:boolean}>(`${commandBase(id)}/org/assignments/${encodeURIComponent(a)}/end`,{});
export const listOrgTemplates=(id:string)=>api.get<OrgTemplate[]>(`${commandBase(id)}/org/templates`);
export const applyOrgTemplate=(id:string,payload:Record<string,unknown>[])=>api.post<number[]>(`${commandBase(id)}/org/templates/apply`,{payload});
export const listIapPackages=(id:string)=>api.get<IapPackage[]>(`${commandBase(id)}/iap/packages`);
export const getIapPackage=(id:string,op:number)=>api.get<IapPackage>(`${commandBase(id)}/iap/packages/${op}`);
export const saveIapPackage=(id:string,op:number,b:Record<string,unknown>)=>api.put<IapPackage>(`${commandBase(id)}/iap/packages/${op}`,b);
export const saveIapForm=(id:string,op:number,f:string,b:Record<string,unknown>)=>api.put<IapPackage>(`${commandBase(id)}/iap/packages/${op}/forms/${encodeURIComponent(f)}`,b);
export const deleteIapForm=(id:string,op:number,f:string)=>api.delete<void>(`${commandBase(id)}/iap/packages/${op}/forms/${encodeURIComponent(f)}`);
export const orderIapForms=(id:string,op:number,order:string[])=>api.put<IapPackage>(`${commandBase(id)}/iap/packages/${op}/forms-order`,{order});

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

export function listTeamTypes() {
  return api.get<TeamTypeDefinition[]>("/api/lookup/team-types");
}

export function listResourceTypes() {
  return api.get<ResourceType[]>("/api/resource-types");
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
// audit trail). Backend: server/sarapp_db/sarapp_db/api/routers/objectives.py, mounted
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

export function listWorkAssignmentsForTask(incidentId: string, taskId: number) {
  return api.get<TaskWorkAssignmentLink[]>(`/api/incidents/${incidentId}/planning/tasks/${taskId}/work-assignments`);
}

// Public Information / PAO
const pioBase = (incidentId: string) => `/api/incidents/${encodeURIComponent(incidentId)}/public-information`;
export const listPioMessages = (id: string) => api.get<PioMessage[]>(`${pioBase(id)}/messages`);
export const getPioMessage = (id: string, messageId: number) => api.get<PioMessage>(`${pioBase(id)}/messages/${messageId}`);
export const savePioMessage = (id: string, body: Record<string, unknown>) => api.post<PioMessage>(`${pioBase(id)}/messages`, body);
export const setPioMessageStatus = (id: string, messageId: number, status: string, user: string, comment: string) =>
  api.post<PioMessage>(`${pioBase(id)}/messages/${messageId}/status`, { status, user, comment });
export const listPioApprovals = (id: string, messageId: number) => api.get<PioApproval[]>(`${pioBase(id)}/messages/${messageId}/approvals`);
export const listPioTemplates = (id: string) => api.get<PioRecord[]>(`${pioBase(id)}/templates`);
export const savePioTemplate = (id: string, body: Record<string, unknown>) => api.post<PioRecord>(`${pioBase(id)}/templates`, body);
export const listPioRecords = (id: string, table: string) => api.get<PioRecord[]>(`${pioBase(id)}/records/${encodeURIComponent(table)}`);
export const savePioRecord = (id: string, table: string, body: Record<string, unknown>) => api.post<PioRecord>(`${pioBase(id)}/records/${encodeURIComponent(table)}`, body);
export const getPioSummary = (id: string) => api.get<Record<string, number | string>>(`${pioBase(id)}/summary`);
export const createPioResponse = (id: string, mediaId: number, user: string) => api.post<PioMessage>(`${pioBase(id)}/media/${mediaId}/response-draft`, { user });
export const listPioTimeline = (id: string, itemId: number) => api.get<PioTimelineEvent[]>(`${pioBase(id)}/misinformation/${itemId}/timeline`);
export const addPioTimeline = (id: string, itemId: number, event_text: string, user: string) => api.post<PioTimelineEvent>(`${pioBase(id)}/misinformation/${itemId}/timeline`, { event_text, user });

// Logistics: Resource Status Board — checked-in personnel/vehicles/aircraft/equipment.
export function listResourceStatus(incidentId: string, resourceType = "") {
  const q = resourceType ? `?resource_type=${encodeURIComponent(resourceType)}` : "";
  return api.get<ResourceStatusRow[]>(`/api/incidents/${incidentId}/resources${q}`);
}

export function getResourceStatus(incidentId: string, resourceType: string, recordId: string | number) {
  return api.get<ResourceStatusRow>(`/api/incidents/${incidentId}/resources/${resourceType}/${recordId}`);
}

export function checkInResource(
  incidentId: string,
  resourceType: string,
  recordId: string | number,
  overrides: Record<string, unknown> = {}
) {
  return api.post<ResourceStatusRow>(`/api/incidents/${incidentId}/resources/${resourceType}/${recordId}`, overrides);
}

export function checkOutResource(incidentId: string, resourceType: string, recordId: string | number) {
  return api.delete<void>(`/api/incidents/${incidentId}/resources/${resourceType}/${recordId}`);
}

export function searchMasterVehicles(search = "") {
  return api.get<MasterVehicle[]>(`/api/master/vehicles?search=${encodeURIComponent(search)}`);
}

export function searchMasterAircraft(search = "") {
  return api.get<MasterAircraft[]>(`/api/master/aircraft?search=${encodeURIComponent(search)}`);
}

export function searchMasterEquipment(search = "") {
  return api.get<MasterEquipment[]>(`/api/master/equipment?search=${encodeURIComponent(search)}`);
}

// Logistics: Check-In — personnel roster + search, backed by the same
// resource_status collection as the board above (entity_type="personnel").
export function fetchCheckinRoster(incidentId: string, params: Record<string, string | boolean> = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== "" && v !== undefined && v !== null) qs.set(k, String(v));
  }
  const q = qs.toString();
  return api.get<CheckinRosterRow[]>(`/api/incidents/${incidentId}/checkin/roster${q ? `?${q}` : ""}`);
}

export function searchCheckinPersonnel(incidentId: string, q = "") {
  return api.get<MasterPersonnelSummary[]>(`/api/incidents/${incidentId}/checkin/personnel/search?q=${encodeURIComponent(q)}`);
}

export function saveCheckin(incidentId: string, personRecord: number, body: Record<string, unknown>) {
  return api.put<Record<string, unknown>>(`/api/incidents/${incidentId}/checkin/${personRecord}`, body);
}

export function setCheckinStatus(incidentId: string, personRecord: number, status: string) {
  return api.patch<Record<string, unknown>>(`/api/incidents/${incidentId}/checkin/${personRecord}/status`, { status });
}

export function patchCheckin(incidentId: string, personRecord: number, body: Record<string, unknown>) {
  return api.patch<Record<string, unknown>>(`/api/incidents/${incidentId}/checkin/${personRecord}`, body);
}

export function listCheckinHistory(incidentId: string, personRecord: number) {
  return api.get<CheckinHistoryItem[]>(`/api/incidents/${incidentId}/checkin/history/${personRecord}`);
}

// Logistics: Check-In — Groups/Teams tab (ICS-211 team check-in/disband).
export function listCheckinTeams(incidentId: string, checkedIn: boolean, includeDisbanded = false) {
  return api.get<CheckinTeamRow[]>(
    `/api/incidents/${incidentId}/checkin/teams/checked-state?checked_in=${checkedIn}&include_disbanded=${includeDisbanded}`
  );
}

export function teamCheckIn(
  incidentId: string,
  teamId: number | string,
  body: { keep_together: boolean; checked_in_by?: string; checkin_notes?: string; status?: string }
) {
  return api.post<Record<string, unknown>>(`/api/incidents/${incidentId}/checkin/teams/${teamId}/checkin`, body);
}

export function teamDisband(incidentId: string, teamId: number | string, body: { disbanded_by?: string } = {}) {
  return api.post<Record<string, unknown>>(`/api/incidents/${incidentId}/checkin/teams/${teamId}/disband`, body);
}

// Logistics: Check-In — status actions (Enroute / Prep Demob / Cancelled)
// on an already-tracked resource_status row, mirrors the desktop ICS-211
// window's use of the resource-status router (a different mount than the
// /resources router the Resource Status Board uses above).
export function getResourceStatusByEntity(incidentId: string, entityType: string, recordId: string | number) {
  return api.get<ResourceStatusRow | null>(
    `/api/incidents/${incidentId}/resource-status/by-entity?entity_type=${encodeURIComponent(entityType)}&record_id=${encodeURIComponent(String(recordId))}`
  );
}

export function setResourceStatusStatus(incidentId: string, itemId: string, status: string) {
  return api.patch<ResourceStatusRow>(`/api/incidents/${incidentId}/resource-status/${itemId}/status`, {
    status,
    changed_by: "Check-In",
  });
}

// Logistics: Check-In — "Add New Record" (master catalog create).
export function createMasterPersonnel(body: Record<string, unknown>) {
  return api.post<MasterPersonnelSummary>(`/api/master/personnel`, body);
}
export function createMasterVehicle(body: Record<string, unknown>) {
  return api.post<MasterVehicle>(`/api/master/vehicles`, body);
}
export function createMasterAircraft(body: Record<string, unknown>) {
  return api.post<MasterAircraft>(`/api/master/aircraft`, body);
}
export function createMasterEquipment(body: Record<string, unknown>) {
  return api.post<MasterEquipment>(`/api/master/equipment`, body);
}

// Liaison coordination uses the shared API; only supported write paths are exposed.
export type LiaisonSection = "agencies" | "requests" | "reporting-digests" | "interactions";
const liaisonBase = (id: string) => `/api/incidents/${encodeURIComponent(id)}/liaison`;
export const listLiaisonRecords = (id: string, section: LiaisonSection) => api.get<LiaisonRecord[]>(`${liaisonBase(id)}/${section}`);
export const createLiaisonRecord = (id: string, section: LiaisonSection, body: Record<string, unknown>) => api.post<LiaisonRecord>(`${liaisonBase(id)}/${section}`, body);
export const updateLiaisonRecord = (id: string, section: Exclude<LiaisonSection, "interactions">, recordId: number, body: Record<string, unknown>) => api.patch<LiaisonRecord>(`${liaisonBase(id)}/${section}/${recordId}`, body);
export const deleteLiaisonRecord = (id: string, section: "requests" | "reporting-digests", recordId: number) => api.delete<void>(`${liaisonBase(id)}/${section}/${recordId}`);
export const getLiaisonAgencyDetail = (id: string, agencyId: number) => api.get<LiaisonAgencyDetail>(`${liaisonBase(id)}/agencies/${agencyId}/detail`);
export const createLiaisonContact = (id: string, agencyId: number, body: Record<string, unknown>) => api.post<LiaisonRecord>(`${liaisonBase(id)}/agencies/${agencyId}/contacts`, body);
export const addLiaisonNarrative = (id: string, requestId: number, body: { text: string; category: string; author: string }) => api.post<LiaisonRequest>(`${liaisonBase(id)}/requests/${requestId}/narrative`, body);
export const listLiaisonResourceLinks = (id: string) => api.get<{ id: string; title: string; request_number?: string }[]>(`/api/incidents/${encodeURIComponent(id)}/logistics/resource-requests`);

// Logistics requests and facilities use the existing shared server workflow.
const requestBase = (id: string) => `/api/incidents/${encodeURIComponent(id)}/logistics/resource-requests`;
export const listResourceRequests = (id: string) => api.get<ResourceRequest[]>(requestBase(id));
export const getResourceRequest = (id: string, requestId: string) => api.get<ResourceRequestDetail>(`${requestBase(id)}/${encodeURIComponent(requestId)}`);
export const createResourceRequest = (id: string, body: Record<string, unknown>) => api.post<ResourceRequestDetail>(requestBase(id), body);
export const updateResourceRequest = (id: string, requestId: string, body: Record<string, unknown>) => api.patch<ResourceRequestDetail>(`${requestBase(id)}/${encodeURIComponent(requestId)}`, body);
export const resourceRequestApproval = (id: string, requestId: string, action: string, actor_id: string, note: string) => api.post<{ id: string }>(`${requestBase(id)}/${encodeURIComponent(requestId)}/approvals`, { action, actor_id, note });
export const resourceRequestStatus = (id: string, requestId: string, status: string, actor_id: string, note: string) => api.post<ResourceRequestDetail>(`${requestBase(id)}/${encodeURIComponent(requestId)}/status`, { status, actor_id, note });
export const replaceResourceRequestItems = (id: string, requestId: string, items: RequestItem[]) => api.put<{ ids: string[] }>(`${requestBase(id)}/${encodeURIComponent(requestId)}/items`, items);
export const assignResourceRequestFulfillment = (id: string, requestId: string, body: Record<string, unknown>) => api.post<{ id: string }>(`${requestBase(id)}/${encodeURIComponent(requestId)}/fulfillments`, body);
export const updateResourceRequestFulfillment = (id: string, requestId: string, fulfillmentId: string, body: Record<string, unknown>) => api.patch<{ ok: boolean }>(`${requestBase(id)}/${encodeURIComponent(requestId)}/fulfillments/${encodeURIComponent(fulfillmentId)}`, body);
const facilityBase = (id: string) => `/api/incidents/${encodeURIComponent(id)}/facilities`;
export const listFacilities = (id: string) => api.get<Facility[]>(facilityBase(id));
export const getFacility = (id: string, facilityId: string) => api.get<Facility>(`${facilityBase(id)}/${encodeURIComponent(facilityId)}`);
export const createFacility = (id: string, body: Record<string, unknown>) => api.post<Facility>(facilityBase(id), body);
export const updateFacility = (id: string, facilityId: string, body: Record<string, unknown>) => api.put<Facility>(`${facilityBase(id)}/${encodeURIComponent(facilityId)}`, body);
export const deleteFacility = (id: string, facilityId: string) => api.delete<{ ok: boolean }>(`${facilityBase(id)}/${encodeURIComponent(facilityId)}`);

// Communications: master radio channel library, shared across incidents.
export const listMasterChannels = (search = "") =>
  api.get<MasterChannel[]>(`/api/comms/master-channels${search ? `?search=${encodeURIComponent(search)}` : ""}`);
export const createMasterChannel = (body: Record<string, unknown>) => api.post<MasterChannel>("/api/comms/master-channels", body);
export const updateMasterChannel = (channelId: number, body: Record<string, unknown>) =>
  api.patch<MasterChannel>(`/api/comms/master-channels/${channelId}`, body);
export const deleteMasterChannel = (channelId: number) => api.delete<{ deleted: boolean }>(`/api/comms/master-channels/${channelId}`);

// Communications: ICS-205 incident channel plan.
const channelsPlanBase = (id: string) => `/api/incidents/${encodeURIComponent(id)}/channels-plan`;
export const listChannelsPlan = (id: string) => api.get<IncidentChannel[]>(channelsPlanBase(id));
export const addChannelFromMaster = (id: string, masterId: number, defaults: Record<string, unknown> = {}) =>
  api.post<IncidentChannel>(channelsPlanBase(id), { master_id: masterId, defaults });
export const updateChannelPlanRow = (id: string, rowId: number, patch: Record<string, unknown>) =>
  api.put<IncidentChannel>(`${channelsPlanBase(id)}/${rowId}`, patch);
export const deleteChannelPlanRow = (id: string, rowId: number) => api.delete<void>(`${channelsPlanBase(id)}/${rowId}`);
export const reorderChannelPlanRow = (id: string, rowId: number, direction: "up" | "down") =>
  api.patch<IncidentChannel>(`${channelsPlanBase(id)}/${rowId}/reorder`, { direction });
export const validateChannelsPlan = (id: string) => api.get<ChannelsPlanValidation>(`${channelsPlanBase(id)}/validate`);

export const getCommunicationsPlan = (id: string, opPeriodId?: string | null) =>
  api.get<CommunicationsPlan>(
    `/api/incidents/${encodeURIComponent(id)}/communications-plan${opPeriodId ? `?op_period_id=${encodeURIComponent(opPeriodId)}` : ""}`
  );
export const saveCommunicationsPlan = (id: string, body: Record<string, unknown>) =>
  api.put<CommunicationsPlan>(`/api/incidents/${encodeURIComponent(id)}/communications-plan`, body);

// Approvals: shared workflow API (start/sign/get) — same endpoints desktop drives.
const approvalsBase = (id: string) => `/api/incidents/${encodeURIComponent(id)}/approvals`;
export const getApprovalInstance = (id: string, entityType: string, entityId: string) =>
  api.get<ApprovalInstance>(`${approvalsBase(id)}/instances/${entityType}/${encodeURIComponent(entityId)}`);
export const previewStartApproval = (id: string, entityType: string, entityId: string) =>
  api.get<ApprovalPreviewRow[]>(`${approvalsBase(id)}/${entityType}/${encodeURIComponent(entityId)}/start/preview`);
export const startApproval = (id: string, entityType: string, entityId: string, assignActors: Record<string, number> = {}) =>
  api.post<ApprovalInstance>(`${approvalsBase(id)}/${entityType}/${encodeURIComponent(entityId)}/start`, { assign_actors: assignActors });
export const previewSignApproval = (id: string, entityType: string, entityId: string, stepId: string) =>
  api.get<ApprovalPreviewRow[]>(`${approvalsBase(id)}/${entityType}/${encodeURIComponent(entityId)}/sign/preview?step_id=${encodeURIComponent(stepId)}`);
export const signApprovalStep = (
  id: string,
  entityType: string,
  entityId: string,
  body: {
    step_id: string;
    actor_id: number;
    action: "approved" | "rejected" | "acknowledged";
    notes?: string;
    assign_actors?: Record<string, number>;
  }
) => api.post<ApprovalInstance>(`${approvalsBase(id)}/${entityType}/${encodeURIComponent(entityId)}/sign`, body);
export const assignApprovalStep = (
  id: string,
  entityType: string,
  entityId: string,
  body: { step_id: string; actor_id: number }
) => api.post<ApprovalInstance>(`${approvalsBase(id)}/${entityType}/${encodeURIComponent(entityId)}/assign-step`, body);
export const notifyApprovalStep = (id: string, entityType: string, entityId: string, stepId: string) =>
  api.post<{ ok: boolean }>(
    `${approvalsBase(id)}/${entityType}/${encodeURIComponent(entityId)}/steps/${encodeURIComponent(stepId)}/notify`,
    {}
  );
export const searchPersonnel = (search: string) =>
  api.get<MasterPersonnelSummary[]>(`/api/master/personnel?search=${encodeURIComponent(search)}&limit=25`);

// Communications: traffic log.
const commsLogBase = (id: string) => `/api/incidents/${encodeURIComponent(id)}/comms-log`;
export function listCommsLog(incidentId: string, params: Record<string, string | boolean | number> = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== "" && v !== undefined && v !== null) qs.set(k, String(v));
  }
  const q = qs.toString();
  return api.get<CommsLogEntry[]>(`${commsLogBase(incidentId)}${q ? `?${q}` : ""}`);
}
export const addCommsLogEntry = (id: string, body: Record<string, unknown>) => api.post<CommsLogEntry>(commsLogBase(id), body);
export const updateCommsLogEntry = (id: string, entryId: number, patch: Record<string, unknown>) =>
  api.patch<CommsLogEntry>(`${commsLogBase(id)}/${entryId}`, patch);
export const deleteCommsLogEntry = (id: string, entryId: number) => api.delete<void>(`${commsLogBase(id)}/${entryId}`);
export const listCommsContacts = (id: string) => api.get<CommsContact[]>(`${commsLogBase(id)}/contacts`);

export const listFormExports = (incidentId: string) => api.get<FormExportDefinition[]>(`/api/incidents/${encodeURIComponent(incidentId)}/form-exports`);
export const downloadFormExport = (incidentId: string, body: FormExportRequest) => api.download(`/api/incidents/${encodeURIComponent(incidentId)}/form-exports`, body);

export const listNotifications = (incidentId: string, personRecord: number, unreadOnly = false) =>
  api.get<IncidentNotification[]>(`/api/incidents/${encodeURIComponent(incidentId)}/notifications?person_record=${personRecord}&unread_only=${unreadOnly}`);
export const acknowledgeNotification = (incidentId: string, notificationId: number) =>
  api.post<IncidentNotification>(`/api/incidents/${encodeURIComponent(incidentId)}/notifications/${notificationId}/acknowledge`);
export const dismissNotification = (incidentId: string, notificationId: number) =>
  api.post<IncidentNotification>(`/api/incidents/${encodeURIComponent(incidentId)}/notifications/${notificationId}/dismiss`);

export const chatSummary = (incidentId: string, userId: string) =>
  api.get<{ items: ChatChannelSummary[] }>(`/api/incidents/${encodeURIComponent(incidentId)}/chat/summary?user_id=${encodeURIComponent(userId)}`);
export const markChatChannelRead = (incidentId: string, channelId: string, userId: string) =>
  api.post<{ id: string }>(`/api/incidents/${encodeURIComponent(incidentId)}/chat/channels/${encodeURIComponent(channelId)}/read`, { user_id: userId });

// ---------------------------------------------------------------------------
// GIS: spatial features (Incident Map). Mirrors gis.py's router.
// ---------------------------------------------------------------------------
const gisFeaturesBase = (incidentId: string) => `/api/incidents/${encodeURIComponent(incidentId)}/gis/features`;
export const listSpatialFeatures = (incidentId: string) => api.get<SpatialFeature[]>(gisFeaturesBase(incidentId));
export const archiveSpatialFeature = (incidentId: string, featureId: number) =>
  api.patch<SpatialFeature>(`${gisFeaturesBase(incidentId)}/${featureId}/archive`, {});

// ---------------------------------------------------------------------------
// Medical: the editable ICS-206 plan. Mirrors medical.py's "Editable ICS-206
// plan API" section — one doc per (op_period, version), locked once
// approval_status leaves "not_started".
// ---------------------------------------------------------------------------
const medicalBase = (incidentId: string) => `/api/incidents/${encodeURIComponent(incidentId)}/medical`;
const opVersionQs = (op: number, version?: number) => `op=${op}${version !== undefined ? `&version=${version}` : ""}`;

export const getMedicalPlan = (incidentId: string, op: number, version?: number, prepared?: { name?: string; personnelId?: string; position?: string }) => {
  const qs = new URLSearchParams({ op: String(op) });
  if (version !== undefined) qs.set("version", String(version));
  if (prepared?.name) qs.set("prepared_name", prepared.name);
  if (prepared?.personnelId) qs.set("prepared_personnel_id", prepared.personnelId);
  if (prepared?.position) qs.set("prepared_position", prepared.position);
  return api.get<MedicalPlan>(`${medicalBase(incidentId)}/plan?${qs.toString()}`);
};
export const listMedicalPlanVersions = (incidentId: string, op: number) =>
  api.get<MedicalPlanVersionSummary[]>(`${medicalBase(incidentId)}/plan/versions?op=${op}`);
export const createMedicalPlanNewVersion = (incidentId: string, op: number, version: number | undefined, body: { change_note?: string; person?: Record<string, unknown> }) =>
  api.post<{ version: number }>(`${medicalBase(incidentId)}/plan/new-version?${opVersionQs(op, version)}`, body);
export const duplicateMedicalPlanLastOp = (incidentId: string, op: number, version: number | undefined, body: { person?: Record<string, unknown> }) =>
  api.post<{ duplicated: boolean }>(`${medicalBase(incidentId)}/plan/duplicate-last-op?${opVersionQs(op, version)}`, body);
export const saveMedicalPlanProcedures = (incidentId: string, op: number, version: number | undefined, content: string) =>
  api.patch<{ content: string }>(`${medicalBase(incidentId)}/plan/procedures?${opVersionQs(op, version)}`, { content });
export const submitMedicalPlanForApproval = (incidentId: string, op: number, version: number | undefined) =>
  api.patch<{ approval_status: string }>(`${medicalBase(incidentId)}/plan/status?${opVersionQs(op, version)}`, { status: "pending" });
export const applyMedicalPlanApproval = (incidentId: string, op: number, version: number | undefined, outcome: "approved" | "rejected", person?: Record<string, unknown>) =>
  api.post<MedicalPlan>(`${medicalBase(incidentId)}/plan/approval?${opVersionQs(op, version)}`, { outcome, person });

export const addMedicalPlanRow = (incidentId: string, table: MedicalPlanTable, op: number, version: number | undefined, body: Record<string, unknown>) =>
  api.post<Record<string, unknown>>(`${medicalBase(incidentId)}/plan/${table}?${opVersionQs(op, version)}`, body);
export const updateMedicalPlanRow = (incidentId: string, table: MedicalPlanTable, rowId: number, op: number, version: number | undefined, body: Record<string, unknown>) =>
  api.patch<Record<string, unknown>>(`${medicalBase(incidentId)}/plan/${table}/${rowId}?${opVersionQs(op, version)}`, body);
export const deleteMedicalPlanRow = (incidentId: string, table: MedicalPlanTable, rowId: number, op: number, version: number | undefined) =>
  api.delete<void>(`${medicalBase(incidentId)}/plan/${table}/${rowId}?${opVersionQs(op, version)}`);
export const importMedicalPlanTable = (incidentId: string, table: MedicalPlanTable, op: number, version: number | undefined) =>
  api.post<{ count: number }>(`${medicalBase(incidentId)}/plan/${table}/import?${opVersionQs(op, version)}`);

export const listMedicalAidStations = (incidentId: string, op: number, version?: number) =>
  api.get<MedicalPlanAidStation[]>(`${medicalBase(incidentId)}/aid-stations?${opVersionQs(op, version)}`);
export const createMedicalAidStation = (incidentId: string, op: number, version: number | undefined, body: Record<string, unknown>) =>
  api.post<MedicalPlanAidStation>(`${medicalBase(incidentId)}/aid-stations?${opVersionQs(op, version)}`, body);
export const updateMedicalAidStation = (incidentId: string, rowId: number, op: number, version: number | undefined, body: Record<string, unknown>) =>
  api.patch<MedicalPlanAidStation>(`${medicalBase(incidentId)}/aid-stations/${rowId}?${opVersionQs(op, version)}`, body);
export const deleteMedicalAidStation = (incidentId: string, rowId: number, op: number, version: number | undefined) =>
  api.delete<void>(`${medicalBase(incidentId)}/aid-stations/${rowId}?${opVersionQs(op, version)}`);
export const importMedicalAidStations = (incidentId: string, op: number, version: number | undefined) =>
  api.post<{ count: number }>(`${medicalBase(incidentId)}/aid-stations/import?${opVersionQs(op, version)}`);

// ---------------------------------------------------------------------------
// Safety: canonical Hazard Register (SPE) and ICS-208 Safety Message.
// Mirrors routers/safety.py.
// ---------------------------------------------------------------------------
const safetyBase = (incidentId: string) => `/api/incidents/${encodeURIComponent(incidentId)}/safety`;

export const listHazards = (incidentId: string, opPeriod?: number) =>
  api.get<Hazard[]>(`${safetyBase(incidentId)}/hazards${opPeriod !== undefined ? `?op_period=${opPeriod}` : ""}`);
export const getHazard = (incidentId: string, hazardId: number) => api.get<Hazard>(`${safetyBase(incidentId)}/hazards/${hazardId}`);
export const createHazard = (incidentId: string, body: Record<string, unknown>) => api.post<Hazard>(`${safetyBase(incidentId)}/hazards`, body);
export const updateHazard = (incidentId: string, hazardId: number, body: Record<string, unknown>) =>
  api.patch<Hazard>(`${safetyBase(incidentId)}/hazards/${hazardId}`, body);
export const deleteHazard = (incidentId: string, hazardId: number) => api.delete<void>(`${safetyBase(incidentId)}/hazards/${hazardId}`);

export const getIcs208 = (incidentId: string, op: number) => api.get<Ics208>(`${safetyBase(incidentId)}/ics208?op=${op}`);
export const saveIcs208 = (incidentId: string, body: Record<string, unknown>) => api.put<Ics208>(`${safetyBase(incidentId)}/ics208`, body);

// ---------------------------------------------------------------------------
// CAP ORM Worksheet (CAPF-160 compatibility view). Mirrors routers/safety.py.
// ---------------------------------------------------------------------------
const ormBase = (incidentId: string) => `${safetyBase(incidentId)}/orm`;
export const getCapOrmForm = (incidentId: string, op: number) => api.get<CapOrmForm>(`${ormBase(incidentId)}/form?op=${op}`);
export const saveCapOrmForm = (incidentId: string, body: Record<string, unknown>) => api.put<CapOrmForm>(`${ormBase(incidentId)}/form`, body);
export const listCapOrmHazards = (incidentId: string, op: number) => api.get<CapOrmHazard[]>(`${ormBase(incidentId)}/hazards?op=${op}`);
export const createCapOrmHazard = (incidentId: string, body: Record<string, unknown>) => api.post<CapOrmHazard>(`${ormBase(incidentId)}/hazards`, body);
export const updateCapOrmHazard = (incidentId: string, hazardId: number, op: number, body: Record<string, unknown>) =>
  api.put<CapOrmHazard>(`${ormBase(incidentId)}/hazards/${hazardId}?op=${op}`, body);
export const deleteCapOrmHazard = (incidentId: string, hazardId: number, op: number) => api.delete<void>(`${ormBase(incidentId)}/hazards/${hazardId}?op=${op}`);
export const approveCapOrmForm = (incidentId: string, op: number) => api.post<CapOrmForm>(`${ormBase(incidentId)}/approve`, { op_period: op });

// ---------------------------------------------------------------------------
// IWI (Illness/Injury "Safety Incident") reports. Mirrors routers/safety.py.
// ---------------------------------------------------------------------------
const iwiBase = (incidentId: string) => `${safetyBase(incidentId)}/iwi`;
export function listIwiReports(incidentId: string, params: { severity?: string; status?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.severity) qs.set("severity", params.severity);
  if (params.status) qs.set("status", params.status);
  const q = qs.toString();
  return api.get<IwiReport[]>(`${iwiBase(incidentId)}${q ? `?${q}` : ""}`);
}
export const getIwiReport = (incidentId: string, reportId: string) => api.get<IwiReport>(`${iwiBase(incidentId)}/${encodeURIComponent(reportId)}`);
export const createIwiReport = (incidentId: string, body: Record<string, unknown>) => api.post<IwiReport>(iwiBase(incidentId), body);
export const updateIwiReport = (incidentId: string, reportId: string, body: Record<string, unknown>) =>
  api.put<IwiReport>(`${iwiBase(incidentId)}/${encodeURIComponent(reportId)}`, body);
export const signoffIwiReport = (incidentId: string, reportId: string, role: string, name: string) =>
  api.post<IwiReport>(`${iwiBase(incidentId)}/${encodeURIComponent(reportId)}/signoff`, { role, name });

// ---------------------------------------------------------------------------
// Intel module. Mirrors routers/intel.py exactly — subjects/leads/items
// (with embedded observations)/assessments/log/dashboard. Clues are intel
// items with item_type="Clue"; there's no separate clues endpoint.
// ---------------------------------------------------------------------------
const intelBase = (incidentId: string) => `/api/incidents/${encodeURIComponent(incidentId)}/intel`;

export const SUBJECT_TYPES = ["Missing Person", "Witness", "Reporting Party", "Contact", "Patient", "Vehicle", "Aircraft"];
export const SUBJECT_STATUSES = ["Active", "Located", "Deceased", "Archived"];
export const LEAD_STATUSES = ["New", "Assigned", "In Progress", "Closed", "Converted", "Rejected"];
export const LEAD_PRIORITIES = ["Critical", "High", "Medium", "Low"];
export const LEAD_SOURCE_CATEGORIES = ["Team", "Staff", "Agency / Liaison", "Public Tip", "Other"];
export const SOURCE_RELIABILITY_VALUES = ["Unknown", "Firsthand", "Secondhand", "Official", "Unverified", "Questionable"];
export const INFORMATION_CONFIDENCE_VALUES = ["Confirmed", "Probable", "Possible", "Unconfirmed", "Ruled Out"];
export const ITEM_TYPES = ["Clue", "Infrastructure Assessment", "Road Closure", "Hazard", "Resource Status", "Population Movement", "Communications", "Medical", "Environmental", "Other"];
export const ITEM_STATUSES = ["Active", "Closed", "Archived"];
export const ITEM_TREND_VALUES = ["Improving", "Stable", "Worsening", "Unknown"];
export const SEVERITY_VALUES = ["Critical", "High", "Medium", "Low", "None"];
export const ASSESSMENT_STATUSES = ["Draft", "In Progress", "Complete", "Archived"];

export const getIntelDashboard = (incidentId: string) => api.get<IntelDashboard>(`${intelBase(incidentId)}/dashboard`);

export function listIntelSubjects(incidentId: string, params: { subject_type?: string; status?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.subject_type) qs.set("subject_type", params.subject_type);
  if (params.status) qs.set("status", params.status);
  const q = qs.toString();
  return api.get<IntelSubject[]>(`${intelBase(incidentId)}/subjects${q ? `?${q}` : ""}`);
}
export const getIntelSubject = (incidentId: string, subjectId: string) =>
  api.get<IntelSubject>(`${intelBase(incidentId)}/subjects/${encodeURIComponent(subjectId)}`);
export const createIntelSubject = (incidentId: string, body: Record<string, unknown>) =>
  api.post<IntelSubject>(`${intelBase(incidentId)}/subjects`, body);
export const updateIntelSubject = (incidentId: string, subjectId: string, body: Record<string, unknown>) =>
  api.patch<IntelSubject>(`${intelBase(incidentId)}/subjects/${encodeURIComponent(subjectId)}`, body);
export const archiveIntelSubject = (incidentId: string, subjectId: string) =>
  api.delete<void>(`${intelBase(incidentId)}/subjects/${encodeURIComponent(subjectId)}`);

export function listIntelLeads(incidentId: string, params: { status?: string; priority?: string; assigned_to?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.priority) qs.set("priority", params.priority);
  if (params.assigned_to) qs.set("assigned_to", params.assigned_to);
  const q = qs.toString();
  return api.get<IntelLead[]>(`${intelBase(incidentId)}/leads${q ? `?${q}` : ""}`);
}
export const getIntelLead = (incidentId: string, leadId: string) =>
  api.get<IntelLead>(`${intelBase(incidentId)}/leads/${encodeURIComponent(leadId)}`);
export const createIntelLead = (incidentId: string, body: Record<string, unknown>) =>
  api.post<IntelLead>(`${intelBase(incidentId)}/leads`, body);
export const updateIntelLead = (incidentId: string, leadId: string, body: Record<string, unknown>) =>
  api.patch<IntelLead>(`${intelBase(incidentId)}/leads/${encodeURIComponent(leadId)}`, body);
export const closeIntelLead = (incidentId: string, leadId: string) =>
  api.delete<void>(`${intelBase(incidentId)}/leads/${encodeURIComponent(leadId)}`);
export const convertIntelLead = (incidentId: string, leadId: string, body: { target_type: string; target_id?: string; actor?: string }) =>
  api.post<IntelLead>(`${intelBase(incidentId)}/leads/${encodeURIComponent(leadId)}/convert`, body);

export function listIntelItems(incidentId: string, params: { item_type?: string; status?: string; priority?: string; trend?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.item_type) qs.set("item_type", params.item_type);
  if (params.status) qs.set("status", params.status);
  if (params.priority) qs.set("priority", params.priority);
  if (params.trend) qs.set("trend", params.trend);
  const q = qs.toString();
  return api.get<IntelItem[]>(`${intelBase(incidentId)}/items${q ? `?${q}` : ""}`);
}
export const getIntelItem = (incidentId: string, itemId: string) =>
  api.get<IntelItem>(`${intelBase(incidentId)}/items/${encodeURIComponent(itemId)}`);
export const createIntelItem = (incidentId: string, body: Record<string, unknown>) =>
  api.post<IntelItem>(`${intelBase(incidentId)}/items`, body);
export const updateIntelItem = (incidentId: string, itemId: string, body: Record<string, unknown>) =>
  api.patch<IntelItem>(`${intelBase(incidentId)}/items/${encodeURIComponent(itemId)}`, body);
export const archiveIntelItem = (incidentId: string, itemId: string) =>
  api.delete<void>(`${intelBase(incidentId)}/items/${encodeURIComponent(itemId)}`);
export const addIntelObservation = (incidentId: string, itemId: string, body: Record<string, unknown>) =>
  api.post<IntelItem>(`${intelBase(incidentId)}/items/${encodeURIComponent(itemId)}/observations`, body);
export const updateIntelObservation = (incidentId: string, itemId: string, obsId: string, body: Record<string, unknown>) =>
  api.patch<IntelItem>(`${intelBase(incidentId)}/items/${encodeURIComponent(itemId)}/observations/${encodeURIComponent(obsId)}`, body);

export function listIntelAssessments(incidentId: string, status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return api.get<IntelAssessment[]>(`${intelBase(incidentId)}/assessments${q}`);
}
export const getIntelAssessment = (incidentId: string, assessmentId: string) =>
  api.get<IntelAssessment>(`${intelBase(incidentId)}/assessments/${encodeURIComponent(assessmentId)}`);
export const createIntelAssessment = (incidentId: string, body: Record<string, unknown>) =>
  api.post<IntelAssessment>(`${intelBase(incidentId)}/assessments`, body);
export const updateIntelAssessment = (incidentId: string, assessmentId: string, body: Record<string, unknown>) =>
  api.patch<IntelAssessment>(`${intelBase(incidentId)}/assessments/${encodeURIComponent(assessmentId)}`, body);
export const archiveIntelAssessment = (incidentId: string, assessmentId: string) =>
  api.delete<void>(`${intelBase(incidentId)}/assessments/${encodeURIComponent(assessmentId)}`);

export function getIntelLog(
  incidentId: string,
  params: { entity_type?: string; entity_id?: string; event_type?: string; since?: string; until?: string; limit?: number } = {},
) {
  const qs = new URLSearchParams();
  if (params.entity_type) qs.set("entity_type", params.entity_type);
  if (params.entity_id) qs.set("entity_id", params.entity_id);
  if (params.event_type) qs.set("event_type", params.event_type);
  if (params.since) qs.set("since", params.since);
  if (params.until) qs.set("until", params.until);
  if (params.limit) qs.set("limit", String(params.limit));
  const q = qs.toString();
  return api.get<IntelLogEntry[]>(`${intelBase(incidentId)}/log${q ? `?${q}` : ""}`);
}
export const deleteIwiReport = (incidentId: string, reportId: string) => api.delete<void>(`${iwiBase(incidentId)}/${encodeURIComponent(reportId)}`);
