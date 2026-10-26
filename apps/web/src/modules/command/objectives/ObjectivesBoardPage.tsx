import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import ExportButton from "../../forms/ExportButton";
import FilterBar from "../../../components/table/FilterBar";
import KpiStrip from "../../../components/KpiStrip";
import StatusPill from "../../../components/table/StatusPill";
import { OBJECTIVE_PRIORITIES, OBJECTIVE_STATUSES } from "../../../api/endpoints";
import type { Objective } from "../../../api/types";
import { objectivePriorityVar, objectiveStatusVar } from "../../../styles/statusColors";
import { useSession } from "../../../auth/SessionContext";
import NewObjectiveDialog from "./NewObjectiveDialog";
import { useCreateObjective, useObjectiveRows } from "./hooks";

const QUICK_CHIPS = [{ key: "", label: "All" }, ...OBJECTIVE_STATUSES];

// Left-border color: same priority as desktop's _ObjectiveCard._apply_style —
// a completed/cancelled objective's status wins (it's done, that's the
// headline fact), then urgent/high priority, then an active objective gets
// the accent, everything else stays a plain border.
function leftBorderColor(o: Objective): string {
  if (o.status === "completed" || o.status === "cancelled") return objectiveStatusVar(o.status).bg;
  if (o.priority === "urgent" || o.priority === "high") return objectivePriorityVar(o.priority).bg;
  if (o.status === "active") return objectiveStatusVar(o.status).bg;
  return "#2a2d33";
}

function ObjectiveCard({ objective, onOpen }: { objective: Objective; onOpen: () => void }) {
  return (
    <div
      className="objective-card"
      style={{ borderLeftColor: leftBorderColor(objective) }}
      onClick={onOpen}
    >
      <div className="objective-card-header">
        <span className="objective-card-title">
          <b>{objective.code}</b> {objective.text || "(Untitled Objective)"}
        </span>
        <StatusPill domain="objective-priority" statusKey={objective.priority} />
        <StatusPill domain="objective" statusKey={objective.status} />
      </div>
      <div className="objective-card-meta">
        <span>{objective.owner_section || "No owner assigned"}</span>
        <span>{objective.op_period_id ? `OP ${objective.op_period_id}` : "No OP"}</span>
        {objective.due_time && <span>Due {new Date(objective.due_time).toLocaleString()}</span>}
      </div>
      <div className="objective-card-footer">
        <span className={objective.open_tasks > 0 ? "objective-card-alert" : undefined}>
          Tasks: {objective.open_tasks} open / {objective.total_tasks} total
        </span>
        {objective.tags.length > 0 && (
          <span className="objective-card-tags">{objective.tags.slice(0, 4).map((t) => `#${t}`).join("  ")}</span>
        )}
      </div>
    </div>
  );
}

export default function ObjectivesBoardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [showNew, setShowNew] = useState(false);

  const { data: rows = [], isLoading, error } = useObjectiveRows(incidentId!);
  const createObjective = useCreateObjective(incidentId!);

  const filteredRows = useMemo(() => {
    return rows
      .filter((o) => {
        if (statusFilter && o.status !== statusFilter) return false;
        if (priorityFilter && o.priority !== priorityFilter) return false;
        if (search) {
          const haystack = `${o.code} ${o.text} ${o.owner_section ?? ""}`.toLowerCase();
          if (!haystack.includes(search.toLowerCase())) return false;
        }
        return true;
      })
      .sort((a, b) => a.display_order - b.display_order);
  }, [rows, search, statusFilter, priorityFilter]);

  const kpiTiles = useMemo(() => {
    const count = (pred: (o: Objective) => boolean) => rows.filter(pred).length;
    const now = Date.now();
    return [
      { key: "total", value: rows.length, label: "Objectives" },
      {
        key: "active",
        value: count((o) => o.status === "active"),
        label: "Active",
        accent: objectiveStatusVar("active").bg,
      },
      {
        key: "draft",
        value: count((o) => o.status === "draft"),
        label: "Draft",
        accent: objectiveStatusVar("draft").bg,
      },
      {
        key: "completed",
        value: count((o) => o.status === "completed"),
        label: "Completed",
        accent: objectiveStatusVar("completed").bg,
      },
      {
        key: "overdue",
        value: count(
          (o) =>
            Boolean(o.due_time) &&
            new Date(o.due_time as string).getTime() < now &&
            o.status !== "completed" &&
            o.status !== "cancelled"
        ),
        label: "Overdue",
        accent: "var(--status-alert-attention-bg)",
      },
    ];
  }, [rows]);

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, gap: 8, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Incident Objectives</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <ExportButton formId="ics_202" label="Export ICS-202" />
          <button style={{ width: "auto" }} onClick={() => setShowNew(true)}>
            New Objective
          </button>
        </div>
      </div>

      <KpiStrip tiles={kpiTiles} />

      <div className="quick-chip-row">
        {QUICK_CHIPS.map((c) => (
          <button
            key={c.key || "all"}
            type="button"
            className={"quick-chip" + (statusFilter === c.key ? " active" : "")}
            onClick={() => setStatusFilter(c.key)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        activeFilters={[
          ...(statusFilter ? [{ key: "status", label: `Status: ${statusFilter}` }] : []),
          ...(priorityFilter ? [{ key: "priority", label: `Priority: ${priorityFilter}` }] : []),
        ]}
        onClearFilter={(key) => (key === "status" ? setStatusFilter("") : setPriorityFilter(""))}
        onResetAll={() => {
          setStatusFilter("");
          setPriorityFilter("");
        }}
      >
        <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
          <option value="">All priorities</option>
          {OBJECTIVE_PRIORITIES.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load objectives.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : filteredRows.length === 0 ? (
        <p className="objective-card-empty">No objectives yet. Click New Objective to create one.</p>
      ) : (
        <div className="objective-card-list">
          {filteredRows.map((o) => (
            <ObjectiveCard key={o._id} objective={o} onOpen={() => navigate(`/command/objectives/${o._id}`)} />
          ))}
        </div>
      )}

      {showNew && (
        <NewObjectiveDialog
          busy={createObjective.isPending}
          onCancel={() => setShowNew(false)}
          onCreate={(body) =>
            createObjective.mutate(
              { ...body, created_by: user?.username },
              { onSuccess: () => setShowNew(false) }
            )
          }
        />
      )}
    </div>
  );
}
