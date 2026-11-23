import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
function loadTs(path) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", compiled)(id => require(id), module, module.exports);
  return module.exports;
}
const m = loadTs("../src/modules/plannedEvent/model.ts");
const at = (iso) => new Date(iso).getTime();

test("event-day actions follow the server status matrix", () => {
  assert.deepEqual(m.allowedActions("Scheduled"), ["start", "delay", "cancel"]);
  assert.deepEqual(m.allowedActions("In Progress"), ["complete", "delay", "cancel"]);
  assert.deepEqual(m.allowedActions("Delayed"), ["resume", "cancel"]);
  assert.deepEqual(m.allowedActions("Completed"), []);
  assert.deepEqual(m.allowedActions("Cancelled"), []);
  assert.equal(m.isTerminal("Completed"), true);
  assert.equal(m.isTerminal("Delayed"), false);
});

test("resume returns to In Progress only if the activity actually started", () => {
  assert.equal(m.resumeTarget({ actual_start_at: "2026-10-20T14:00:00Z" }), "In Progress");
  assert.equal(m.resumeTarget({ actual_start_at: "" }), "Scheduled");
});

test("attention is computed, never a status", () => {
  const now = at("2026-10-20T12:00:00Z");
  assert.equal(m.attention({ status: "Scheduled", starts_at: "2026-10-20T11:30:00Z", ends_at: "" }, now).kind, "overdue-start");
  assert.equal(m.attention({ status: "Scheduled", starts_at: "2026-10-20T12:30:00Z", ends_at: "" }, now).kind, "starting-soon");
  assert.equal(m.attention({ status: "Scheduled", starts_at: "2026-10-20T15:00:00Z", ends_at: "" }, now), null);
  assert.equal(m.attention({ status: "In Progress", starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T11:00:00Z" }, now).kind, "past-end");
  assert.equal(m.attention({ status: "In Progress", starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T13:00:00Z" }, now), null);
  assert.equal(m.attention({ status: "Delayed", starts_at: "", ends_at: "" }, now).kind, "delayed");
  for (const status of ["Completed", "Cancelled"]) assert.equal(m.attention({ status, starts_at: "2020-01-01T00:00:00Z", ends_at: "2020-01-01T01:00:00Z" }, now), null);
});

test("planned vs actual reports variance in whole minutes, signed late/early", () => {
  const v = m.plannedVsActual({ starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T11:00:00Z", actual_start_at: "2026-10-20T10:12:00Z", actual_end_at: "2026-10-20T11:05:00Z" });
  assert.deepEqual(v, { startVarianceMin: 12, endVarianceMin: 5, plannedDurationMin: 60, actualDurationMin: 53 });
  assert.equal(m.varianceLabel(12), "12 min late");
  assert.equal(m.varianceLabel(-65), "1 h 5 min early");
  assert.equal(m.varianceLabel(0), "On time");
  assert.equal(m.varianceLabel(null), "—");
  assert.equal(m.plannedVsActual({ starts_at: "", ends_at: "", actual_start_at: "", actual_end_at: "" }).startVarianceMin, null);
});

test("reasons are mandatory for delay, cancel and correction", () => {
  assert.match(m.validateDelay({ reason: "  " }, ""), /reason/i);
  assert.equal(m.validateDelay({ reason: "Rain" }, ""), null);
  assert.match(m.validateDelay({ reason: "Rain", revisedStartLocal: "2026-10-20T14:00" }, "2026-10-20T10:00:00Z"), /revised start/i);
  assert.match(m.validateCancel(""), /reason/i);
  assert.equal(m.validateCancel("Weather"), null);
  assert.match(m.validateCorrection("", { status: "Scheduled" }), /reason/i);
  assert.match(m.validateCorrection("typo", {}), /change/i);
  assert.match(m.validateCorrection("typo", { actual_start_at: "2026-10-20T12:00:00Z", actual_end_at: "2026-10-20T11:00:00Z" }), /actual end/i);
  assert.equal(m.validateCorrection("typo", { status: "Scheduled" }), null);
});

test("action bodies carry the revision and trimmed reasons", () => {
  assert.deepEqual(m.plainActionBody(3, "Pat"), { expected_revision: 3, changed_by: "Pat" });
  assert.deepEqual(m.cancelBody(" Rain ", 4, "Pat"), { expected_revision: 4, changed_by: "Pat", cancellation_reason: "Rain" });
  const delay = m.delayBody({ reason: " Late truck ", revisedStartLocal: "" }, 2, "Pat");
  assert.equal(delay.delay_reason, "Late truck");
  assert.equal("revised_start_at" in delay, false);
  assert.match(m.delayBody({ reason: "x", revisedStartLocal: "2026-10-20T14:00" }, 2, "Pat").revised_start_at, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
});

test("corrections send only what changed", () => {
  const item = { status: "Completed", actual_start_at: "2026-10-20T10:00:00Z", actual_end_at: "2026-10-20T11:00:00Z" };
  const same = m.correctionBody(item, { reason: "r", status: "Completed", actualStartLocal: m.toLocalInput(item.actual_start_at), actualEndLocal: m.toLocalInput(item.actual_end_at) }, 5, "Pat");
  assert.deepEqual(Object.keys(same).sort(), ["corrected_by", "expected_revision", "reason"]);
  const reopen = m.correctionBody(item, { reason: "r", status: "In Progress", actualStartLocal: m.toLocalInput(item.actual_start_at), actualEndLocal: "" }, 5, "Pat");
  assert.equal(reopen.status, "In Progress");
  assert.equal(reopen.actual_end_at, "");
  assert.equal("actual_start_at" in reopen, false);
});

test("timestamps round-trip through datetime-local without sub-second precision", () => {
  const api = m.toApiTime("2026-10-20T14:30");
  assert.match(api, /^\d{4}-\d\d-\d\dT\d\d:\d\d:00Z$/);
  assert.equal(m.toLocalInput(api), "2026-10-20T14:30");
  assert.equal(m.toApiTime(""), "");
  assert.equal(m.toLocalInput(""), "");
  assert.equal(m.toLocalInput("not a date"), "");
});

test("activity patch includes only changed fields and treats equal instants as unchanged", () => {
  const item = { title: "Gates", kind: "Milestone", starts_at: "2026-10-20T14:30:00Z", ends_at: "", location: "", zone: "", owner: "", assigned_to: "", assigned_team_id: "", summary: "" };
  const form = m.activityToForm(item);
  assert.deepEqual(m.activityPatch(item, form), {});
  assert.deepEqual(m.activityPatch(item, { ...form, name: "Gates open", location: "North" }), { name: "Gates open", location: "North" });
  assert.match(m.validateActivity({ ...form, name: " " }), /name/i);
  assert.match(m.validateActivity({ ...form, starts_at: "2026-10-20T15:00", ends_at: "2026-10-20T14:00" }), /end/i);
});

test("reminders describe timing, state, and which will still fire", () => {
  assert.equal(m.describeReminderTiming({ offset_minutes: -15, relative_to: "start", trigger_at: "" }), "15 min before start");
  assert.equal(m.describeReminderTiming({ offset_minutes: 0, relative_to: "end", trigger_at: "" }), "At end");
  assert.equal(m.describeReminderTiming({ offset_minutes: 90, relative_to: "end", trigger_at: "" }), "1 h 30 min after end");
  assert.equal(m.describeReminderTiming({ offset_minutes: null, relative_to: "start", trigger_at: "2026-10-20T10:00:00Z" }), "At a fixed time");
  assert.equal(m.reminderState({ enabled: true, fired_at: "", fire_error: "" }), "Waiting");
  assert.equal(m.reminderState({ enabled: false, fired_at: "", fire_error: "" }), "Disabled");
  assert.equal(m.reminderState({ enabled: true, fired_at: "x", fire_error: "" }), "Fired");
  assert.equal(m.reminderState({ enabled: true, fired_at: "", fire_error: "boom" }), "Failed");
  const ts = [{ enabled: true, fired_at: "" }, { enabled: true, fired_at: "x" }, { enabled: false, fired_at: "" }];
  assert.equal(m.pendingReminders(ts, "Scheduled").length, 1);
  assert.equal(m.pendingReminders(ts, "Cancelled").length, 0);
  assert.equal(m.validateReminder({ ...m.emptyReminderForm(), label: "" }) !== null, true);
  assert.equal(m.validateReminder({ ...m.emptyReminderForm(), label: "Heads up", minutes: "-3" }) !== null, true);
  assert.equal(m.reminderBody({ ...m.emptyReminderForm(), label: "Heads up" }, "INC-PLAN-SCHEDULE-1").offset_minutes, -15);
  assert.equal(m.reminderBody({ ...m.emptyReminderForm(), label: "After", direction: "after", relativeTo: "end" }, "S").relative_to, "end");
});

test("assignment lifecycle: promoted is final and read-only", () => {
  assert.equal(m.assignmentState({ lifecycle_state: "", linked_tasking_id: "", promoted_read_only: false }), "Active");
  assert.equal(m.assignmentState({ lifecycle_state: "Pending", linked_tasking_id: "", promoted_read_only: false }), "Pending");
  assert.equal(m.assignmentState({ lifecycle_state: "Active", linked_tasking_id: "7", promoted_read_only: true }), "Promoted");
  assert.equal(m.canPromote({ lifecycle_state: "Active", linked_tasking_id: "", promoted_read_only: false }), true);
  assert.equal(m.canPromote({ lifecycle_state: "Promoted", linked_tasking_id: "", promoted_read_only: false }), false);
});

test("promotion preview: team carries over, person or free text stays behind", () => {
  const team = m.promotionCarryOver({ assigned_team_id: "4", assigned_person_id: "", assigned_to: "Team 4" });
  assert.ok(team.carried.includes("Assigned team")); assert.equal(team.kept.length, 0);
  const person = m.promotionCarryOver({ assigned_team_id: "", assigned_person_id: "p1", assigned_to: "Pat" });
  assert.equal(person.carried.includes("Assigned team"), false); assert.equal(person.kept.length, 1);
  assert.equal(m.promotionCarryOver({ assigned_team_id: "", assigned_person_id: "", assigned_to: "" }).kept.length, 0);
});

test("recurring assignment validation and body", () => {
  const base = { ...m.emptyAssignmentForm(), title: "Check gates" };
  assert.equal(m.validateAssignment(base), null);
  assert.match(m.validateAssignment({ ...base, recurring: true, recurrence_rule: " " }), /repeats/i);
  assert.match(m.validateAssignment({ ...base, recurring: true, recurrence_rule: "Hourly", recurrence_start_at: "2026-10-20T15:00", recurrence_end_at: "2026-10-20T14:00" }), /recurrence/i);
  assert.match(m.validateAssignment({ ...base, title: "" }), /title/i);
  const off = m.assignmentBody({ ...base, recurrence_rule: "Hourly" });
  assert.equal(off.recurring, false); assert.equal(off.recurrence_rule, ""); assert.equal(off.missed_occurrence_behavior, "");
  const on = m.assignmentBody({ ...base, recurring: true, recurrence_rule: " Hourly " });
  assert.equal(on.recurrence_rule, "Hourly"); assert.equal(on.missed_occurrence_behavior, "latest_overdue");
});

test("many assignments may link to one activity; source resolves by record id", () => {
  const activity = { record_id: "INC-PLAN-SCHEDULE-1", quick_assignment_id: "INC-PLAN-QA-2" };
  const all = [
    { record_id: "INC-PLAN-QA-1", schedule_item_id: "INC-PLAN-SCHEDULE-1", source_id: "" },
    { record_id: "INC-PLAN-QA-2", schedule_item_id: "", source_id: "INC-PLAN-SCHEDULE-1" },
    { record_id: "INC-PLAN-QA-3", schedule_item_id: "INC-PLAN-SCHEDULE-9", source_id: "" },
  ];
  assert.deepEqual(m.linkedAssignments(activity, all).map(a => a.record_id), ["INC-PLAN-QA-1", "INC-PLAN-QA-2"]);
  const acts = [{ record_id: "INC-PLAN-SCHEDULE-1", title: "Gates" }];
  assert.equal(m.sourceActivity({ schedule_item_id: "INC-PLAN-SCHEDULE-1", source_id: "", source_tool: "" }, acts).title, "Gates");
  assert.equal(m.sourceActivity({ schedule_item_id: "", source_id: "INC-PLAN-SCHEDULE-1", source_tool: "promotions/schedule" }, acts).title, "Gates");
  assert.equal(m.sourceActivity({ schedule_item_id: "", source_id: "x", source_tool: "other" }, acts), undefined);
});
