import FormExportControls from "../../forms/FormExportControls";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import FilterBar from "../../../components/table/FilterBar";
import KpiStrip from "../../../components/KpiStrip";
import StatusPill from "../../../components/table/StatusPill";
import { OBJECTIVE_PRIORITIES, OBJECTIVE_STATUSES } from "../../../api/endpoints";
import type { Objective } from "../../../api/types";
import { objectiveStatusVar } from "../../../styles/statusColors";
import { useSession } from "../../../auth/SessionContext";
import NewObjectiveDialog from "./NewObjectiveDialog";
import { useCreateObjective, useObjectiveRows } from "./hooks";

const QUICK_CHIPS = [{ key: "", label: "All" }, ...OBJECTIVE_STATUSES];

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
    return rows.filter((o) => {
      if (statusFilter && o.status !== statusFilter) return false;
      if (priorityFilter && o.priority !== priorityFilter) return false;
      if (search) {
        const haystack = `${o.code} ${o.text} ${o.owner_section ?? ""}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });
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

  const columns: ColumnDef<Objective>[] = [
    { key: "code", header: "Code", defaultWidth: 90 },
    { key: "text", header: "Objective", sortable: true, sortValue: (o) => o.text, defaultWidth: 320 },
    {
      key: "priority",
      header: "Priority",
      sortable: true,
      sortValue: (o) => o.priority,
      render: (o) => <StatusPill domain="objective-priority" statusKey={o.priority} />,
      defaultWidth: 100,
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (o) => o.status,
      render: (o) => <StatusPill domain="objective" statusKey={o.status} />,
      defaultWidth: 110,
    },
    { key: "owner_section", header: "Owner Section", render: (o) => o.owner_section ?? "—", defaultWidth: 140 },
    {
      key: "tasks",
      header: "Tasks",
      render: (o) => `${o.open_tasks}/${o.total_tasks}`,
      defaultWidth: 80,
    },
    {
      key: "due_time",
      header: "Due",
      render: (o) => (o.due_time ? new Date(o.due_time).toLocaleString() : "—"),
      defaultWidth: 160,
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <FormExportControls formIds={["ics_202"]} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Strategic Objectives</h2>
        <button style={{ width: "auto" }} onClick={() => setShowNew(true)}>
          New Objective
        </button>
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
      ) : (
        <DataTable
          tableId="planning-objectives-board"
          columns={columns}
          rows={filteredRows}
          rowKey={(o) => o._id}
          onRowActivate={(o) => navigate(`/planning/objectives/${o._id}`)}
          emptyMessage="No objectives yet. Click New Objective to create one."
        />
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
