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

export interface TeamTypeDefinition {
  id: number;
  name: string;
  type_short: string;
  category: string;
  description: string;
  background_color: string;
  text_color: string;
  icon_key: string;
  capability_ids: string[];
  minimum_personnel: number;
  minimum_vehicles: number;
  minimum_aircraft: number;
  minimum_equipment: number;
  detail_sections: string[];
  is_drone: boolean;
  is_aviation: boolean;
  is_active: boolean;
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
  leader_person_record?: number | string | null;
  member_person_records: number[];
  phone: string | null;
  team_type: string | null;
  role: string | null;
  priority: string | null;
  assignment: string | null;
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
  last_comm_ts?: string | null;
  last_contact_ts?: string | null;
  last_update_ts?: string | null;
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
  // Some older meetings were seeded without per-item ids (legacy data) --
  // see MeetingDetailPage's "addressable" guard for what that means for
  // editing/removing such a row.
  id: number | null;
  meeting_id: number | null;
  display_name: string;
  attendee_type: string;
  role: string;
  requirement_status: string;
  attendance_status: string;
}

export interface MeetingChecklistItem {
  id: number | null;
  meeting_id: number | null;
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

// GET /api/incidents/{id}/sitreps — sitrep.py.
export interface SitrepSection {
  section_type: string;
  title: string;
  auto_content: string;
  edited_content: string;
  visibility: string;
  review_status: string;
  last_refreshed_at: string | null;
}

export interface Sitrep {
  id: string;
  incident_id: string;
  sitrep_number: number;
  operational_period_id: string | null;
  created_at: string;
  updated_at: string;
  prepared_by: string;
  status: string;
  audience: string;
  approved_by: string | null;
  approved_at: string | null;
  distributed_at: string | null;
  summary: string;
  current_priority: string;
  current_tempo: string;
  next_update_due: string | null;
  sections: SitrepSection[];
}

export interface SitrepOperationalSummary {
  teams: Record<string, number>;
  tasks: Record<string, number>;
  total_checked_in: number;
  alerts: { message: string; source: string }[];
}

export interface SitrepEvent {
  id: string;
  incident_id: string;
  sitrep_id: string | null;
  timestamp: string;
  event_type: string;
  summary: string;
  source: string;
  impact: string;
  visibility: string;
  include_in_sitrep: boolean;
  include_in_214: boolean;
  reviewed_by: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

// GET /api/incidents/{id}/planning/work-assignments — work_assignments.py.
// ICS-215/204-style tactics planner. Only the fields this client's UI uses
// are modeled here (hazards/comms/agency_request_links/log_entries/outputs
// exist on the real doc but have no web UI yet).
export interface WorkAssignmentResourceAssignment {
  id: number;
  resource_kind: string;
  resource_id: string;
  display_name: string;
  status: string;
  assigned_at: string | null;
  released_at: string | null;
  notes: string;
}

export interface WorkAssignmentResourceRequirement {
  id: number;
  resource_type_id: string | null;
  resource_type_text: string;
  capability_id: string | null;
  capability_text: string;
  quantity_required: number;
  quantity_assigned: number;
  quantity_available: number;
  quantity_gap: number;
  unit: string;
  priority: string;
  source_note: string;
  notes: string;
  created_at: string;
  updated_at: string;
  assignments: WorkAssignmentResourceAssignment[];
}

export interface WorkAssignmentTaskLink {
  id: number;
  task_id: number;
  link_type: string;
  created_at: string;
  notes: string;
}

export interface TaskWorkAssignmentLink {
  id: number;
  assignment_number: string;
  assignment_name: string;
  objective_id: string | null;
  planning_status: string;
  link_id: number;
  link_type: string;
}

export interface WorkAssignment {
  id: number;
  assignment_number: string;
  assignment_name: string;
  objective_id: string | null;
  operational_period_id: number | null;
  branch: string;
  division_group: string;
  location: string;
  location_facility_id: string;
  assignment_kind: string;
  priority: string;
  planning_status: string;
  safety_status: string;
  resource_status: string;
  description: string;
  tactics_summary: string;
  special_instructions: string;
  prepared_by: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
  notes: string;
  resources: WorkAssignmentResourceRequirement[];
  task_links: WorkAssignmentTaskLink[];
}

export interface SitrepDistribution {
  id: string;
  sitrep_id: string;
  incident_id: string;
  version_name: string;
  audience: string;
  recipient_group: string;
  delivery_method: string;
  approved_by: string | null;
  distributed_by: string;
  distributed_at: string;
  export_file_path: string | null;
  notes: string;
  created_at: string;
}

// Public Information: shared per-incident API, matching the desktop record shape.
export interface PioApproval {
  id: number; reviewer_name: string; reviewer_id: string; action: string; comment: string; timestamp: string;
}
export interface PioMessage {
  id: number; title: string; subtitle: string; type: string; audience: string; priority: string; status: string;
  dateline: string; body: string; next_update_statement: string; boilerplate: string;
  created_by: string; created_at: string; updated_at: string;
  approved_by: string; approved_at: string; published_by: string; published_at: string;
  archived_by: string; archived_at: string; related_operational_period_id: string;
  template_id: number | null; source_media_log_id?: number;
}
export interface PioRecord {
  id: number;
  [key: string]: unknown;
}
export interface PioTimelineEvent {
  id: number; event_time: string; event_text: string; created_by: string;
}

// GET /api/incidents/{id}/resources — checked-in resource_status rows
// (personnel, vehicle, aircraft, equipment share this collection).
export interface ResourceStatusRow {
  entity_type: "personnel" | "vehicle" | "aircraft" | "equipment" | string;
  record_id: number | string;
  resource_name: string;
  resource_type: string;
  status: string;
  assigned_to: string | null;
  assignment_reference: string | null;
  location: string | null;
  notes: string | null;
  eta_utc: string | null;
  checked_in_time: string | null;
  checked_out_time: string | null;
  created_at: string;
  updated_at: string;
  status_log: { status: string; timestamp: string; changed_by: string }[];
}

// GET /api/incidents/{id}/checkin/roster — personnel roster derived from resource_status.
export interface CheckinRosterRow {
  person_record: number;
  person_id: string;
  name: string;
  role: string | null;
  team: string;
  phone: string;
  callsign: string;
  status: string;
  checked_in: boolean;
  updated_at: string | null;
}

// GET /api/incidents/{id}/checkin/personnel/search — master personnel lookup.
export interface MasterPersonnelSummary {
  person_record: number;
  person_id: string;
  name: string;
  primary_role: string | null;
  phone: string | null;
  callsign?: string;
}

export interface MasterVehicle {
  vehicle_record: number;
  vehicle_id: string;
  make: string;
  model: string;
  license_plate: string;
}

export interface MasterAircraft {
  aircraft_record: number;
  aircraft_id: string;
  tail_number: string;
  callsign: string;
  make: string;
  model: string;
}

export interface MasterEquipment {
  equipment_record: number;
  equipment_id: string;
  name: string;
  type: string;
  serial_number: string;
}

// Liaison records retain the API's sequential int_id identifier.
export interface LiaisonRecord {
  int_id: number;
  [key: string]: unknown;
}
export interface LiaisonNarrative {
  ts: string; category: string; author: string; text: string;
}
export interface LiaisonRequest extends LiaisonRecord {
  agency_id: number; code: string; request_type: "Request" | "Offer";
  summary: string; status: string; priority: string; due_date: string;
  objective_ids: string[]; task_ids: number[]; resource_request_ids: string[];
  narrative: LiaisonNarrative[];
}
export interface LiaisonAgencyDetail {
  agency: LiaisonRecord;
  contacts: LiaisonRecord[]; interactions: LiaisonRecord[];
  requests: LiaisonRecord[]; offers: LiaisonRecord[]; feedback: LiaisonRecord[];
  followups: LiaisonRecord[]; restrictions: LiaisonRecord[]; agreements: LiaisonRecord[];
}

export interface LogisticsRecord { [key: string]: unknown; }
export interface RequestItem extends LogisticsRecord {
  id: string; kind: string; description: string; quantity: number; unit: string;
  ref_id?: string | null; special_instructions?: string | null;
}
export interface RequestFulfillment extends LogisticsRecord {
  id: string; status: string; eta_utc?: string | null; note?: string | null;
  supplier_id?: string | null; assigned_team_id?: number | string | null;
  assigned_vehicle_id?: number | string | null; destination_location?: string | null;
  destination_facility_id?: string | null; ts_utc: string;
}
export interface ResourceRequest extends LogisticsRecord {
  id: string; title: string; requesting_section: string; priority: string; status: string;
  needed_by_utc?: string | null; delivery_location?: string | null; delivery_facility_id?: string | null;
  justification?: string | null; comms_requirements?: string | null; links?: string | null;
  created_by_id: string; created_utc: string; last_updated_utc: string; version: number;
}
export interface ResourceRequestDetail extends ResourceRequest {
  items: RequestItem[]; approvals: LogisticsRecord[]; fulfillments: RequestFulfillment[]; audit: LogisticsRecord[];
}
export interface Facility extends LogisticsRecord {
  id: string; name: string; facility_type: string; status: string; address: string;
  latitude: number | null; longitude: number | null; geocoded_address: string; icao_code: string;
  manager_personnel_id: string; manager_name: string; contact_name: string; contact_phone: string;
  notes: string; function_tags: string[]; served_sections: string[]; is_primary: boolean;
  metadata: Record<string, unknown>; created_at: string; updated_at: string;
}
export interface IncidentProfile { id:string; name:string; number:string; type:string; status:string; description:string; start_time:string|null; end_time:string|null; icp_location:string; icp_facility_id:string|null; latitude:number|null; longitude:number|null; is_training:boolean; }
export interface OrgAssignment { id:string; assignment_id:string; position_id:number; person_record:number; person_name:string; assignment_type:string; start_time:string|null; end_time:string|null; }
export interface OrgPosition { id:number; position_id:number; title:string; classification:string; parent_position_id:number|null; sort_order:number; primary:OrgAssignment[]; deputies:OrgAssignment[]; staff_assistants:OrgAssignment[]; }
export interface OrgTemplate { id:number; template_id:number; name:string; description:string|null; payload:Record<string,unknown>[]; }
export interface IapForm { form_id:string; title:string; op_number:number; revision:number; status:string; last_updated:string|null; fields:Record<string,unknown>; attachments:string[]; display_order:number; }
export interface IapPackage { incident_id:string; op_number:number; op_start:string; op_end:string; created_at:string; status:string; notes:string; version_tag:string|null; published_pdf_path:string|null; forms:IapForm[]; }

// GET /api/comms/master-channels — radio channel library (shared across incidents).
export interface MasterChannel {
  id: number | null;
  name: string;
  function: string;
  rx_freq: number;
  tx_freq: number | null;
  rx_tone: string | null;
  tx_tone: string | null;
  system: string | null;
  mode: string;
  notes: string | null;
  line_a: number;
  line_c: number;
  display_name: string;
  band: string;
}

// GET .../channels-plan — an incident's ICS-205 channel assignment row,
// joined with the master channel it points to.
export interface IncidentChannel {
  id: number | null;
  channel_id: string;
  master_id: string;
  channel: string;
  function: string | null;
  band: string | null;
  system: string | null;
  mode: string | null;
  rx_freq: number | null;
  tx_freq: number | null;
  rx_tone: string | null;
  tx_tone: string | null;
  line_a: number;
  line_c: number;
  encryption: string;
  assignment_division: string | null;
  assignment_team: string | null;
  priority: string;
  include_on_205: number;
  remarks: string | null;
  sort_index: number;
  created_at: string;
  updated_at: string;
}

export interface CommunicationsPlan {
  plan_id: string;
  incident_id: string;
  op_period_id: string | null;
  special_instructions: string;
  phone_numbers: Record<string, unknown>[];
  notes: string;
  created_at?: string;
  updated_at?: string;
}

// Approval workflow — matches server/sarapp_db/sarapp_db/api/routers/approvals.py.
// Step/escalation logic lives server-side; this is just the instance shape
// both desktop and web render.
export interface ApprovalStepInstance {
  step_id: string;
  role: string;
  label: string;
  kind: "sequential" | "parallel" | "ack";
  order: number;
  status: "waiting" | "active" | "completed" | "skipped";
  resolved_actor_id: number | null;
  resolved_role: string | null;
  activated_at: string | null;
  completed_at: string | null;
}

export interface ApprovalInstance {
  incident_id: string;
  entity_type: string;
  entity_id: string;
  status: "not_started" | "pending" | "approved" | "rejected";
  steps: ApprovalStepInstance[];
  started_at: string | null;
  completed_at: string | null;
}

export interface ChannelsPlanValidation {
  messages: { level: "conflict" | "warning"; text: string }[];
  conflicts: number;
  warnings: number;
}

export interface CommsContact {
  type: "team" | "personnel";
  id: number | null;
  primary: string;
  secondary: string;
  aliases: string[];
}

// GET/POST .../comms-log — radio/phone traffic log entries.
export interface CommsLogEntry {
  id: number | null;
  comms_id: string;
  ts_utc: string;
  ts_local: string | null;
  direction: string | null;
  priority: string;
  resource_id: number | null;
  resource_label: string;
  frequency: string;
  band: string;
  mode: string;
  from_unit: string;
  to_unit: string;
  message: string;
  action_taken: string;
  follow_up_required: boolean;
  disposition: string;
  operator_user_id: string | null;
  operator_display_name: string | null;
  team_id: number | null;
  task_id: number | null;
  vehicle_id: number | null;
  personnel_id: number | null;
  attachments: string[];
  geotag_lat: number | null;
  geotag_lon: number | null;
  notification_level: string | null;
  is_status_update: boolean;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
}

export interface FormExportDefinition { form_id: string; label: string; source: string; set: string; }
export interface FormExportRequest { form_id: string; source_id?: string; operational_period_id?: number; prepared_by: string; }
