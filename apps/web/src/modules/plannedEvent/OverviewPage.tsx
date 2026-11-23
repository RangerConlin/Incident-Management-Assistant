import { Link } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import KpiStrip from "../../components/KpiStrip";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { usePlannedRecords, useScheduleItems } from "./hooks";
import { assignmentState, attention, isTerminal } from "./model";
import { useNow } from "./ui";

export default function OverviewPage() {
  const { incidentId } = useSession();
  const now = useNow();
  const schedule = useScheduleItems(incidentId!);
  const assignments = usePlannedRecords(incidentId!, "quick-assignments");
  const queries = [schedule, assignments];
  const total = (q: { isPending: boolean; isError: boolean }, n: number) => (q.isPending || q.isError ? "—" : n);
  const items = schedule.data ?? [];
  const flagged = items.map(item => ({ item, flag: attention(item, now) })).filter(x => x.flag && x.flag.kind !== "starting-soon");
  const upcoming = items
    .filter(i => i.status === "Scheduled" && attention(i, now)?.kind === "starting-soon")
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const inProgress = items.filter(i => i.status === "In Progress");
  const pending = (assignments.data ?? []).filter(a => assignmentState(a) !== "Promoted");

  return (
    <>
      <div className="pe-toolbar">
        <h3>Event-day overview</h3>
        <Link to="schedule/new">New activity</Link>
        <button className="secondary" disabled={queries.some(q => q.isFetching)} onClick={() => void Promise.all(queries.map(q => q.refetch()))}>Refresh</button>
      </div>
      {queries.some(q => q.isError) && <p className="error" role="alert">Some event data could not be loaded. Affected totals are unavailable. Refresh to retry.</p>}
      <KpiStrip tiles={[
        { key: "progress", label: "In progress", value: total(schedule, inProgress.length) },
        { key: "soon", label: "Starting within the hour", value: total(schedule, upcoming.length) },
        { key: "attention", label: "Need attention", value: total(schedule, flagged.length), accent: "var(--status-alert-attention-bg)" },
        { key: "assignments", label: "Assignments not yet promoted", value: total(assignments, pending.length) },
      ]} />
      <div className="pe-grid">
        <section className={"pe-panel" + (flagged.length ? " pe-attention" : "")}>
          <h3>Needs attention</h3>
          {schedule.isPending ? <p role="status">Loading…</p> : flagged.length === 0 ? <p>Nothing is overdue, delayed or running long.</p> : (
            <ul className="pe-list">
              {flagged.map(({ item, flag }) => (
                <li key={item.id}>
                  <Link to={`schedule/${item.id}`}>{item.title || `Activity #${item.id}`}</Link>
                  <span className="pe-flag">{flag!.label}</span>
                  <StatusPill domain="planned-schedule" statusKey={item.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="pe-panel">
          <h3>Starting within the hour</h3>
          {schedule.isPending ? <p role="status">Loading…</p> : upcoming.length === 0 ? <p>No activities are about to start.</p> : (
            <ul className="pe-list">
              {upcoming.map(item => (
                <li key={item.id}>
                  <Link to={`schedule/${item.id}`}>{item.title || `Activity #${item.id}`}</Link>
                  <span>{formatDateTime(item.starts_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="pe-panel">
          <h3>In progress now</h3>
          {schedule.isPending ? <p role="status">Loading…</p> : inProgress.length === 0 ? <p>Nothing is running.</p> : (
            <ul className="pe-list">
              {inProgress.map(item => (
                <li key={item.id}>
                  <Link to={`schedule/${item.id}`}>{item.title || `Activity #${item.id}`}</Link>
                  <span>Planned end {formatDateTime(item.ends_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="pe-panel">
          <h3>Open assignments</h3>
          {assignments.isPending ? <p role="status">Loading…</p> : pending.length === 0 ? <p>Every assignment has been promoted, or none exist yet.</p> : (
            <ul className="pe-list">
              {pending.slice(0, 8).map(a => (
                <li key={a.id}>
                  <Link to={`assignments/${a.id}`}>{a.title || `Assignment #${a.id}`}</Link>
                  <StatusPill domain="planned-assignment" statusKey={assignmentState(a)} />
                </li>
              ))}
            </ul>
          )}
          <p><Link to="assignments">All assignments</Link></p>
        </section>
      </div>
      <p className="pe-note">{items.filter(i => isTerminal(i.status)).length > 0 ? "Completed and cancelled activities stay on the schedule for the record." : ""}</p>
    </>
  );
}
