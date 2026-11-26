import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import FilterBar from "../../components/table/FilterBar";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { usePlannedRecords, useScheduleItems } from "./hooks";
import { assignmentState, sourceActivity, type PlannedRecord } from "./model";

const STATES = ["Pending", "Active", "Promoted"];

export default function AssignmentsPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const query = usePlannedRecords(incidentId!, "quick-assignments");
  const schedule = useScheduleItems(incidentId!);
  const update = (key: string, value: string) => setParams(old => { const next = new URLSearchParams(old); if (value) next.set(key, value); else next.delete(key); return next; }, { replace: true });
  const all = query.data ?? [];
  const q = (params.get("q") ?? "").toLowerCase();
  const state = params.get("state") ?? "";
  const recurring = params.get("recurring") === "1";
  const rows = all
    .filter(a => !state || assignmentState(a) === state)
    .filter(a => !recurring || a.recurring)
    .filter(a => !q || [a.title, a.summary, a.assigned_to, a.location, a.source_label].some(v => (v ?? "").toLowerCase().includes(q)));
  const columns: ColumnDef<PlannedRecord>[] = [
    { key: "title", header: "Assignment", defaultWidth: 260, sortable: true, sortValue: r => r.title.toLowerCase(), render: r => <Link to={`${r.id}`}>{r.title || `Assignment #${r.id}`}</Link> },
    { key: "state", header: "State", defaultWidth: 120, sortable: true, sortValue: r => assignmentState(r), render: r => <StatusPill domain="planned-assignment" statusKey={assignmentState(r)} /> },
    { key: "priority", header: "Priority", defaultWidth: 100, sortable: true, sortValue: r => r.priority, render: r => r.priority || "—" },
    { key: "assigned_to", header: "Responsible", defaultWidth: 170, sortable: true, sortValue: r => r.assigned_to, render: r => r.assigned_to || "—" },
    { key: "due_at", header: "Due", defaultWidth: 150, sortable: true, sortValue: r => r.due_at, render: r => formatDateTime(r.due_at) },
    { key: "recurring", header: "Repeats", defaultWidth: 160, render: r => (r.recurring ? r.recurrence_rule || "Yes" : "—") },
    { key: "activity", header: "Supports activity", defaultWidth: 220, render: r => { const a = sourceActivity(r, schedule.data ?? []); return a ? <Link to={`/toolkits/planned-event/schedule/${a.id}`}>{a.title}</Link> : "—"; } },
    { key: "task", header: "Operations task", defaultWidth: 140, render: r => (r.linked_tasking_id ? <Link to={`/ops/tasks/${r.linked_tasking_id}`}>Task #{r.linked_tasking_id}</Link> : "—") },
  ];
  return (
    <>
      <div className="pe-toolbar"><h3>Assignments</h3><Link to="new">New assignment</Link><button className="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh</button></div>
      <p>Quick assignments for event staff. Promote one to send it to Operations as a formal task.</p>
      <FilterBar search={params.get("q") ?? ""} onSearchChange={v => update("q", v)}
        activeFilters={[state && { key: "state", label: state }, recurring && { key: "recurring", label: "Recurring" }].filter(Boolean) as { key: string; label: string }[]}
        onClearFilter={k => update(k, "")} onResetAll={() => setParams({})}>
        <select aria-label="State filter" value={state} onChange={e => update("state", e.target.value)}><option value="">All states</option>{STATES.map(s => <option key={s}>{s}</option>)}</select>
        <label><input type="checkbox" checked={recurring} onChange={e => update("recurring", e.target.checked ? "1" : "")} /> Recurring only</label>
      </FilterBar>
      {query.isError ? <p className="error" role="alert">Could not load assignments. Refresh to retry.</p> : query.isPending ? <p role="status">Loading…</p> :
        <DataTable tableId="planned-assignments" columns={columns} rows={rows} rowKey={r => r.id} onRowActivate={r => navigate(`${r.id}`)} emptyMessage={all.length ? "No assignments match your filters." : "No assignments yet."} />}
    </>
  );
}
