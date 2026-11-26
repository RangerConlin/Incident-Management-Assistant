import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { describeError, usePlannedRecords, usePlannedTeams, usePlannedWrites, useScheduleItems } from "./hooks";
import {
  assignmentBody, assignmentState, assignmentToForm, canPromote, emptyAssignmentForm, MISSED_OCCURRENCE_LATEST_OVERDUE, promotionCarryOver,
  sourceActivity, validateAssignment, type AssignmentForm, type PlannedRecord,
} from "./model";
import { Definition, ErrorNote, Field } from "./ui";

export default function AssignmentPage() {
  const { recordId } = useParams();
  const [search] = useSearchParams();
  const { incidentId } = useSession();
  const query = usePlannedRecords(incidentId!, "quick-assignments");
  const isNew = recordId === "new";
  const record = isNew ? undefined : query.data?.find(r => String(r.id) === recordId);
  if (!isNew && query.isError) return <p className="error" role="alert">Could not load this assignment. Refresh to retry.</p>;
  if (!isNew && query.isPending) return <p role="status">Loading…</p>;
  if (!isNew && !record) return <p>Assignment not found. <Link to="/toolkits/planned-event/assignments">Back to assignments</Link></p>;
  return <AssignmentEditor key={record ? `${record.id}-${record.updated_at}` : "new"} record={record} presetActivity={search.get("activity") ?? ""} />;
}

function AssignmentEditor({ record, presetActivity }: { record?: PlannedRecord; presetActivity: string }) {
  const { incidentId, user } = useSession();
  const by = user.display_name || user.username;
  const navigate = useNavigate();
  const writes = usePlannedWrites(incidentId!, "quick-assignments");
  const schedule = useScheduleItems(incidentId!);
  const teams = usePlannedTeams(incidentId!);
  const [form, setForm] = useState<AssignmentForm>(() => (record ? assignmentToForm(record) : emptyAssignmentForm(presetActivity)));
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const readOnly = record ? assignmentState(record) === "Promoted" : false;
  const set = (patch: Partial<AssignmentForm>) => setForm(f => ({ ...f, ...patch }));
  const activity = record ? sourceActivity(record, schedule.data ?? []) : (schedule.data ?? []).find(a => a.record_id === form.schedule_item_id);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problem = validateAssignment(form);
    if (problem) return setError(problem);
    setError(null);
    const body = assignmentBody(form);
    if (!record) {
      // A new assignment started from an activity records that source so the link is visible from both sides.
      const source = (schedule.data ?? []).find(a => a.record_id === form.schedule_item_id);
      if (source) Object.assign(body, { source_type: "planned_schedule_item", source_id: source.record_id, source_label: source.title, source_tool: "promotions/schedule" });
    }
    writes.save.mutate({ recordId: record?.id, body }, { onSuccess: saved => { if (!record) navigate(`/toolkits/planned-event/assignments/${saved.id}`, { replace: true }); }, onError: err => setError(describeError(err)) });
  };

  const promote = () => record && writes.promote.mutate({ recordId: record.id, by }, { onSuccess: () => setConfirming(false), onError: err => { setConfirming(false); setError(describeError(err)); } });
  const carry = record ? promotionCarryOver(record) : null;

  return (
    <>
      <div className="pe-toolbar">
        <h3>{record ? record.title || `Assignment #${record.id}` : "New assignment"} {record && <StatusPill domain="planned-assignment" statusKey={assignmentState(record)} />}</h3>
        <Link to="/toolkits/planned-event/assignments">Back to assignments</Link>
      </div>
      {record && readOnly && (
        <div className="pe-readonly">
          <p><strong>Promoted to Operations{record.linked_tasking_id ? <> as <Link to={`/ops/tasks/${record.linked_tasking_id}`}>Task #{record.linked_tasking_id}</Link></> : ""}.</strong> This assignment is now read-only. Manage the work from the Operations task.</p>
          <Definition rows={[["Promoted", formatDateTime(record.promoted_at)], ["Promoted by", record.promoted_by || "—"]]} />
        </div>
      )}
      <ErrorNote message={error} />
      <form className="pe-panel" onSubmit={submit}>
        <fieldset disabled={readOnly} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
          <div className="pe-form">
            <Field label="Title *" htmlFor="pe-a-title"><input id="pe-a-title" required value={form.title} onChange={e => set({ title: e.target.value })} /></Field>
            <Field label="Priority" htmlFor="pe-a-pri"><select id="pe-a-pri" value={form.priority} onChange={e => set({ priority: e.target.value })}>{[...new Set(["Low", "Medium", "High", form.priority])].filter(Boolean).map(p => <option key={p}>{p}</option>)}</select></Field>
            <Field label="Responsible team" htmlFor="pe-a-team">
              <select id="pe-a-team" value={form.assigned_team_id} onChange={e => { const t = teams.data?.find(x => String(x.int_id) === e.target.value); set({ assigned_team_id: e.target.value, assigned_to: t ? String(t.name ?? "") : form.assigned_to }); }}>
                <option value="">No team</option>{(teams.data ?? []).map(t => <option key={t.int_id} value={t.int_id}>{String(t.name ?? `Team #${t.int_id}`)}</option>)}
              </select>
            </Field>
            <Field label="Responsible (name)" htmlFor="pe-a-who"><input id="pe-a-who" value={form.assigned_to} onChange={e => set({ assigned_to: e.target.value })} /></Field>
            <Field label="Start" htmlFor="pe-a-start"><input id="pe-a-start" type="datetime-local" value={form.scheduled_at} onChange={e => set({ scheduled_at: e.target.value })} /></Field>
            <Field label="Due" htmlFor="pe-a-due"><input id="pe-a-due" type="datetime-local" value={form.due_at} onChange={e => set({ due_at: e.target.value })} /></Field>
            <Field label="Location" htmlFor="pe-a-loc"><input id="pe-a-loc" value={form.location} onChange={e => set({ location: e.target.value })} /></Field>
            <Field label="Zone" htmlFor="pe-a-zone"><input id="pe-a-zone" value={form.zone} onChange={e => set({ zone: e.target.value })} /></Field>
            <Field label="Supports activity" htmlFor="pe-a-act">
              <select id="pe-a-act" value={form.schedule_item_id} onChange={e => set({ schedule_item_id: e.target.value })}>
                <option value="">None</option>{(schedule.data ?? []).map(a => <option key={a.record_id} value={a.record_id}>{a.title || `Activity #${a.id}`}</option>)}
              </select>
            </Field>
            <Field label="Starts as" htmlFor="pe-a-life">
              <select id="pe-a-life" value={form.lifecycle_state} onChange={e => set({ lifecycle_state: e.target.value as AssignmentForm["lifecycle_state"] })}>
                <option value="Active">Active — ready to work</option><option value="Pending">Pending — not yet released</option>
              </select>
            </Field>
            <Field label="Instructions" wide htmlFor="pe-a-sum"><textarea id="pe-a-sum" value={form.summary} onChange={e => set({ summary: e.target.value })} /></Field>
          </div>
          <h4>Repeats</h4>
          <label><input type="checkbox" checked={form.recurring} onChange={e => set({ recurring: e.target.checked })} /> This assignment recurs</label>
          {form.recurring && (
            <div className="pe-form" style={{ marginTop: 12 }}>
              <Field label="How often *" wide htmlFor="pe-a-rule"><input id="pe-a-rule" value={form.recurrence_rule} onChange={e => set({ recurrence_rule: e.target.value })} /></Field>
              <Field label="Repeats from" htmlFor="pe-a-rs"><input id="pe-a-rs" type="datetime-local" value={form.recurrence_start_at} onChange={e => set({ recurrence_start_at: e.target.value })} /></Field>
              <Field label="Repeats until" htmlFor="pe-a-re"><input id="pe-a-re" type="datetime-local" value={form.recurrence_end_at} onChange={e => set({ recurrence_end_at: e.target.value })} /></Field>
              <p className="pe-wide pe-note">If occurrences are missed, only the latest overdue occurrence is created{record?.missed_occurrence_behavior && record.missed_occurrence_behavior !== MISSED_OCCURRENCE_LATEST_OVERDUE ? ` (stored rule: ${record.missed_occurrence_behavior})` : ""}.</p>
            </div>
          )}
        </fieldset>
        {!readOnly && <div className="pe-actions"><button type="submit" disabled={writes.save.isPending}>{writes.save.isPending ? "Saving…" : record ? "Save changes" : "Create assignment"}</button></div>}
      </form>

      {record && activity && <section className="pe-panel"><h3>Supports</h3><p><Link to={`/toolkits/planned-event/schedule/${activity.id}`}>{activity.title}</Link> <StatusPill domain="planned-schedule" statusKey={activity.status} /></p><p className="pe-note">This assignment's status and promotion do not change when the activity changes.</p></section>}

      {record && canPromote(record) && carry && (
        <section className="pe-panel">
          <h3>Promote to Operations</h3>
          <p>Creates one formal Operations task from this assignment. This happens once, and the assignment becomes read-only afterwards.</p>
          {!confirming ? <button onClick={() => setConfirming(true)}>Promote to Operations task…</button> : (
            <div className="pe-readonly">
              <p><strong>Carried over:</strong> {carry.carried.join(", ")}.</p>
              {carry.kept.length > 0 && <p><strong>Stays here:</strong> {carry.kept.join("; ")}.</p>}
              <div className="pe-actions"><button disabled={writes.promote.isPending} onClick={promote}>{writes.promote.isPending ? "Promoting…" : "Confirm promotion"}</button><button className="secondary" onClick={() => setConfirming(false)}>Cancel</button></div>
            </div>
          )}
        </section>
      )}
      {record && !readOnly && (
        <section className="pe-panel"><h3>Remove</h3>
          {!confirmDelete ? <button className="secondary" onClick={() => setConfirmDelete(true)}>Delete assignment…</button> : (
            <div className="pe-actions"><span>Delete this assignment?</span>
              <button disabled={writes.remove.isPending} onClick={() => writes.remove.mutate(record.id, { onSuccess: () => navigate("/toolkits/planned-event/assignments"), onError: err => setError(describeError(err)) })}>Delete</button>
              <button className="secondary" onClick={() => setConfirmDelete(false)}>Keep</button></div>
          )}
        </section>
      )}
    </>
  );
}
