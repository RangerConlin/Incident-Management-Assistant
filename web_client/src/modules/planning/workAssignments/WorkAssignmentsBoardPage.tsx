import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import FilterBar from "../../../components/table/FilterBar";
import StatusPill from "../../../components/table/StatusPill";
import { WA_PLANNING_STATUSES } from "../../../api/endpoints";
import type { WorkAssignment } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { useCreateWorkAssignment, useWorkAssignments } from "./hooks";

export default function WorkAssignmentsBoardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const { data: rows = [], isLoading, error } = useWorkAssignments(incidentId!);
  const createWA = useCreateWorkAssignment(incidentId!);

  const filteredRows = useMemo(() => {
    return rows.filter((w) => {
      if (statusFilter && w.planning_status !== statusFilter) return false;
      if (search) {
        const haystack = `${w.assignment_number} ${w.assignment_name} ${w.branch} ${w.division_group}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [rows, search, statusFilter]);

  const columns: ColumnDef<WorkAssignment>[] = [
    { key: "assignment_number", header: "#", defaultWidth: 90 },
    { key: "assignment_name", header: "Name", sortable: true, sortValue: (w) => w.assignment_name, defaultWidth: 220 },
    {
      key: "priority",
      header: "Priority",
      render: (w) => <StatusPill domain="objective-priority" statusKey={w.priority} />,
      defaultWidth: 100,
    },
    { key: "planning_status", header: "Planning Status", defaultWidth: 160 },
    { key: "safety_status", header: "Safety Status", defaultWidth: 160 },
    { key: "resource_status", header: "Resource Status", defaultWidth: 150 },
    { key: "division_group", header: "Division/Group", render: (w) => w.division_group || "—", defaultWidth: 140 },
    {
      key: "resources",
      header: "Resources",
      render: (w) => {
        const required = w.resources.reduce((sum, r) => sum + r.quantity_required, 0);
        const assigned = w.resources.reduce((sum, r) => sum + r.quantity_assigned, 0);
        return `${assigned}/${required}`;
      },
      defaultWidth: 100,
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Work Assignments</h2>
        <button
          style={{ width: "auto" }}
          disabled={createWA.isPending}
          onClick={() =>
            createWA.mutate(
              { created_by: user?.username },
              { onSuccess: (created) => navigate(`/planning/work-assignments/${created.id}`) }
            )
          }
        >
          New Work Assignment
        </button>
      </div>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        activeFilters={statusFilter ? [{ key: "status", label: `Status: ${statusFilter}` }] : []}
        onClearFilter={() => setStatusFilter("")}
        onResetAll={() => setStatusFilter("")}
      >
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {WA_PLANNING_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load work assignments.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="planning-work-assignments-board"
          columns={columns}
          rows={filteredRows}
          rowKey={(w) => w.id}
          onRowActivate={(w) => navigate(`/planning/work-assignments/${w.id}`)}
          emptyMessage="No work assignments yet. Click New Work Assignment to create one."
        />
      )}
    </div>
  );
}
