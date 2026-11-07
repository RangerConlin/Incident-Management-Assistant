import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import KpiStrip from "../../components/KpiStrip";
import StatusPill from "../../components/table/StatusPill";
import EntryCard from "../command/EntryCard";
import { objectiveStatusVar } from "../../styles/statusColors";
import { formatDateTime } from "../../utils/formatDateTime";
import { useObjectiveRows } from "../command/objectives/hooks";
import { useOperationalPeriods } from "./operationalPeriods/hooks";
import { useMeetings } from "./meetings/hooks";
import { useWorkAssignments } from "./workAssignments/hooks";
import { useResourceStatusRows } from "../logistics/resourceStatus/hooks";
import { pendingApprovals } from "../../api/endpoints";
import { useQuery } from "@tanstack/react-query";
import "./planning.css";

const OPEN_WA_STATUSES = new Set(["Complete", "Cancelled"]);
const DEMOB_STATUSES = new Set(["Preparing for Demobilization", "Demobilized"]);

export default function PlanningDashboardPage() {
  const { incidentId, personnel } = useSession();
  const id = incidentId!;
  const navigate = useNavigate();

  const objectives = useObjectiveRows(id);
  const periods = useOperationalPeriods(id);
  const meetings = useMeetings(id);
  const workAssignments = useWorkAssignments(id);
  const demobResources = useResourceStatusRows(id, "");
  const personRecord = personnel?.person_record;
  const approvals = useQuery({
    queryKey: ["incident", id, "approval_instances", "pending", personRecord],
    queryFn: () => pendingApprovals(id, personRecord!),
    enabled: Boolean(personRecord),
    refetchInterval: 20_000,
  });

  const activePeriod = (periods.data ?? []).find((p) => p.status === "Active");
  const nextPeriod = [...(periods.data ?? [])]
    .filter((p) => p.status === "Planned")
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())[0];

  const upcomingMeetings = useMemo(() => {
    const now = Date.now();
    return [...(meetings.data ?? [])]
      .filter((m) => !["completed", "canceled"].includes(m.status) && new Date(`${m.meeting_date}T${m.start_time}`).getTime() >= now)
      .sort((a, b) => `${a.meeting_date}T${a.start_time}`.localeCompare(`${b.meeting_date}T${b.start_time}`))
      .slice(0, 4);
  }, [meetings.data]);

  const openWorkAssignments = useMemo(
    () => (workAssignments.data ?? []).filter((w) => !OPEN_WA_STATUSES.has(w.planning_status)),
    [workAssignments.data]
  );

  const demobilizing = useMemo(
    () => (demobResources.data ?? []).filter((r) => DEMOB_STATUSES.has(r.status)),
    [demobResources.data]
  );

  const upcomingObjectives = useMemo(() => {
    return (objectives.data ?? [])
      .filter((o) => o.due_time && o.status !== "completed" && o.status !== "cancelled")
      .sort((a, b) => new Date(a.due_time!).getTime() - new Date(b.due_time!).getTime())
      .slice(0, 4);
  }, [objectives.data]);

  const activeObjectives = (objectives.data ?? []).filter((o) => o.status === "active");

  const kpiTiles = [
    { key: "objectives-active", value: activeObjectives.length, label: "Active objectives", accent: objectiveStatusVar("active").bg },
    { key: "wa-open", value: openWorkAssignments.length, label: "Open work assignments", accent: "var(--status-severity-warning-bg)" },
    { key: "meetings", value: upcomingMeetings.length, label: "Upcoming meetings" },
    { key: "approvals", value: approvals.data?.length ?? 0, label: "Your pending approvals", accent: "var(--status-severity-critical-bg)" },
    { key: "demob", value: demobilizing.length, label: "Demobilizing resources" },
  ];

  if (!id) return null;

  return (
    <div className="planning-dashboard">
      <header className="command-heading">
        <div>
          <p className="command-eyebrow">PLANNING SECTION</p>
          <h2>Planning</h2>
        </div>
      </header>
      <p style={{ opacity: 0.7, marginTop: -8 }}>Strategic objectives, operational periods, meetings, work assignments, approvals, and demobilization.</p>

      <div className="info-strip">
        <div className="info-item"><span className="k">Active Op Period</span><span className="v">{activePeriod ? `OP ${activePeriod.number} — ${activePeriod.name}` : "None active"}</span></div>
        <div className="info-item"><span className="k">Next Op Period</span><span className="v">{nextPeriod ? `OP ${nextPeriod.number} — ${formatDateTime(nextPeriod.start_time)}` : "Not scheduled"}</span></div>
      </div>

      <KpiStrip tiles={kpiTiles} />

      <div className="planning-grid">
        <section className="planning-panel">
          <h3>Active Objectives</h3>
          {objectives.isPending ? <p>Loading…</p> : objectives.isError ? <p className="error" role="alert">Unable to load objectives.</p> :
            upcomingObjectives.length === 0 ? <p className="entry-empty">No objectives with an upcoming due date.</p> :
            upcomingObjectives.map((o) => (
              <EntryCard
                key={o._id}
                title={<>{o.code} — {o.text}</>}
                when={o.due_time ? `Due ${formatDateTime(o.due_time)}` : undefined}
                summary={<StatusPill domain="objective" statusKey={o.status} />}
              >
                <Link className="panel-link" to={`/command/objectives/${o._id}`}>Open objective →</Link>
              </EntryCard>
            ))}
          <Link className="panel-link" to="/command/objectives">Open Incident Objectives →</Link>
        </section>

        <section className="planning-panel">
          <h3>Upcoming Meetings</h3>
          {meetings.isPending ? <p>Loading…</p> : meetings.isError ? <p className="error" role="alert">Unable to load meetings.</p> :
            upcomingMeetings.length === 0 ? <p className="entry-empty">No upcoming meetings scheduled.</p> :
            upcomingMeetings.map((m) => (
              <EntryCard
                key={m.id}
                title={m.title}
                when={`${m.meeting_date} ${m.start_time}`}
                summary={m.owner ? `Owner: ${m.owner}` : "No owner recorded."}
              >
                <Link className="panel-link" to="/planning/meetings">Open Meetings →</Link>
              </EntryCard>
            ))}
        </section>

        <section className="planning-panel">
          <h3>Open Work Assignments</h3>
          {workAssignments.isPending ? <p>Loading…</p> : workAssignments.isError ? <p className="error" role="alert">Unable to load work assignments.</p> :
            openWorkAssignments.length === 0 ? <p className="entry-empty">No open work assignments.</p> :
            openWorkAssignments.slice(0, 5).map((w) => (
              <EntryCard
                key={w.id}
                title={`${w.assignment_number} — ${w.assignment_name}`}
                summary={`${w.planning_status} · ${w.branch || "No branch"}${w.division_group ? ` / ${w.division_group}` : ""}`}
              >
                <Link className="panel-link" to="/tactics/assignments">Open Assignment Board →</Link>
              </EntryCard>
            ))}
        </section>

        <section className="planning-panel">
          <h3>Your Pending Approvals</h3>
          {!personRecord ? <p className="entry-empty">Your account must be linked to personnel to see assigned approvals.</p> :
            approvals.isPending ? <p>Loading…</p> : approvals.isError ? <p className="error" role="alert">Unable to load approvals.</p> :
            (approvals.data ?? []).length === 0 ? <p className="entry-empty">No pending approvals assigned to you.</p> :
            (approvals.data ?? []).slice(0, 5).map((a) => (
              <EntryCard
                key={`${a.entity_type}:${a.entity_id}:${a.step_id}`}
                title={String(a.label ?? a.entity_type)}
                when={a.activated_at ? formatDateTime(String(a.activated_at)) : undefined}
                summary={`${a.entity_type} · ${a.role}`}
              >
                <button className="panel-link" style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }} onClick={() => navigate("/planning/approvals")}>
                  Open Approvals →
                </button>
              </EntryCard>
            ))}
        </section>

        <section className="planning-panel" style={{ gridColumn: "1 / -1" }}>
          <h3>Demobilizing Resources</h3>
          {demobResources.isPending ? <p>Loading…</p> : demobResources.isError ? <p className="error" role="alert">Unable to load resources.</p> :
            demobilizing.length === 0 ? <p className="entry-empty">No resources currently demobilizing.</p> :
            demobilizing.slice(0, 6).map((r) => (
              <EntryCard
                key={`${r.entity_type}:${r.record_id}`}
                title={r.resource_name}
                summary={`${r.status} · ${r.resource_type}`}
              >
                <Link className="panel-link" to="/planning/demobilization">Open Demobilization →</Link>
              </EntryCard>
            ))}
        </section>
      </div>
    </div>
  );
}
