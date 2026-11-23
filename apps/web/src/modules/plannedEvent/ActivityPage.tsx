import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { describeError, staleCurrent, usePlannedRecords, usePlannedTeams, useReminderWrites, useScheduleItems, useScheduleTriggers, useScheduleWrites } from "./hooks";
import {
  ACTION_LABEL, activityBody, activityPatch, activityToForm, allowedActions, assignmentState, attention, cancelBody, correctionBody, correctionChanges,
  delayBody, emptyActivityForm, emptyReminderForm, describeReminderTiming, formatMinutes, isTerminal, linkedAssignments, pendingReminders, plainActionBody,
  plannedVsActual, reminderBody, reminderState, resumeTarget, SCHEDULE_STATUSES, toLocalInput, validateActivity, validateCancel, validateCorrection,
  validateDelay, validateReminder, varianceLabel, type ActivityForm, type CorrectionForm, type PlannedRecord, type ReasonInput, type ReminderForm, type ScheduleAction, type ScheduleTrigger,
} from "./model";
import { Definition, ErrorNote, Field, useNow } from "./ui";

type Panel = null | "delay" | "cancel" | "correct" | "delete";

export default function ActivityPage() {
  const { recordId } = useParams();
  return recordId === "new" ? <CreateActivity /> : <ActivityDetail id={Number(recordId)} />;
}

function ResponsibilityFields({ form, set, incidentId }: { form: ActivityForm; set: (patch: Partial<ActivityForm>) => void; incidentId: string }) {
  const teams = usePlannedTeams(incidentId);
  return (
    <>
      <Field label="Responsible team" htmlFor="pe-team">
        <select id="pe-team" value={form.assigned_team_id} onChange={e => {
          const team = teams.data?.find(t => String(t.int_id) === e.target.value);
          set({ assigned_team_id: e.target.value, assigned_to: team ? String(team.name ?? "") : form.assigned_to });
        }}>
          <option value="">No team</option>
          {(teams.data ?? []).map(t => <option key={t.int_id} value={t.int_id}>{String(t.name ?? `Team #${t.int_id}`)}</option>)}
        </select>
      </Field>
      <Field label="Responsible (name)" htmlFor="pe-assigned"><input id="pe-assigned" value={form.assigned_to} onChange={e => set({ assigned_to: e.target.value })} /></Field>
    </>
  );
}

function ActivityFields({ form, set, incidentId, kinds }: { form: ActivityForm; set: (patch: Partial<ActivityForm>) => void; incidentId: string; kinds: string[] }) {
  return (
    <div className="pe-form">
      <Field label="Name *" htmlFor="pe-name"><input id="pe-name" required value={form.name} onChange={e => set({ name: e.target.value })} /></Field>
      <Field label="Kind" htmlFor="pe-kind">
        <input id="pe-kind" list="pe-kinds" value={form.kind} onChange={e => set({ kind: e.target.value })} />
        <datalist id="pe-kinds">{[...new Set(["Milestone", ...kinds])].map(k => <option key={k} value={k} />)}</datalist>
      </Field>
      <Field label="Planned start" htmlFor="pe-start"><input id="pe-start" type="datetime-local" value={form.starts_at} onChange={e => set({ starts_at: e.target.value })} /></Field>
      <Field label="Planned end" htmlFor="pe-end"><input id="pe-end" type="datetime-local" value={form.ends_at} onChange={e => set({ ends_at: e.target.value })} /></Field>
      <ResponsibilityFields form={form} set={set} incidentId={incidentId} />
      <Field label="Owner" htmlFor="pe-owner"><input id="pe-owner" value={form.owner} onChange={e => set({ owner: e.target.value })} /></Field>
      <Field label="Location" htmlFor="pe-loc"><input id="pe-loc" value={form.location} onChange={e => set({ location: e.target.value })} /></Field>
      <Field label="Zone" htmlFor="pe-zone"><input id="pe-zone" value={form.zone} onChange={e => set({ zone: e.target.value })} /></Field>
      <Field label="Notes" wide htmlFor="pe-notes"><textarea id="pe-notes" value={form.notes} onChange={e => set({ notes: e.target.value })} /></Field>
    </div>
  );
}

function CreateActivity() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const schedule = useScheduleItems(incidentId!);
  const { save } = useScheduleWrites(incidentId!);
  const [form, setForm] = useState<ActivityForm>(emptyActivityForm);
  const [error, setError] = useState<string | null>(null);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problem = validateActivity(form);
    if (problem) return setError(problem);
    setError(null);
    save.mutate({ body: { ...activityBody(form), status: "Scheduled" } }, { onSuccess: saved => navigate(`/toolkits/planned-event/schedule/${saved.id}`, { replace: true }), onError: err => setError(describeError(err)) });
  };
  return (
    <form onSubmit={submit} className="pe-panel">
      <div className="pe-toolbar"><h3>New activity</h3><Link to="/toolkits/planned-event/schedule">Back to schedule</Link></div>
      <ActivityFields form={form} set={p => setForm(f => ({ ...f, ...p }))} incidentId={incidentId!} kinds={(schedule.data ?? []).map(i => i.kind)} />
      <ErrorNote message={error} />
      <div className="pe-actions"><button type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Create activity"}</button></div>
    </form>
  );
}

function ActivityDetail({ id }: { id: number }) {
  const { incidentId, user } = useSession();
  const by = user.display_name || user.username;
  const now = useNow();
  const navigate = useNavigate();
  const schedule = useScheduleItems(incidentId!);
  const triggers = useScheduleTriggers(incidentId!);
  const assignments = usePlannedRecords(incidentId!, "quick-assignments");
  const writes = useScheduleWrites(incidentId!);
  const reminderWrites = useReminderWrites(incidentId!);
  const item = schedule.data?.find(i => i.id === id);
  const [panel, setPanel] = useState<Panel>(null);
  const [form, setForm] = useState<ActivityForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<PlannedRecord | null>(null);

  // Seed the edit form once per loaded revision, never over unsaved edits of the same revision.
  const revision = item?.revision;
  useEffect(() => { if (item) setForm(activityToForm(item)); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [item?.id, revision]);

  if (schedule.isError) return <p className="error" role="alert">Could not load this activity. Refresh to retry.</p>;
  if (schedule.isPending) return <p role="status">Loading…</p>;
  if (!item || !form) return <p>Activity not found. <Link to="/toolkits/planned-event/schedule">Back to schedule</Link></p>;

  const flag = attention(item, now);
  const pva = plannedVsActual(item);
  const terminal = isTerminal(item.status);
  const itemTriggers = (triggers.data ?? []).filter(t => t.schedule_item_id === item.record_id);
  const willFire = pendingReminders(itemTriggers, item.status);
  const linked = linkedAssignments(item, assignments.data ?? []);

  const onFail = (err: unknown) => {
    const current = staleCurrent(err);
    if (current) { setConflict(current); setError(null); } else setError(describeError(err));
  };
  const reload = () => { setConflict(null); setError(null); setPanel(null); void schedule.refetch(); void triggers.refetch(); };
  const run = (action: ScheduleAction, body: Record<string, unknown>) => {
    setError(null);
    writes.act.mutate({ recordId: item.id, action, body }, { onSuccess: () => { setPanel(null); setConflict(null); }, onError: onFail });
  };

  const saveDetails = (e: FormEvent) => {
    e.preventDefault();
    const problem = validateActivity(form);
    if (problem) return setError(problem);
    const patch = activityPatch(item, form);
    if (Object.keys(patch).length === 0) return setError("Nothing has changed.");
    setError(null);
    writes.save.mutate({ recordId: item.id, body: { ...patch, expected_revision: item.revision, changed_by: by } }, { onSuccess: () => setConflict(null), onError: onFail });
  };

  return (
    <>
      <div className="pe-toolbar">
        <h3>{item.title || `Activity #${item.id}`} <StatusPill domain="planned-schedule" statusKey={item.status} /></h3>
        <Link to="/toolkits/planned-event/schedule">Back to schedule</Link>
      </div>
      {flag && <p><span className={"pe-flag" + (flag.kind === "starting-soon" ? " pe-flag-soft" : "")}>{flag.label}</span> Status never changes on its own — record what actually happened below.</p>}
      {conflict && (
        <div className="pe-conflict" role="alert">
          <p><strong>This activity was changed by another operator.</strong> It is now <StatusPill domain="planned-schedule" statusKey={conflict.status} /> (revision {conflict.revision}). Your change was not saved.</p>
          <button onClick={reload}>Reload latest</button>
        </div>
      )}
      <ErrorNote message={error} />

      <section className="pe-panel">
        <h3>Event-day actions</h3>
        <div className="pe-actions">
          {allowedActions(item.status).map(action => {
            const needsReason = action === "delay" || action === "cancel";
            return (
              <button key={action} className={action === "cancel" ? "secondary" : undefined} disabled={writes.act.isPending}
                onClick={() => needsReason ? setPanel(action as Panel) : run(action, plainActionBody(item.revision, by))}>
                {action === "resume" ? `Resume (back to ${resumeTarget(item)})` : ACTION_LABEL[action]}
              </button>
            );
          })}
          <button className="secondary" onClick={() => setPanel(panel === "correct" ? null : "correct")}>{terminal ? "Reopen or correct…" : "Correct a recorded time…"}</button>
        </div>
        {terminal && <p className="pe-note">{item.status} activities have no routine way out. Use a logged correction to reopen one.</p>}
        {panel === "delay" && <ReasonPanel kind="delay" endsAt={item.ends_at} busy={writes.act.isPending} onCancel={() => setPanel(null)}
          onSubmit={input => { const err = validateDelay(input, item.ends_at); if (err) return setError(err); run("delay", delayBody(input, item.revision, by)); }} />}
        {panel === "cancel" && <ReasonPanel kind="cancel" endsAt={item.ends_at} busy={writes.act.isPending} reminderCount={willFire.length} onCancel={() => setPanel(null)}
          onSubmit={input => { const err = validateCancel(input.reason); if (err) return setError(err); run("cancel", cancelBody(input.reason, item.revision, by)); }} />}
        {panel === "correct" && <CorrectionPanel item={item} busy={writes.correct.isPending} onCancel={() => setPanel(null)}
          onSubmit={cf => {
            const body = correctionBody(item, cf, item.revision, by);
            const err = validateCorrection(cf.reason, correctionChanges(body));
            if (err) return setError(err);
            setError(null);
            writes.correct.mutate({ recordId: item.id, body }, { onSuccess: () => { setPanel(null); setConflict(null); }, onError: onFail });
          }} />}
        {item.status === "Delayed" && item.delay_reason && <p className="pe-note"><strong>Delay reason:</strong> {item.delay_reason}</p>}
        {item.status === "Cancelled" && item.cancellation_reason && <p className="pe-note"><strong>Cancellation reason:</strong> {item.cancellation_reason}</p>}
      </section>

      <section className="pe-panel">
        <h3>Planned vs. actual</h3>
        <Definition rows={[
          ["Planned", `${formatDateTime(item.starts_at)} – ${formatDateTime(item.ends_at)}`],
          ["Actual", `${formatDateTime(item.actual_start_at)} – ${item.actual_end_at ? formatDateTime(item.actual_end_at) : item.actual_start_at ? "still running" : "—"}`],
        ]} />
        <div className="pe-variance" style={{ marginTop: 12 }}>
          <div>Start<b>{varianceLabel(pva.startVarianceMin, "early", "late")}</b></div>
          <div>End<b>{varianceLabel(pva.endVarianceMin, "early", "late")}</b></div>
          <div>Planned length<b>{pva.plannedDurationMin === null ? "—" : formatMinutes(pva.plannedDurationMin)}</b></div>
          <div>Actual length<b>{pva.actualDurationMin === null ? "—" : formatMinutes(pva.actualDurationMin)}</b></div>
        </div>
      </section>

      <form className="pe-panel" onSubmit={saveDetails}>
        <h3>Details</h3>
        <ActivityFields form={form} set={p => setForm(f => ({ ...f!, ...p }))} incidentId={incidentId!} kinds={(schedule.data ?? []).map(i => i.kind)} />
        <div className="pe-actions"><button type="submit" disabled={writes.save.isPending}>{writes.save.isPending ? "Saving…" : "Save changes"}</button></div>
        <p className="pe-note">Changing the planned start re-times any reminder that follows this activity.</p>
      </form>

      <Reminders item={item} triggers={itemTriggers} writes={reminderWrites} />

      <section className="pe-panel">
        <h3>Assignments</h3>
        {linked.length === 0 ? <p>No assignments are linked to this activity.</p> : (
          <ul className="pe-list">{linked.map(a => (
            <li key={a.id}><Link to={`/toolkits/planned-event/assignments/${a.id}`}>{a.title || `Assignment #${a.id}`}</Link><StatusPill domain="planned-assignment" statusKey={assignmentState(a)} /></li>
          ))}</ul>
        )}
        <div className="pe-actions">
          {!item.quick_assignment_id && !terminal && (
            <button className="secondary" disabled={writes.createAssignment.isPending}
              onClick={() => writes.createAssignment.mutate(item.id, { onSuccess: r => navigate(`/toolkits/planned-event/assignments/${r.quick_assignment.id}`), onError: onFail })}>
              Create assignment from this activity
            </button>
          )}
          <Link to={`/toolkits/planned-event/assignments/new?activity=${encodeURIComponent(item.record_id)}`}>Add another assignment</Link>
        </div>
        <p className="pe-note">Several assignments can support one activity. An assignment's own status and promotion stay independent of the activity.</p>
      </section>

      <section className="pe-panel">
        <h3>Remove</h3>
        {panel === "delete" ? (
          <div className="pe-actions">
            <span>Delete this activity? Cancelling keeps the record; deleting removes it from the schedule.</span>
            <button disabled={writes.remove.isPending} onClick={() => writes.remove.mutate(item.id, { onSuccess: () => navigate("/toolkits/planned-event/schedule"), onError: onFail })}>Delete activity</button>
            <button className="secondary" onClick={() => setPanel(null)}>Keep</button>
          </div>
        ) : <button className="secondary" onClick={() => setPanel("delete")}>Delete activity…</button>}
      </section>
    </>
  );
}

function ReasonPanel({ kind, onSubmit, onCancel, busy, endsAt, reminderCount = 0 }: { kind: "delay" | "cancel"; onSubmit: (input: ReasonInput) => void; onCancel: () => void; busy: boolean; endsAt: string; reminderCount?: number }) {
  const [reason, setReason] = useState("");
  const [revised, setRevised] = useState("");
  return (
    <form className="pe-form" style={{ marginTop: 14 }} onSubmit={e => { e.preventDefault(); onSubmit({ reason, revisedStartLocal: revised }); }}>
      <Field label={kind === "delay" ? "Reason for the delay *" : "Reason for cancelling *"} wide htmlFor="pe-reason"><textarea id="pe-reason" required value={reason} onChange={e => setReason(e.target.value)} /></Field>
      {kind === "delay" && <Field label="Revised start (optional)" htmlFor="pe-revised"><input id="pe-revised" type="datetime-local" max={toLocalInput(endsAt) || undefined} value={revised} onChange={e => setRevised(e.target.value)} /></Field>}
      {kind === "cancel" && reminderCount > 0 && <p className="pe-wide pe-note">{reminderCount} reminder{reminderCount === 1 ? "" : "s"} that have not fired will be disabled.</p>}
      <div className="pe-actions pe-wide">
        <button type="submit" disabled={busy}>{kind === "delay" ? "Mark delayed" : "Cancel activity"}</button>
        <button type="button" className="secondary" onClick={onCancel}>Back</button>
      </div>
    </form>
  );
}

function CorrectionPanel({ item, onSubmit, onCancel, busy }: { item: PlannedRecord; onSubmit: (f: CorrectionForm) => void; onCancel: () => void; busy: boolean }) {
  const [form, setForm] = useState<CorrectionForm>({ reason: "", status: item.status, actualStartLocal: toLocalInput(item.actual_start_at), actualEndLocal: toLocalInput(item.actual_end_at) });
  return (
    <form className="pe-form" style={{ marginTop: 14 }} onSubmit={e => { e.preventDefault(); onSubmit(form); }}>
      <p className="pe-wide pe-note">Corrections are logged with your reason. Use them to reopen a completed or cancelled activity or to fix an actual time recorded wrong. Planned times and everything else are edited under Details.</p>
      <Field label="Status" htmlFor="pe-c-status"><select id="pe-c-status" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>{SCHEDULE_STATUSES.map(s => <option key={s}>{s}</option>)}</select></Field>
      <span />
      <Field label="Actual start" htmlFor="pe-c-start"><input id="pe-c-start" type="datetime-local" value={form.actualStartLocal} onChange={e => setForm({ ...form, actualStartLocal: e.target.value })} /></Field>
      <Field label="Actual end" htmlFor="pe-c-end"><input id="pe-c-end" type="datetime-local" value={form.actualEndLocal} onChange={e => setForm({ ...form, actualEndLocal: e.target.value })} /></Field>
      <Field label="Reason for the correction *" wide htmlFor="pe-c-reason"><textarea id="pe-c-reason" required value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} /></Field>
      <div className="pe-actions pe-wide"><button type="submit" disabled={busy}>Record correction</button><button type="button" className="secondary" onClick={onCancel}>Back</button></div>
    </form>
  );
}

function Reminders({ item, triggers, writes }: { item: PlannedRecord; triggers: ScheduleTrigger[]; writes: ReturnType<typeof useReminderWrites> }) {
  const [form, setForm] = useState<ReminderForm>(emptyReminderForm);
  const [error, setError] = useState<string | null>(null);
  const hasAnchor = Boolean(item.starts_at || item.ends_at);
  const add = (e: FormEvent) => {
    e.preventDefault();
    const problem = validateReminder(form);
    if (problem) return setError(problem);
    setError(null);
    writes.create.mutate(reminderBody(form, item.record_id), { onSuccess: () => setForm(emptyReminderForm()), onError: err => setError(describeError(err)) });
  };
  return (
    <section className="pe-panel">
      <h3>Reminders</h3>
      {triggers.length === 0 ? <p>No reminders set for this activity.</p> : (
        <ul className="pe-list">
          {triggers.map(t => (
            <li key={t.id}>
              <span><strong>{t.label || `Reminder #${t.id}`}</strong> — {describeReminderTiming(t)}{t.trigger_at ? ` (${formatDateTime(t.trigger_at)})` : ""}</span>
              <span>{reminderState(t)}</span>
              {!t.fired_at && <button className="secondary" disabled={writes.update.isPending} onClick={() => writes.update.mutate({ recordId: t.id, body: { enabled: !t.enabled } }, { onError: err => setError(describeError(err)) })}>{t.enabled ? "Disable" : "Enable"}</button>}
              <button className="secondary" disabled={writes.remove.isPending} onClick={() => writes.remove.mutate(t, { onError: err => setError(describeError(err)) })}>Remove</button>
            </li>
          ))}
        </ul>
      )}
      <form className="pe-form" onSubmit={add}>
        <Field label="Label *" htmlFor="pe-r-label"><input id="pe-r-label" value={form.label} onChange={e => setForm({ ...form, label: e.target.value })} /></Field>
        <Field label="Minutes" htmlFor="pe-r-min"><input id="pe-r-min" inputMode="numeric" value={form.minutes} onChange={e => setForm({ ...form, minutes: e.target.value })} /></Field>
        <Field label="Before or after" htmlFor="pe-r-dir"><select id="pe-r-dir" value={form.direction} onChange={e => setForm({ ...form, direction: e.target.value as ReminderForm["direction"] })}><option value="before">Before</option><option value="after">After</option></select></Field>
        <Field label="Relative to" htmlFor="pe-r-rel"><select id="pe-r-rel" value={form.relativeTo} onChange={e => setForm({ ...form, relativeTo: e.target.value as ReminderForm["relativeTo"] })}><option value="start">Activity start</option><option value="end">Activity end</option></select></Field>
        <Field label="Message" wide htmlFor="pe-r-msg"><input id="pe-r-msg" value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} /></Field>
        <label className="pe-wide"><input type="checkbox" checked={form.requiresAck} onChange={e => setForm({ ...form, requiresAck: e.target.checked })} /> Requires acknowledgement</label>
        <div className="pe-actions pe-wide"><button type="submit" disabled={writes.create.isPending || !hasAnchor}>Add reminder</button></div>
      </form>
      {!hasAnchor && <p className="pe-note">Give the activity a planned start or end before adding a relative reminder.</p>}
      <ErrorNote message={error} />
      <p className="pe-note">Reminders follow the activity: they move when its planned start changes, and cancelling the activity disables any that have not fired.</p>
    </section>
  );
}
