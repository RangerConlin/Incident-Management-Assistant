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
  vehicle: string;
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
  category: string;
  task_type: string;
  due_datetime: string | null;
  created_at: string | null;
  updated_at: string | null;
  created_by: string;
  operational_period: string;
  primary_team: string;
  team_count: number;
  sortie_count: number;
  last_activity_at: string | null;
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

// GET /api/objectives?incident_id=... — see objectives.py's _normalize().
export interface ObjectiveTaskLink {
  id: number;
  task_id: number;
  link_type: string;
  created_at: string;
  created_by: string | null;
}

export interface ObjectiveAuditEntry {
  ts: string;
  action: string;
  field: string | null;
  old_value: unknown;
  new_value: unknown;
  user_id: string | null;
}

export interface Objective {
  _id: string;
  incident_id: string;
  code: string;
  text: string;
  priority: string;
  status: string;
  owner_section: string | null;
  op_period_id: string | null;
  due_time: string | null;
  tags: string[];
  display_order: number;
  narrative: string | null;
  task_links: ObjectiveTaskLink[];
  audit: ObjectiveAuditEntry[];
  open_tasks: number;
  total_tasks: number;
  created_by: string | null;
  updated_by: string | null;
  origin_module: string | null;
  origin_id: string | null;
}

// GET /api/incidents/{id}/planning/operational-periods — operational_periods.py.
export interface OperationalPeriod {
  id: number;
  incident_id: string;
  number: number;
  name: string;
  status: "Planned" | "Active" | "Complete" | "Canceled";
  start_time: string;
  end_time: string;
  briefing_time: string;
  debrief_time: string;
  objectives: string;
  weather_summary: string;
  safety_message: string;
  created_at: string;
  updated_at: string;
}

// GET /api/incidents/{id}/planning/meetings — meetings.py.
export interface MeetingAttendee {
  id: number;
  meeting_id: number;
  display_name: string;
  attendee_type: string;
  role: string;
  requirement_status: string;
  attendance_status: string;
}

export interface MeetingChecklistItem {
  id: number;
  meeting_id: number;
  group_name: string;
  text: string;
  assigned_to: string;
  is_complete: boolean;
  is_not_applicable: boolean;
  sort_order: number;
}

export interface MeetingNote {
  id: number;
  meeting_id: number;
  category: string;
  text: string;
  author: string;
  timestamp: string;
  routing_status: string;
  routed_log_refs: string[];
  routed_at: string | null;
}

export interface Meeting {
  id: number;
  incident_id: string;
  operational_period_id: string | null;
  template_id: string | null;
  title: string;
  meeting_date: string;
  start_time: string;
  end_time: string;
  location: string;
  virtual_link: string;
  owner: string;
  status: string;
  show_on_ics230: boolean;
  freeform_notes: string;
  notes_log_routing_status: string;
  created_at: string;
  updated_at: string;
  attendees: MeetingAttendee[];
  checklist_items: MeetingChecklistItem[];
  structured_notes: MeetingNote[];
}

export interface MeetingTemplate {
  slug: string;
  name: string;
  default_duration_minutes: number;
  agenda_sections: string[];
  required_attendee_roles: string[];
  optional_attendee_roles: string[];
  prep_checklist_items: string[];
  agenda_checklist_items: string[];
  closeout_checklist_items: string[];
  appears_on_ics230_default: boolean;
  active: boolean;
}
