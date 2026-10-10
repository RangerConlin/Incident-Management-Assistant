import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import FilterBar from "../../../components/table/FilterBar";
import RowContextMenu, { type ContextMenuSection } from "../../../components/table/RowContextMenu";
import StatusPill from "../../../components/table/StatusPill";
import type { TaskRow } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { TASK_STATUS_OPTIONS, useCreateTask, useSetTaskStatus, useTaskRows } from "./hooks";

export default function TaskStatusBoardPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [menu, setMenu] = useState<{ row: TaskRow; x: number; y: number } | null>(null);

  const { data: rows = [], isLoading, error } = useTaskRows(incidentId!);
  const createTask = useCreateTask(incidentId!);
  const setStatus = useSetTaskStatus(incidentId!);

  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (search) {
        const haystack = `${r.number} ${r.name} ${r.assigned_teams.join(" ")}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [rows, search, statusFilter]);

  const columns: ColumnDef<TaskRow>[] = [
    { key: "number", header: "Task #", sortable: true, sortValue: (r) => r.number, defaultWidth: 100 },
    { key: "name", header: "Task Name", sortable: true, sortValue: (r) => r.name, defaultWidth: 220 },
    {
      key: "assigned_teams",
      header: "Assigned Teams",
      render: (r) => r.assigned_teams.join(", ") || "—",
      defaultWidth: 200,
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (r) => r.status,
      render: (r) => <StatusPill domain="task" statusKey={r.status} />,
      defaultWidth: 130,
    },
    { key: "priority", header: "Priority", defaultWidth: 100 },
    { key: "location", header: "Location", defaultWidth: 180 },
  ];

  const buildMenuSections = (row: TaskRow): ContextMenuSection[] => [
    {
      title: "Status",
      items: TASK_STATUS_OPTIONS.map((s) => ({
        label: s.label,
        onClick: () => setStatus.mutate({ taskId: row.id, statusKey: s.key }),
      })),
    },
    {
      items: [{ label: "View Task Detail", onClick: () => navigate(`/ops/tasks/${row.id}`) }],
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Task Status Board</h2>
        <button
          style={{ width: "auto" }}
          onClick={() => createTask.mutate({}, { onSuccess: (task) => navigate(`/ops/tasks/${task.int_id}`) })}
        >
          New Task
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
          {TASK_STATUS_OPTIONS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load tasks.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="task-status-board"
          columns={columns}
          rows={filteredRows}
          rowKey={(r) => r.id}
          onRowActivate={(r) => navigate(`/ops/tasks/${r.id}`)}
          onRowContextMenu={(r, e) => setMenu({ row: r, x: e.clientX, y: e.clientY })}
          emptyMessage="No tasks yet. Click New Task to create one."
        />
      )}

      <RowContextMenu
        position={menu ? { x: menu.x, y: menu.y } : null}
        sections={menu ? buildMenuSections(menu.row) : []}
        onClose={() => setMenu(null)}
      />
    </div>
  );
}
