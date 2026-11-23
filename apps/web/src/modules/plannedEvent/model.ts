// Pure logic for the Planned Event Toolkit screens. No React, no network — kept
// separate so it can be unit-tested with `node --test` (see tests/plannedEvent.test.mjs).
// The rules mirror server/sarapp_db/sarapp_db/api/routers/plannedtoolkit.py; the
// server stays authoritative and these helpers only decide what to offer and
// what to send.

export const SCHEDULE_STATUSES = ["Scheduled", "In Progress", "Completed", "Delayed", "Cancelled"] as const;
export type ScheduleStatus = (typeof SCHEDULE_STATUSES)[number];
export const TERMINAL_STATUSES: readonly string[] = ["Completed", "Cancelled"];

/** The one missed-occurrence rule the backend vocabulary defines today. */
export const MISSED_OCCURRENCE_LATEST_OVERDUE = "latest_overdue";

export type PlannedTool = "promotions" | "vendors" | "permits" | "quick-assignments" | "health-inspections";

/** Planned record as returned by the planned toolkit API (`_map_doc`). */
export interface PlannedRecord {
  id: number;
  record_id: string;
  incident_id: string;
  tool: string;
  title: string;
  summary: string;
  status: string;
  priority: string;
  assigned_to: string;
  assigned_team_id: string;
  assigned_person_id: string;
  location: string;
  zone: string;
  scheduled_at: string;
  due_at: string;
  starts_at: string;
  ends_at: string;
  actual_start_at: string;
  actual_end_at: string;
  time_zone: string;
  delay_reason: string;
  cancellation_reason: string;
  meeting_id: string;
  gis_feature_id: string;
  quick_assignment_id: string;
  schedule_item_id: string;
  revision: number;
  kind: string;
  owner: string;
  tags: string[];
  recurring: boolean;
  recurrence_rule: string;
  recurrence_start_at: string;
  recurrence_end_at: string;
  missed_occurrence_behavior: string;
  template_id: string;
  generated_from_template_id: string;
  lifecycle_state: string;
  active_at: string;
  triggered_at: string;
  source_type: string;
  source_id: string;
  source_label: string;
  source_tool: string;
  linked_tasking_id: string;
  promoted_at: string;
  promoted_by: string;
  promoted_read_only: boolean;
  audience: string;
  channel: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Reminder (schedule trigger) as returned by `_map_schedule_trigger`. */
export interface ScheduleTrigger {
  id: number;
  trigger_id: string;
  incident_id: string;
  schedule_item_id: string;
  trigger_type: string;
  label: string;
  offset_minutes: number | null;
  trigger_at: string;
  relative_to: string;
  enabled: boolean;
  fired_at: string;
  fire_error: string;
  severity: string;
  requires_acknowledgement: boolean;
  message_template: string;
  quick_assignment_template_id: string;
  title: string;
  summary: string;
  recurring: boolean;
  recurrence_rule: string;
  missed_occurrence_behavior: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------- actions

export type ScheduleAction = "start" | "resume" | "complete" | "delay" | "cancel";

const ACTION_FROM: Record<ScheduleAction, readonly string[]> = {
  start: ["Scheduled"],
  resume: ["Delayed"],
  complete: ["In Progress"],
  delay: ["Scheduled", "In Progress"],
  cancel: ["Scheduled", "In Progress", "Delayed"],
};

export const ACTION_LABEL: Record<ScheduleAction, string> = {
  start: "Start", resume: "Resume", complete: "Complete", delay: "Delay", cancel: "Cancel activity",
};

/** Event-day actions available from a status (the server's status matrix). */
export function allowedActions(status: string): ScheduleAction[] {
  return (Object.keys(ACTION_FROM) as ScheduleAction[]).filter(action => ACTION_FROM[action].includes(status));
}

/** Where Resume lands: back in progress if it ever actually started, otherwise rescheduled. */
export function resumeTarget(item: Pick<PlannedRecord, "actual_start_at">): ScheduleStatus {
  return item.actual_start_at ? "In Progress" : "Scheduled";
}

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.includes(status);
}

// ------------------------------------------------------------------ time

export function parseTime(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isNaN(ms) ? null : ms;
}

/** `<input type="datetime-local">` value (local, minute precision) -> API timestamp (UTC, whole seconds). */
export function toApiTime(local: string): string {
  if (!local) return "";
  const ms = new Date(local).getTime();
  if (Number.isNaN(ms)) return "";
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}

/** API timestamp -> `<input type="datetime-local">` value in the viewer's local zone. */
export function toLocalInput(value: string | null | undefined): string {
  const ms = parseTime(value);
  if (ms === null) return "";
  const d = new Date(ms);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function minutesBetween(fromMs: number, toMs: number): number {
  return Math.round((toMs - fromMs) / 60_000);
}

/** "1 h 5 min", "12 min", "0 min". Sign is the caller's job. */
export function formatMinutes(total: number): string {
  const abs = Math.abs(Math.round(total));
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  if (h && m) return `${h} h ${m} min`;
  if (h) return `${h} h`;
  return `${m} min`;
}

// ------------------------------------------------- planned vs. actual

export interface PlannedVsActual {
  startVarianceMin: number | null;   // + = started late, - = started early
  endVarianceMin: number | null;
  plannedDurationMin: number | null;
  actualDurationMin: number | null;
}

export function plannedVsActual(item: Pick<PlannedRecord, "starts_at" | "ends_at" | "actual_start_at" | "actual_end_at">): PlannedVsActual {
  const ps = parseTime(item.starts_at), pe = parseTime(item.ends_at);
  const as = parseTime(item.actual_start_at), ae = parseTime(item.actual_end_at);
  return {
    startVarianceMin: ps !== null && as !== null ? minutesBetween(ps, as) : null,
    endVarianceMin: pe !== null && ae !== null ? minutesBetween(pe, ae) : null,
    plannedDurationMin: ps !== null && pe !== null ? minutesBetween(ps, pe) : null,
    actualDurationMin: as !== null && ae !== null ? minutesBetween(as, ae) : null,
  };
}

export function varianceLabel(minutes: number | null, early = "early", late = "late"): string {
  if (minutes === null) return "—";
  if (minutes === 0) return "On time";
  return `${formatMinutes(minutes)} ${minutes > 0 ? late : early}`;
}

// ------------------------------------------------------------- attention

export type AttentionKind = "overdue-start" | "past-end" | "starting-soon" | "delayed";
export interface Attention { kind: AttentionKind; label: string; minutes: number }

/** Window in which a still-Scheduled activity is flagged as starting soon. */
export const STARTING_SOON_MINUTES = 60;

/**
 * Computed attention condition. Deliberately not a status: the server never
 * changes an activity's status just because its time passed, so the board
 * only flags it.
 */
export function attention(item: Pick<PlannedRecord, "status" | "starts_at" | "ends_at">, nowMs: number): Attention | null {
  const start = parseTime(item.starts_at), end = parseTime(item.ends_at);
  if (item.status === "Delayed") return { kind: "delayed", label: "Delayed", minutes: 0 };
  if (item.status === "Scheduled" && start !== null) {
    const until = minutesBetween(nowMs, start);
    if (until < 0) return { kind: "overdue-start", label: `Should have started ${formatMinutes(until)} ago`, minutes: -until };
    if (until <= STARTING_SOON_MINUTES) return { kind: "starting-soon", label: `Starts in ${formatMinutes(until)}`, minutes: until };
  }
  if (item.status === "In Progress" && end !== null) {
    const over = minutesBetween(end, nowMs);
    if (over > 0) return { kind: "past-end", label: `${formatMinutes(over)} past planned end`, minutes: over };
  }
  return null;
}

// ---------------------------------------------------------- validation

export function validateRange(startIso: string, endIso: string, label: string): string | null {
  const s = parseTime(startIso), e = parseTime(endIso);
  if (s !== null && e !== null && e < s) return `${label} end must not be before its start.`;
  return null;
}

export interface ReasonInput { reason: string; revisedStartLocal?: string }

export function validateDelay(input: ReasonInput, endsAt: string): string | null {
  if (!input.reason.trim()) return "A reason is required to delay an activity.";
  if (input.revisedStartLocal) {
    const err = validateRange(toApiTime(input.revisedStartLocal), endsAt, "Planned");
    if (err) return "The revised start must not be after the planned end.";
  }
  return null;
}

export function validateCancel(reason: string): string | null {
  return reason.trim() ? null : "A reason is required to cancel an activity.";
}

export function validateCorrection(reason: string, changes: { status?: string; actual_start_at?: string; actual_end_at?: string }): string | null {
  if (!reason.trim()) return "A reason is required to correct an activity.";
  if (changes.status === undefined && changes.actual_start_at === undefined && changes.actual_end_at === undefined) return "Change the status or an actual time to record a correction.";
  return validateRange(changes.actual_start_at ?? "", changes.actual_end_at ?? "", "Actual");
}

// ------------------------------------------------------------ payloads

export interface ActivityForm {
  name: string; kind: string; starts_at: string; ends_at: string; location: string; zone: string;
  owner: string; assigned_to: string; assigned_team_id: string; notes: string;
}

export function emptyActivityForm(): ActivityForm {
  return { name: "", kind: "Milestone", starts_at: "", ends_at: "", location: "", zone: "", owner: "", assigned_to: "", assigned_team_id: "", notes: "" };
}

export function activityToForm(item: PlannedRecord): ActivityForm {
  return {
    name: item.title, kind: item.kind || "Milestone", starts_at: toLocalInput(item.starts_at), ends_at: toLocalInput(item.ends_at),
    location: item.location, zone: item.zone, owner: item.owner, assigned_to: item.assigned_to, assigned_team_id: item.assigned_team_id, notes: item.summary,
  };
}

export function validateActivity(form: ActivityForm): string | null {
  if (!form.name.trim()) return "Name is required.";
  return validateRange(toApiTime(form.starts_at), toApiTime(form.ends_at), "Planned");
}

/** Create/patch body. Free-text responsibility never invents a team id; the picker owns that. */
export function activityBody(form: ActivityForm): Record<string, unknown> {
  return {
    name: form.name.trim(), kind: form.kind.trim() || "Milestone",
    starts_at: toApiTime(form.starts_at), ends_at: toApiTime(form.ends_at),
    location: form.location.trim(), zone: form.zone.trim(), owner: form.owner.trim(),
    assigned_to: form.assigned_to.trim(), assigned_team_id: form.assigned_team_id, notes: form.notes.trim(),
  };
}

/** Only the fields that changed — keeps the audit trail honest and the PATCH small. */
export function activityPatch(original: PlannedRecord, form: ActivityForm): Record<string, unknown> {
  const next = activityBody(form);
  const current: Record<string, unknown> = {
    name: original.title, kind: original.kind || "Milestone", starts_at: original.starts_at, ends_at: original.ends_at,
    location: original.location, zone: original.zone, owner: original.owner, assigned_to: original.assigned_to,
    assigned_team_id: original.assigned_team_id, notes: original.summary,
  };
  const patch: Record<string, unknown> = {};
  for (const key of Object.keys(next)) {
    if (key === "starts_at" || key === "ends_at") {
      if (parseTime(String(next[key])) !== parseTime(String(current[key]))) patch[key] = next[key];
    } else if (next[key] !== current[key]) patch[key] = next[key];
  }
  return patch;
}

export type ActionBody = {
  expected_revision: number; changed_by: string;
  delay_reason?: string; cancellation_reason?: string; revised_start_at?: string;
};

export function delayBody(input: ReasonInput, revision: number, by: string): ActionBody {
  const body: ActionBody = { expected_revision: revision, changed_by: by, delay_reason: input.reason.trim() };
  if (input.revisedStartLocal) body.revised_start_at = toApiTime(input.revisedStartLocal);
  return body;
}

export function cancelBody(reason: string, revision: number, by: string): ActionBody {
  return { expected_revision: revision, changed_by: by, cancellation_reason: reason.trim() };
}

export function plainActionBody(revision: number, by: string): ActionBody {
  return { expected_revision: revision, changed_by: by };
}

export interface CorrectionForm { reason: string; status: string; actualStartLocal: string; actualEndLocal: string }

/** Sends only what differs from the stored record. */
export function correctionBody(original: PlannedRecord, form: CorrectionForm, revision: number, by: string) {
  const body: Record<string, unknown> = { reason: form.reason.trim(), expected_revision: revision, corrected_by: by };
  if (form.status && form.status !== original.status) body.status = form.status;
  const start = toApiTime(form.actualStartLocal), end = toApiTime(form.actualEndLocal);
  if (parseTime(start) !== parseTime(original.actual_start_at)) body.actual_start_at = start;
  if (parseTime(end) !== parseTime(original.actual_end_at)) body.actual_end_at = end;
  return body;
}

export function correctionChanges(body: Record<string, unknown>) {
  return { status: body.status as string | undefined, actual_start_at: body.actual_start_at as string | undefined, actual_end_at: body.actual_end_at as string | undefined };
}

// ------------------------------------------------------------ reminders

export type ReminderState = "Fired" | "Failed" | "Disabled" | "Waiting";

export function reminderState(t: Pick<ScheduleTrigger, "fired_at" | "fire_error" | "enabled">): ReminderState {
  if (t.fire_error) return "Failed";
  if (t.fired_at) return "Fired";
  return t.enabled ? "Waiting" : "Disabled";
}

/** "15 min before start", "At end", "30 min after end", or a fixed time. */
export function describeReminderTiming(t: Pick<ScheduleTrigger, "offset_minutes" | "relative_to" | "trigger_at">): string {
  if (t.offset_minutes === null || t.offset_minutes === undefined) return t.trigger_at ? "At a fixed time" : "—";
  const anchor = t.relative_to === "end" ? "end" : "start";
  if (t.offset_minutes === 0) return `At ${anchor}`;
  return `${formatMinutes(t.offset_minutes)} ${t.offset_minutes < 0 ? "before" : "after"} ${anchor}`;
}

export interface ReminderForm { label: string; minutes: string; direction: "before" | "after"; relativeTo: "start" | "end"; message: string; requiresAck: boolean }

export function emptyReminderForm(): ReminderForm {
  return { label: "", minutes: "15", direction: "before", relativeTo: "start", message: "", requiresAck: false };
}

export function validateReminder(form: ReminderForm): string | null {
  if (!form.label.trim()) return "Give the reminder a label.";
  const n = Number(form.minutes);
  if (!Number.isInteger(n) || n < 0) return "Minutes must be a whole number, zero or more.";
  return null;
}

export function reminderBody(form: ReminderForm, scheduleItemId: string): Record<string, unknown> {
  const n = Number(form.minutes);
  return {
    schedule_item_id: scheduleItemId, trigger_type: "notification", label: form.label.trim(),
    offset_minutes: form.direction === "before" ? -n : n, relative_to: form.relativeTo, enabled: true,
    message_template: form.message.trim(), requires_acknowledgement: form.requiresAck, link_to_schedule_item: true,
  };
}

/** Reminders that will still fire for a schedule item: enabled and not yet fired. */
export function pendingReminders(triggers: ScheduleTrigger[], status: string): ScheduleTrigger[] {
  if (status === "Cancelled") return [];
  return triggers.filter(t => t.enabled && !t.fired_at);
}

// ----------------------------------------------------------- assignments

export type AssignmentState = "Pending" | "Active" | "Promoted";

export function assignmentState(qa: Pick<PlannedRecord, "lifecycle_state" | "linked_tasking_id" | "promoted_read_only">): AssignmentState {
  if (qa.linked_tasking_id || qa.promoted_read_only || qa.lifecycle_state === "Promoted") return "Promoted";
  return qa.lifecycle_state === "Pending" ? "Pending" : "Active";
}

export function isPromoted(qa: Pick<PlannedRecord, "linked_tasking_id" | "promoted_read_only" | "lifecycle_state">): boolean {
  return assignmentState(qa) === "Promoted";
}

export function canPromote(qa: Pick<PlannedRecord, "linked_tasking_id" | "promoted_read_only" | "lifecycle_state">): boolean {
  return !isPromoted(qa);
}

/** What does and does not carry over to the Operations Task (server rules, shown before confirming). */
export function promotionCarryOver(qa: Pick<PlannedRecord, "assigned_team_id" | "assigned_person_id" | "assigned_to">) {
  const carried = ["Title", "Summary (as the assignment text)", "Priority", "Status", "Location", "Due time"];
  const kept: string[] = [];
  if (qa.assigned_team_id) carried.push("Assigned team");
  else if (qa.assigned_person_id || qa.assigned_to) kept.push("Assignee (a person or free-text assignee stays on this assignment)");
  return { carried, kept };
}

export interface AssignmentForm {
  title: string; summary: string; priority: string; assigned_to: string; assigned_team_id: string; location: string; zone: string;
  scheduled_at: string; due_at: string; lifecycle_state: "Pending" | "Active"; recurring: boolean; recurrence_rule: string;
  recurrence_start_at: string; recurrence_end_at: string; schedule_item_id: string;
}

export function emptyAssignmentForm(scheduleItemId = ""): AssignmentForm {
  return { title: "", summary: "", priority: "Medium", assigned_to: "", assigned_team_id: "", location: "", zone: "", scheduled_at: "", due_at: "", lifecycle_state: "Active", recurring: false, recurrence_rule: "", recurrence_start_at: "", recurrence_end_at: "", schedule_item_id: scheduleItemId };
}

export function assignmentToForm(qa: PlannedRecord): AssignmentForm {
  return {
    title: qa.title, summary: qa.summary, priority: qa.priority || "Medium", assigned_to: qa.assigned_to, assigned_team_id: qa.assigned_team_id,
    location: qa.location, zone: qa.zone, scheduled_at: toLocalInput(qa.scheduled_at), due_at: toLocalInput(qa.due_at),
    lifecycle_state: qa.lifecycle_state === "Pending" ? "Pending" : "Active", recurring: qa.recurring, recurrence_rule: qa.recurrence_rule,
    recurrence_start_at: toLocalInput(qa.recurrence_start_at), recurrence_end_at: toLocalInput(qa.recurrence_end_at), schedule_item_id: qa.schedule_item_id,
  };
}

export function validateAssignment(form: AssignmentForm): string | null {
  if (!form.title.trim()) return "Title is required.";
  const dueErr = validateRange(toApiTime(form.scheduled_at), toApiTime(form.due_at), "Assignment");
  if (dueErr) return dueErr;
  if (form.recurring) {
    if (!form.recurrence_rule.trim()) return "Describe how often the assignment repeats.";
    const recErr = validateRange(toApiTime(form.recurrence_start_at), toApiTime(form.recurrence_end_at), "Recurrence");
    if (recErr) return recErr;
  }
  return null;
}

/** Create/patch body for a Quick Assignment. Recurrence fields are blanked when the toggle is off. */
export function assignmentBody(form: AssignmentForm): Record<string, unknown> {
  const rec = form.recurring;
  return {
    title: form.title.trim(), summary: form.summary.trim(), priority: form.priority, assigned_to: form.assigned_to.trim(),
    assigned_team_id: form.assigned_team_id, location: form.location.trim(), zone: form.zone.trim(),
    scheduled_at: toApiTime(form.scheduled_at), due_at: toApiTime(form.due_at), lifecycle_state: form.lifecycle_state,
    recurring: rec, recurrence_rule: rec ? form.recurrence_rule.trim() : "",
    recurrence_start_at: rec ? toApiTime(form.recurrence_start_at) : "", recurrence_end_at: rec ? toApiTime(form.recurrence_end_at) : "",
    missed_occurrence_behavior: rec ? MISSED_OCCURRENCE_LATEST_OVERDUE : "",
    schedule_item_id: form.schedule_item_id,
  };
}

/** Quick Assignments linked to a schedule activity: many may point at one activity. */
export function linkedAssignments(activity: Pick<PlannedRecord, "record_id" | "quick_assignment_id">, all: PlannedRecord[]): PlannedRecord[] {
  return all.filter(qa => qa.schedule_item_id === activity.record_id || qa.record_id === activity.quick_assignment_id || qa.source_id === activity.record_id);
}

/** An assignment's source activity, resolved by the activity's record id. */
export function sourceActivity(qa: Pick<PlannedRecord, "schedule_item_id" | "source_id" | "source_tool">, activities: PlannedRecord[]): PlannedRecord | undefined {
  const key = qa.schedule_item_id || (qa.source_tool === "promotions/schedule" ? qa.source_id : "");
  return key ? activities.find(a => a.record_id === key) : undefined;
}

// ------------------------------------------------------------------ clock

export function formatClock(nowMs: number): string {
  return new Date(nowMs).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}
