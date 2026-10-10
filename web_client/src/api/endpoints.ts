import { api } from "./client";
import type {
  CheckinRecord,
  ChatChannel,
  ChatMessage,
  Incident,
  LoginResponse,
  PersonnelSummary,
  RosterRow,
  TeamOption,
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

export async function fetchCheckin(incidentId: string, personRecord: number): Promise<CheckinRecord | null> {
  try {
    return await api.get<CheckinRecord>(`/api/incidents/${incidentId}/checkin/${personRecord}`);
  } catch (err) {
    if ((err as { status?: number }).status === 404) return null;
    throw err;
  }
}

export function saveCheckin(
  incidentId: string,
  personRecord: number,
  payload: {
    status: string;
    role_on_team: string;
    team_id?: string | null;
    location?: string;
    notes?: string;
  }
) {
  return api.put<CheckinRecord>(`/api/incidents/${incidentId}/checkin/${personRecord}`, payload);
}

export function getCheckinRoles(incidentId: string) {
  return api.get<string[]>(`/api/incidents/${incidentId}/checkin/roles`);
}

export function getCheckinTeams(incidentId: string) {
  return api.get<TeamOption[]>(`/api/incidents/${incidentId}/checkin/teams`);
}

export function getRoster(incidentId: string) {
  return api.get<RosterRow[]>(`/api/incidents/${incidentId}/checkin/roster`);
}

export function patchCheckinStatus(incidentId: string, personRecord: number, status: string) {
  return api.patch<RosterRow>(`/api/incidents/${incidentId}/checkin/${personRecord}/status`, { status });
}

export const TEAM_STATUS_STEPS: { key: string; label: string }[] = [
  { key: "assigned", label: "Assigned" },
  { key: "briefed", label: "Briefed" },
  { key: "enroute", label: "En Route" },
  { key: "arrival", label: "On Scene" },
  { key: "find", label: "Find" },
  { key: "complete", label: "Complete" },
  { key: "returning", label: "Returning" },
];

export function getTeam(incidentId: string, teamId: string) {
  return api.get<{ status?: string }>(`/api/incidents/${incidentId}/operations/teams/${teamId}`);
}

export function setTeamStatus(incidentId: string, teamId: string, statusKey: string) {
  return api.patch(`/api/incidents/${incidentId}/operations/teams/${teamId}/status`, {
    status_key: statusKey,
  });
}

export function listChannels(incidentId: string, userId: string) {
  return api.get<{ items: ChatChannel[] }>(
    `/api/incidents/${incidentId}/chat/channels?user_id=${encodeURIComponent(userId)}`
  );
}

export function listMessages(incidentId: string, channelId: string) {
  return api.get<{ items: ChatMessage[] }>(
    `/api/incidents/${incidentId}/chat/channels/${channelId}/messages`
  );
}

export function sendMessage(
  incidentId: string,
  channelId: string,
  senderId: string,
  senderName: string,
  text: string
) {
  return api.post<ChatMessage>(`/api/incidents/${incidentId}/chat/channels/${channelId}/messages`, {
    sender_id: senderId,
    sender_name: senderName,
    text,
  });
}
