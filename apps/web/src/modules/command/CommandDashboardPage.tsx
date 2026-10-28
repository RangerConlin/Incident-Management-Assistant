import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listIncidents, listNotifications } from "../../api/endpoints";
import { useSession } from "../../auth/SessionContext";
import KpiStrip from "../../components/KpiStrip";
import { objectiveStatusVar } from "../../styles/statusColors";
import { useTeamRows } from "../operations/teamStatus/hooks";
import { useTaskRows } from "../operations/taskStatus/hooks";
import { useCommsLog } from "../communications/log/hooks";
import { useDataset } from "../workspaces/hooks";
import { useObjectiveRows } from "./objectives/hooks";
import { useOperationalPeriods } from "../planning/operationalPeriods/hooks";
import { useSitreps } from "../planning/sitreps/hooks";
import { formatCommandTime, tasksDueSoon } from "./dashboardModel";
import { SAFETY_REPORTS_DATASET } from "./QuickEntryBar";
import QuickEntryBar from "./QuickEntryBar";
import EntryCard from "./EntryCard";
import "./command.css";

function teamAlert(emergency: boolean, assistance: boolean): { severity: "critical" | "warning" | "info"; flag: string } {
  if (emergency) return { severity: "critical", flag: "Emergency" };
  if (assistance) return { severity: "warning", flag: "Needs Assistance" };
  return { severity: "info", flag: "Comm Check Overdue" };
}

function taskUrgency(status: string, dueTime: string | null, now: number): { severity?: "critical" | "warning"; flag: string } {
  if (dueTime && new Date(dueTime).getTime() < now) return { severity: "critical", flag: "Overdue" };
  if (status.toLowerCase() === "in progress") return { severity: "warning", flag: "In Progress" };
  return { flag: "Not Started" };
}

function safetySeverity(value: unknown): "critical" | "warning" | "info" {
  const level = String(value ?? "").toUpperCase();
  if (level === "CRITICAL" || level === "SERIOUS") return "critical";
  if (level === "MODERATE") return "warning";
  return "info";
}

export default function CommandDashboardPage() {
  const { incidentId, personnel } = useSession();
  const id = incidentId!;
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: listIncidents, refetchInterval: 20_000 });
  const teams = useTeamRows(id);
  const tasks = useTaskRows(id);
  const objectives = useObjectiveRows(id);
  const periods = useOperationalPeriods(id);
  const sitreps = useSitreps(id);
  const commsLog = useCommsLog(id);
  const safetyReports = useDataset(SAFETY_REPORTS_DATASET, id);
  const personRecord = personnel?.person_record;
  const notifications = useQuery({
    queryKey: ["incident", id, "notifications", personRecord],
    queryFn: () => listNotifications(id, personRecord!),
    enabled: Boolean(personRecord),
    refetchInterval: 20_000,
  });
  const queries = [incidents, teams, tasks, objectives, periods, sitreps, commsLog, safetyReports];
  const incident = incidents.data?.find(i => i.id === id);
  const activePeriod = periods.data?.find(p => p.status === "Active");
  const alerts = (teams.data ?? []).filter(t => t.emergency_flag || t.needs_assistance_flag || t.needs_attention)
    .sort((a, b) => Number(b.emergency_flag) - Number(a.emergency_flag));
  const due = tasksDueSoon(tasks.data ?? [], now);
  const activeObjectives = (objectives.data ?? []).filter(o => o.status === "active");
  const reports = [...(sitreps.data ?? [])].sort((a, b) => b.sitrep_number - a.sitrep_number).slice(0, 3);
  const safetyAlerts = [...(safetyReports.data ?? [])]
    .filter(r => r.flagged)
    .sort((a, b) => String(b.time ?? "").localeCompare(String(a.time ?? "")))
    .slice(0, 5);
  const recentMessages = [...(commsLog.data ?? [])]
    .sort((a, b) => (b.ts_utc ?? "").localeCompare(a.ts_utc ?? ""))
    .slice(0, 3);
  const recentNotifications = [...(notifications.data ?? [])].slice(0, 4);
  const metric = (query: { isPending: boolean; isError: boolean }, count: number) => query.isPending || query.isError ? "—" : count;

  return <div className="command-dashboard">
    <QuickEntryBar />

    <header className="command-heading"><div><p className="command-eyebrow">INCIDENT COMMAND</p>
      <h2>{incident?.name || "Command Dashboard"}</h2>
    </div><div><time>{formatCommandTime(new Date(now).toISOString())}</time>
      <button className="secondary" disabled={queries.some(q => q.isFetching)} onClick={() => { void Promise.all(queries.map(q => q.refetch())); }}>Refresh</button>
    </div></header>

    <div className="info-strip">
      <div className="info-item"><span className="k">Number</span><span className="v">{incident?.number || "Not recorded"}</span></div>
      <div className="info-item"><span className="k">Type</span><span className="v">{incident?.type || "Not recorded"}</span></div>
      <div className="info-item"><span className="k">Status</span><span className="v">{incident?.status || "Not recorded"}</span></div>
      <div className="info-item"><span className="k">Op Period</span><span className="v">{activePeriod ? `OP ${activePeriod.number} — ${activePeriod.name}` : "No active period"}</span></div>
    </div>

    <KpiStrip tiles={[
      { key: "teams", label: "Teams", value: metric(teams, teams.data?.length ?? 0) },
      { key: "attention", label: "Teams needing attention", value: metric(teams, alerts.length), accent: "var(--status-severity-critical-bg)" },
      { key: "tasks", label: "Tasks overdue / due within 24h", value: metric(tasks, due.length), accent: "var(--status-severity-warning-bg)" },
      { key: "objectives", label: "Active objectives", value: metric(objectives, activeObjectives.length), accent: objectiveStatusVar("active").bg },
    ]} />

    <div className="command-grid">
      <section className="command-panel" style={{ gridColumn: "1 / -1" }}>
        <h3>Map Snapshot</h3>
        <div className="map-mock">
          <span className="map-pin" style={{ left: "24%", top: "36%" }} title="ICP" />
          {alerts.length > 0 && <span className="map-pin critical" style={{ left: "58%", top: "22%" }} title="Teams needing attention" />}
          {activeObjectives.length > 0 && <span className="map-pin good" style={{ left: "41%", top: "58%" }} title="Active objective" />}
        </div>
        <p className="muted" style={{ marginTop: 8, opacity: 0.65 }}>Static placeholder — the real panel will embed the live incident map once GIS support exists in the web client.</p>
      </section>

      <section className="command-panel">
        <h3>Safety Alerts</h3>
        {safetyReports.isPending ? <p>Loading…</p> : safetyReports.isError ? <p className="error" role="alert">Unable to load safety reports.</p> :
          safetyAlerts.length === 0 ? <p className="entry-empty">No flagged safety alerts.</p> :
          safetyAlerts.map((r) => (
            <EntryCard
              key={String(r.id)}
              severity={safetySeverity(r.severity)}
              flag={String(r.severity ?? "")}
              title={String(r.location || "Safety report")}
              summary={String(r.notes || "No notes recorded.")}
            >
              <p>Reported by {String(r.reported_by || "Unknown")} at {formatCommandTime(r.time as string | null)}.</p>
              <Link className="panel-link" to="/safety">View safety reports →</Link>
            </EntryCard>
          ))}
      </section>

      <section className="command-panel">
        <h3>Latest Situation Reports</h3>
        {sitreps.isPending ? <p>Loading…</p> : sitreps.isError ? <p className="error" role="alert">Unable to load situation reports.</p> :
          reports.length === 0 ? <p className="entry-empty">No situation reports recorded.</p> :
          reports.map((r) => {
            const sev = r.status === "approved" || r.status === "distributed" ? "good" as const
              : r.status === "needs_revision" ? "critical" as const
              : r.status === "ready_for_review" ? "warning" as const
              : undefined;
            return (
              <EntryCard
                key={r.id}
                severity={sev}
                flag={r.status.replace(/_/g, " ")}
                title={`SITREP ${r.sitrep_number}`}
                summary={r.summary || "No summary recorded."}
              >
                <p>Updated {formatCommandTime(r.updated_at)}.</p>
                <Link className="panel-link" to={`/command/sitreps/${r.id}`}>Open SITREP {r.sitrep_number} →</Link>
              </EntryCard>
            );
          })}
      </section>

      <section className="command-panel">
        <h3>Teams Needing Attention</h3>
        {teams.isPending ? <p>Loading…</p> : teams.isError ? <p className="error" role="alert">Unable to load teams.</p> :
          alerts.length === 0 ? <p className="entry-empty">No team attention flags reported.</p> :
          alerts.map((r) => {
            const { severity, flag } = teamAlert(r.emergency_flag, r.needs_assistance_flag);
            return (
              <EntryCard
                key={r.team_id}
                severity={severity}
                flag={flag}
                title={r.name}
                when={r.last_checkin_at ? formatCommandTime(r.last_checkin_at) : undefined}
                summary={r.assignment || r.location || "No assignment recorded."}
              >
                <p>Location: {r.location || "Not recorded"}. Status: {r.status}.</p>
                <Link className="panel-link" to={r.task_id ? `/ops/tasks/${r.task_id}` : `/ops/teams/${r.team_id}`}>Open task detail →</Link>
              </EntryCard>
            );
          })}
      </section>

      <section className="command-panel">
        <h3>Tasks Overdue or Due Within 24 Hours</h3>
        {tasks.isPending ? <p>Loading…</p> : tasks.isError ? <p className="error" role="alert">Unable to load tasks.</p> :
          due.length === 0 ? <p className="entry-empty">No open tasks due within 24 hours.</p> :
          due.map((r) => {
            const { severity, flag } = taskUrgency(r.status, r.due_datetime, now);
            return (
              <EntryCard
                key={r.id}
                severity={severity}
                flag={flag}
                title={`${r.number} — ${r.name}`}
                when={r.due_datetime ? `Due ${formatCommandTime(r.due_datetime)}` : undefined}
                summary={r.primary_team ? `Assigned to ${r.primary_team}.` : "Not yet assigned."}
              >
                <p>Status: {r.status}. Category: {r.category || "Not recorded"}.</p>
                <Link className="panel-link" to={`/ops/tasks/${r.id}`}>Open task detail →</Link>
              </EntryCard>
            );
          })}
      </section>

      <section className="command-panel">
        <h3>Active Objectives</h3>
        {objectives.isPending ? <p>Loading…</p> : objectives.isError ? <p className="error" role="alert">Unable to load objectives.</p> :
          activeObjectives.length === 0 ? <p className="entry-empty">No active objectives recorded.</p> :
          activeObjectives.map((o) => (
            <EntryCard
              key={o._id}
              title={`${o.code} — ${o.text}`}
              when={o.due_time ? `Due ${formatCommandTime(o.due_time)}` : undefined}
              summary={`${o.owner_section || "No owner section"} · ${o.open_tasks} open / ${o.total_tasks} total tasks`}
            >
              <p>{o.narrative || "No narrative recorded."}</p>
              <Link className="panel-link" to={`/command/objectives/${o._id}`}>Open objective →</Link>
            </EntryCard>
          ))}
      </section>

      <section className="command-panel">
        <h3>Recent Messages</h3>
        {commsLog.isPending ? <p>Loading…</p> : commsLog.isError ? <p className="error" role="alert">Unable to load the communications log.</p> :
          recentMessages.length === 0 ? <p className="entry-empty">No traffic logged yet.</p> :
          recentMessages.map((m) => (
            <EntryCard
              key={m.id}
              title={m.from_unit || "Unknown unit"}
              when={m.ts_local ? formatCommandTime(m.ts_local) : undefined}
              summary={m.message}
            >
              <p>{m.to_unit ? `To ${m.to_unit}. ` : ""}Priority: {m.priority}.</p>
              <Link className="panel-link" to="/comms/log">Open Traffic Log →</Link>
            </EntryCard>
          ))}
      </section>

      <section className="command-panel">
        <h3>Notifications</h3>
        {!personRecord ? <p className="entry-empty">Your account must be linked to personnel to receive notifications.</p> :
          notifications.isPending ? <p>Loading…</p> : notifications.isError ? <p className="error" role="alert">Unable to load notifications.</p> :
          recentNotifications.length === 0 ? <p className="entry-empty">No notifications.</p> :
          recentNotifications.map((n) => (
            <EntryCard
              key={n.notification_id}
              severity={n.severity === "emergency" ? "critical" : n.severity === "priority" ? "warning" : undefined}
              title={n.title}
              when={formatCommandTime(n.created_at)}
              summary={n.message}
            >
              <p>Category: {n.category}. {n.source_label ? `Source: ${n.source_label}.` : ""}</p>
              <Link className="panel-link" to="/notifications">Open Notifications →</Link>
            </EntryCard>
          ))}
      </section>
    </div>
  </div>;
}
