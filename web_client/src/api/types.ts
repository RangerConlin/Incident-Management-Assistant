export interface PublicUser {
  user_id: string;
  username: string;
  display_name: string;
  person_record: number | null;
}

export interface PersonnelSummary {
  person_record: number | null;
  person_id: string;
  first_name?: string;
  last_name?: string;
  name: string;
  primary_role?: string | null;
}

export interface LoginResponse {
  token: string;
  session_id: string;
  user_id: string;
  person_record: number | null;
  user: PublicUser;
  personnel: PersonnelSummary | null;
}

export interface Incident {
  id: string;
  incident_id?: string;
  number: string;
  name: string;
  status?: string;
  type?: string;
}

// GET /api/incidents/{id}/operations/team-assignment-rows — one row per team.
export interface TeamAssignmentRow {
  tt_id: number | null;
  task_id: number | string | null;
  team_id: number;
  sortie: string;
  name: string;
  team_type: string;
  leader: string;
  contact: string;
  status: string;
  ci_status: string;
  assignment: string;
  location: string;
  needs_attention: boolean;
  needs_assistance_flag: boolean;
  emergency_flag: boolean;
  last_checkin_at: string | null;
  checkin_reference_at: string | null;
  team_status_updated: string | null;
  last_updated: string | null;
}

// GET /api/incidents/{id}/operations/task-rows — one row per task.
export interface TaskRow {
  id: number;
  number: string;
  name: string;
  assigned_teams: string[];
  status: string;
  priority: string;
  location: string;
}

// GET/PATCH .../operations/teams/{team_id} — full team document.
export interface TeamDetail {
  int_id: number;
  name: string | null;
  callsign: string | null;
  team_leader: number | string | null;
  leader_name?: string | null;
  leader_phone?: string | null;
  phone: string | null;
  team_type: string | null;
  role: string | null;
  priority: string | null;
  notes: string | null;
  status: string;
  ci_status: string;
  status_updated: string | null;
  current_task_id: number | string | null;
  location: string | null;
  operational_unit_id: number | string | null;
  needs_attention: boolean;
  emergency_flag: boolean;
  last_checkin_at: string | null;
  checkin_reference_at: string | null;
  last_comm_ping: string | null;
  members_json: string;
  vehicles_json: string;
  equipment_json: string;
  aircraft_json: string;
  resource_type_id: number | string | null;
  readiness_status: string | null;
}

export interface TaskTeam {
  id: number;
  team_id: number;
  team_name: string;
  team_leader: string;
  team_leader_phone: string;
  sortie_id: string | null;
  is_primary: boolean;
  time_assigned: string | null;
  time_briefed: string | null;
  time_enroute: string | null;
  time_arrived: string | null;
  time_discovery: string | null;
  time_complete: string | null;
  time_cleared: string | null;
}

// GET/PATCH .../operations/tasks/{task_id} — full task document.
export interface TaskDetail {
  int_id: number;
  task_id: string;
  title: string;
  category: string | null;
  task_type: string | null;
  priority: string;
  status: string;
  location: string | null;
  location_kind: string;
  location_facility_id: string | null;
  location_geocoded_address: string | null;
  location_latitude: number | null;
  location_longitude: number | null;
  location_feature_id: string | null;
  assignment: string | null;
  created_by: string;
  created_at: string;
  due_time: string | null;
  task_teams: TaskTeam[];
  active_team_ids: number[];
}
