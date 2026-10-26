import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listIncidents } from "../../api/endpoints";
import { useSession } from "../../auth/SessionContext";
import KpiStrip from "../../components/KpiStrip";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import StatusPill from "../../components/table/StatusPill";
import type { TaskRow, TeamAssignmentRow } from "../../api/types";
import { useTeamRows } from "../operations/teamStatus/hooks";
import { useTaskRows } from "../operations/taskStatus/hooks";
import { useObjectiveRows } from "./objectives/hooks";
import { useOperationalPeriods } from "../planning/operationalPeriods/hooks";
import { useSitreps } from "../planning/sitreps/hooks";
import { formatCommandTime, tasksDueSoon } from "./dashboardModel";
import "./command.css";

function Panel({ title, loading, error, children }: {
  title: string; loading: boolean; error: boolean; children: ReactNode;
}) {
  return <section className="command-panel"><h3>{title}</h3>
    {error ? <p className="error" role="alert">Unable to load this panel. Use Refresh to retry.</p> :
      loading ? <p role="status">Loading…</p> : children}
  </section>;
}

const teamColumns: ColumnDef<TeamAssignmentRow>[] = [
  { key: "name", header: "Team", render: r => <Link to={`/ops/teams/${r.team_id}`}>{r.name}</Link>, defaultWidth: 180 },
  { key: "alert", header: "Attention", render: r => r.emergency_flag ? "Emergency" : r.needs_assistance_flag ? "Assistance requested" : "Needs attention", defaultWidth: 190 },
  { key: "status", header: "Status", render: r => <StatusPill domain="team" statusKey={r.status} /> },
  { key: "location", header: "Location", render: r => r.location || "Not recorded" },
];
const taskColumns: ColumnDef<TaskRow>[] = [
  { key: "name", header: "Task", render: r => <Link to={`/ops/tasks/${r.id}`}>{r.number} — {r.name}</Link>, defaultWidth: 240 },
  { key: "due", header: "Due", render: r => formatCommandTime(r.due_datetime), defaultWidth: 220 },
  { key: "status", header: "Status", render: r => <StatusPill domain="task" statusKey={r.status} /> },
];

export default function CommandDashboardPage() {
  const { incidentId } = useSession();
  const id = incidentId!;
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: listIncidents, refetchInterval: 20_000 });
  const teams = useTeamRows(id);
  const tasks = useTaskRows(id);
  const objectives = useObjectiveRows(id);
  const periods = useOperationalPeriods(id);
  const sitreps = useSitreps(id);
  const queries = [incidents, teams, tasks, objectives, periods, sitreps];
  const incident = incidents.data?.find(i => i.id === id);
  const activePeriods = periods.data?.filter(p => p.status === "Active") ?? [];
  const alerts = (teams.data ?? []).filter(t => t.emergency_flag || t.needs_assistance_flag || t.needs_attention)
    .sort((a, b) => Number(b.emergency_flag) - Number(a.emergency_flag));
  const due = tasksDueSoon(tasks.data ?? [], now);
  const activeObjectives = (objectives.data ?? []).filter(o => o.status === "active");
  const reports = [...(sitreps.data ?? [])].sort((a,b) => b.sitrep_number - a.sitrep_number).slice(0, 3);
  const metric = (query: { isPending: boolean; isError: boolean }, count: number) => query.isPending || query.isError ? "—" : count;

  return <div className="command-dashboard">
    <header className="command-heading"><div><p className="command-eyebrow">INCIDENT COMMAND</p>
      <h2>{incident?.name || "Command Dashboard"}</h2>
      <p>{incident ? `${incident.number} · ${incident.status || "Status not recorded"} · ${incident.type || "Type not recorded"}` : incidents.isError ? "Incident identity could not be loaded." : "Loading incident identity…"}</p>
    </div><div><time>{formatCommandTime(new Date(now).toISOString())}</time>
      <button className="secondary" disabled={queries.some(q => q.isFetching)} onClick={() => { void Promise.all(queries.map(q => q.refetch())); }}>Refresh</button>
    </div></header>
    <nav className="command-actions" aria-label="Command workspaces">
      <Link to="/command/objectives">Manage objectives</Link><Link to="/command/sitreps">Situation reports</Link>
      <Link to="/planning/operational-periods">Operational periods</Link><Link to="/ops/teams">Team board</Link><Link to="/ops/tasks">Task board</Link>
    </nav>
    <KpiStrip tiles={[
      { key: "teams", label: "Teams", value: metric(teams, teams.data?.length ?? 0) },
      { key: "attention", label: "Teams needing attention", value: metric(teams, alerts.length) },
      { key: "tasks", label: "Tasks overdue / due within 24h", value: metric(tasks, due.length) },
      { key: "objectives", label: "Active objectives", value: metric(objectives, activeObjectives.length) },
    ]} />
    <div className="command-grid">
      <Panel title="Current operational period" loading={periods.isPending} error={periods.isError}>
        {activePeriods.length === 0 ? <p>No active operational period. <Link to="/planning/operational-periods">Manage periods</Link></p> : activePeriods.map(p => <div key={p.id}>
          <h4><Link to={`/planning/operational-periods/${p.id}`}>OP {p.number} · {p.name}</Link></h4>
          <p>{formatCommandTime(p.start_time)} – {formatCommandTime(p.end_time)}</p>
          <p><strong>Safety message:</strong> {p.safety_message || "Not recorded"}</p>
          <p><strong>Weather:</strong> {p.weather_summary || "Not recorded"}</p>
        </div>)}
        {activePeriods.length > 1 && <p role="alert">Multiple periods are marked active. Review operational periods.</p>}
      </Panel>
      <Panel title="Latest situation reports" loading={sitreps.isPending} error={sitreps.isError}>
        {reports.length === 0 ? <p>No situation reports recorded.</p> : reports.map(r => <article key={r.id} className="command-record">
          <Link to={`/command/sitreps/${r.id}`}>SITREP {r.sitrep_number}</Link> <StatusPill domain="sitrep" statusKey={r.status} />
          <p>{r.summary || "No summary recorded."}</p><small>Updated {formatCommandTime(r.updated_at)}</small>
        </article>)}
      </Panel>
      <Panel title="Teams needing attention" loading={teams.isPending} error={teams.isError}>
        <DataTable tableId="command-alerts" columns={teamColumns} rows={alerts} rowKey={r => r.team_id} emptyMessage="No team attention flags reported." />
      </Panel>
      <Panel title="Tasks overdue or due within 24 hours" loading={tasks.isPending} error={tasks.isError}>
        <DataTable tableId="command-deadlines" columns={taskColumns} rows={due} rowKey={r => r.id} emptyMessage="No open tasks due within 24 hours." />
      </Panel>
      <Panel title="Active objectives" loading={objectives.isPending} error={objectives.isError}>
        {activeObjectives.length === 0 ? <p>No active objectives recorded.</p> : activeObjectives.map(o => <article key={o._id} className="command-record">
          <Link to={`/command/objectives/${o._id}`}>{o.code} — {o.text}</Link>
          <p>{o.owner_section || "No owner section"} · Due {formatCommandTime(o.due_time)}</p>
        </article>)}
      </Panel>
      <section className="command-panel"><h3>Command data gaps</h3><p>Approval queues, section health, operational readiness, and a unified activity feed are not tracked yet.</p><p>Personnel, lead, and safety totals are unavailable. Team attention flags above reflect the team board.</p></section>
    </div>
  </div>;
}
