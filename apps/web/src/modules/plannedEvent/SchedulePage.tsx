import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import FilterBar from "../../components/table/FilterBar";
import { formatDateTime } from "../../utils/formatDateTime";
import { useScheduleItems, useScheduleTriggers } from "./hooks";
import { attention, describeReminderTiming, parseTime, reminderState, SCHEDULE_STATUSES, type PlannedRecord, type ScheduleTrigger } from "./model";
import ScheduleTable from "./ScheduleTable";
import Timeline from "./Timeline";
import { useNow } from "./ui";

type View = "timeline" | "list" | "reminders";
const VIEWS: { key: View; label: string }[] = [{ key: "timeline", label: "Timeline" }, { key: "list", label: "List" }, { key: "reminders", label: "Reminders" }];

export function filterSchedule(items: PlannedRecord[], params: URLSearchParams, now: number): PlannedRecord[] {
  const q = (params.get("q") ?? "").trim().toLowerCase();
  const status = params.get("status") ?? "";
  const needs = params.get("attention") === "1";
  const kind = params.get("kind") ?? "";
  return items
    .filter(i => !status || i.status === status)
    .filter(i => !kind || i.kind === kind)
    .filter(i => !needs || (attention(i, now) !== null && attention(i, now)!.kind !== "starting-soon"))
    .filter(i => !q || [i.title, i.summary, i.location, i.owner, i.assigned_to, i.kind].some(v => (v ?? "").toLowerCase().includes(q)))
    .sort((a, b) => (parseTime(a.starts_at) ?? Infinity) - (parseTime(b.starts_at) ?? Infinity));
}

export default function SchedulePage() {
  const { incidentId } = useSession();
  const now = useNow();
  const [params, setParams] = useSearchParams();
  const schedule = useScheduleItems(incidentId!);
  const triggers = useScheduleTriggers(incidentId!);
  const view = (VIEWS.find(v => v.key === params.get("view"))?.key ?? "timeline") as View;
  const update = (key: string, value: string) => setParams(old => { const next = new URLSearchParams(old); if (value) next.set(key, value); else next.delete(key); return next; }, { replace: true });
  const items = schedule.data ?? [];
  const rows = useMemo(() => filterSchedule(items, params, now), [items, params, now]);
  const kinds = [...new Set(items.map(i => i.kind).filter(Boolean))];
  const chips = ["status", "kind", "attention"].filter(k => params.get(k)).map(k => ({ key: k, label: k === "attention" ? "Needs attention" : params.get(k)! }));

  return (
    <>
      <div className="pe-toolbar">
        <h3>Event schedule</h3>
        <Link to="new">New activity</Link>
        <button className="secondary" disabled={schedule.isFetching} onClick={() => { void schedule.refetch(); void triggers.refetch(); }}>Refresh</button>
      </div>
      <div className="pe-tabs" role="group" aria-label="Schedule view">
        {VIEWS.map(v => <button key={v.key} className="secondary" aria-pressed={view === v.key} onClick={() => update("view", v.key === "timeline" ? "" : v.key)}>{v.label}</button>)}
      </div>
      {view !== "reminders" && (
        <FilterBar search={params.get("q") ?? ""} onSearchChange={v => update("q", v)} activeFilters={chips} onClearFilter={k => update(k, "")} onResetAll={() => setParams(view === "timeline" ? {} : { view })}>
          <select aria-label="Status filter" value={params.get("status") ?? ""} onChange={e => update("status", e.target.value)}>
            <option value="">All statuses</option>{SCHEDULE_STATUSES.map(s => <option key={s}>{s}</option>)}
          </select>
          {kinds.length > 0 && (
            <select aria-label="Kind filter" value={params.get("kind") ?? ""} onChange={e => update("kind", e.target.value)}>
              <option value="">All kinds</option>{kinds.map(k => <option key={k}>{k}</option>)}
            </select>
          )}
          <label><input type="checkbox" checked={params.get("attention") === "1"} onChange={e => update("attention", e.target.checked ? "1" : "")} /> Needs attention</label>
        </FilterBar>
      )}
      {schedule.isError ? <p className="error" role="alert">Could not load the event schedule. Refresh to retry.</p>
        : schedule.isPending ? <p role="status">Loading…</p>
        : view === "timeline" ? <Timeline rows={rows} now={now} emptyMessage={items.length ? "No activities match your filters." : "No activities scheduled yet."} />
        : view === "list" ? <ScheduleTable rows={rows} now={now} emptyMessage={items.length ? "No activities match your filters." : "No activities scheduled yet."} />
        : <ReminderTable triggers={triggers.data ?? []} items={items} loading={triggers.isPending} failed={triggers.isError} />}
    </>
  );
}

function ReminderTable({ triggers, items, loading, failed }: { triggers: ScheduleTrigger[]; items: PlannedRecord[]; loading: boolean; failed: boolean }) {
  const byRecord = new Map(items.map(i => [i.record_id, i]));
  const columns: ColumnDef<ScheduleTrigger>[] = [
    { key: "label", header: "Reminder", defaultWidth: 240, sortable: true, sortValue: t => t.label.toLowerCase(), render: t => t.label || `Reminder #${t.id}` },
    { key: "activity", header: "Activity", defaultWidth: 240, sortable: true, sortValue: t => byRecord.get(t.schedule_item_id)?.title ?? "", render: t => { const a = byRecord.get(t.schedule_item_id); return a ? <Link to={`${a.id}`}>{a.title}</Link> : "—"; } },
    { key: "timing", header: "When", defaultWidth: 190, render: t => describeReminderTiming(t) },
    { key: "trigger_at", header: "Fires at", defaultWidth: 160, sortable: true, sortValue: t => t.trigger_at, render: t => formatDateTime(t.trigger_at) },
    { key: "state", header: "State", defaultWidth: 110, sortable: true, sortValue: t => reminderState(t), render: t => { const s = reminderState(t); return s === "Failed" ? <span className="pe-flag" title={t.fire_error}>Failed</span> : s; } },
    { key: "fired_at", header: "Fired", defaultWidth: 150, render: t => formatDateTime(t.fired_at) },
  ];
  if (failed) return <p className="error" role="alert">Could not load reminders. Refresh to retry.</p>;
  if (loading) return <p role="status">Loading…</p>;
  return <DataTable tableId="planned-reminders" columns={columns} rows={triggers.filter(t => t.schedule_item_id)} rowKey={t => t.id} emptyMessage="No reminders have been set. Add one from an activity." />;
}

