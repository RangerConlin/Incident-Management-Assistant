import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import ElapsedTime from "../../../components/table/ElapsedTime";
import FilterBar from "../../../components/table/FilterBar";
import RowContextMenu, { type ContextMenuSection } from "../../../components/table/RowContextMenu";
import StatusPill from "../../../components/table/StatusPill";
import { TEAM_STATUS_STEPS } from "../../../api/endpoints";
import type { TeamAssignmentRow } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import TaskPickerDialog from "./TaskPickerDialog";
import {
  STATUSES_REQUIRING_TASK,
  TEAM_STATUS_OTHER,
  useAssignTeamToTask,
  useCreateTeam,
  useResetCommPing,
  useSetTeamStatus,
  useTeamRows,
} from "./hooks";

export default function TeamStatusBoardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [menu, setMenu] = useState<{ row: TeamAssignmentRow; x: number; y: number } | null>(null);
  const [pendingStatus, setPendingStatus] = useState<{ row: TeamAssignmentRow; statusKey: string } | null>(null);

  const { data: rows = [], isLoading, error } = useTeamRows(incidentId!);
  const setStatus = useSetTeamStatus(incidentId!);
  const createTeam = useCreateTeam(incidentId!);
  const resetCommPing = useResetCommPing(incidentId!);
  const assignToTask = useAssignTeamToTask(incidentId!);

  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (search) {
        const haystack = `${r.name} ${r.leader} ${r.assignment}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [rows, search, statusFilter]);

  const applyStatus = (row: TeamAssignmentRow, statusKey: string) => {
    if (STATUSES_REQUIRING_TASK.has(statusKey) && row.task_id == null) {
      setPendingStatus({ row, statusKey });
      return;
    }
    setStatus.mutate({ teamId: row.team_id, statusKey });
  };

  const columns: ColumnDef<TeamAssignmentRow>[] = [
    { key: "sortie", header: "Sortie #", defaultWidth: 90 },
    { key: "name", header: "Team Name", sortable: true, sortValue: (r) => r.name, defaultWidth: 160 },
    { key: "team_type", header: "Team Type", defaultWidth: 100 },
    { key: "leader", header: "Team Leader", defaultWidth: 150 },
    { key: "contact", header: "Contact #", defaultWidth: 130 },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (r) => r.status,
      render: (r) => <StatusPill domain="team" statusKey={r.status} />,
      defaultWidth: 120,
    },
    { key: "assignment", header: "Assignment", defaultWidth: 200 },
    { key: "location", header: "Location", defaultWidth: 160 },
    {
      key: "last_updated",
      header: "Last Update",
      render: (r) => <ElapsedTime since={r.last_updated} />,
      defaultWidth: 110,
    },
  ];

  const buildMenuSections = (row: TeamAssignmentRow): ContextMenuSection[] => [
    {
      title: "Status (requires a task)",
      items: TEAM_STATUS_STEPS.map((s) => ({ label: s.label, onClick: () => applyStatus(row, s.key) })),
    },
    {
      title: "Other status",
      items: TEAM_STATUS_OTHER.map((s) => ({ label: s.label, onClick: () => applyStatus(row, s.key) })),
    },
    {
      items: [
        { label: "View Team Detail", onClick: () => navigate(`/ops/teams/${row.team_id}`) },
        {
          label: "View Task Detail",
          onClick: () => row.task_id != null && navigate(`/ops/tasks/${row.task_id}`),
          disabled: row.task_id == null,
        },
        { label: "Reset Timer", onClick: () => resetCommPing.mutate(row.team_id) },
      ],
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Team Status Board</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={{ width: "auto" }} onClick={() => createTeam.mutate({})}>
            New Team
          </button>
        </div>
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
          {[...TEAM_STATUS_STEPS, ...TEAM_STATUS_OTHER].map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load teams.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="team-status-board"
          columns={columns}
          rows={filteredRows}
          rowKey={(r) => r.team_id}
          onRowActivate={(r) => navigate(`/ops/teams/${r.team_id}`)}
          onRowContextMenu={(r, e) => setMenu({ row: r, x: e.clientX, y: e.clientY })}
          getRowClassName={(r) => (r.emergency_flag || r.needs_attention ? "row-emergency" : undefined)}
          leadingIcon={(r) => (r.emergency_flag ? "🚨" : r.needs_attention ? "⚠" : "")}
          emptyMessage="No teams yet. Click New Team to create one."
        />
      )}

      <RowContextMenu
        position={menu ? { x: menu.x, y: menu.y } : null}
        sections={menu ? buildMenuSections(menu.row) : []}
        onClose={() => setMenu(null)}
      />

      {pendingStatus && (
        <TaskPickerDialog
          incidentId={incidentId}
          onCancel={() => setPendingStatus(null)}
          onPick={(taskId) => {
            assignToTask.mutate(
              { taskId, teamId: pendingStatus.row.team_id },
              {
                onSuccess: () => {
                  setStatus.mutate({ teamId: pendingStatus.row.team_id, statusKey: pendingStatus.statusKey });
                  setPendingStatus(null);
                },
              }
            );
          }}
        />
      )}

      <p style={{ fontSize: "0.75rem", opacity: 0.5, marginTop: 8 }}>
        Signed in as {user?.display_name}. "Other status" entries ({TEAM_STATUS_OTHER.map((s) => s.label).join(", ")})
        don't require a task; the rest prompt for one if this team isn't currently assigned.
      </p>
    </div>
  );
}
