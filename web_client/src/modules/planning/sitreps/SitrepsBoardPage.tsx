import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import StatusPill from "../../../components/table/StatusPill";
import KpiStrip from "../../../components/KpiStrip";
import type { Sitrep } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { useCreateSitrep, useDuplicateSitrep, useSitrepOperationalSummary, useSitreps } from "./hooks";

export default function SitrepsBoardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();

  const { data: rows = [], isLoading, error } = useSitreps(incidentId!);
  const { data: summary } = useSitrepOperationalSummary(incidentId!);
  const createSitrep = useCreateSitrep(incidentId!);
  const duplicateSitrep = useDuplicateSitrep(incidentId!);

  const columns: ColumnDef<Sitrep>[] = [
    { key: "sitrep_number", header: "#", sortable: true, sortValue: (s) => s.sitrep_number, defaultWidth: 60 },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (s) => s.status,
      render: (s) => <StatusPill domain="sitrep" statusKey={s.status} />,
      defaultWidth: 130,
    },
    { key: "prepared_by", header: "Prepared By", render: (s) => s.prepared_by || "—", defaultWidth: 140 },
    { key: "current_priority", header: "Priority", render: (s) => s.current_priority || "—", defaultWidth: 150 },
    { key: "created_at", header: "Created", render: (s) => new Date(s.created_at).toLocaleString(), defaultWidth: 170 },
    {
      key: "actions",
      header: "",
      render: (s) => (
        <button
          className="secondary"
          style={{ width: "auto", padding: "4px 10px", fontSize: "0.78rem" }}
          onClick={(e) => {
            e.stopPropagation();
            duplicateSitrep.mutate(s.id, { onSuccess: (created) => navigate(`/planning/sitreps/${created.id}`) });
          }}
        >
          New Update From This
        </button>
      ),
      defaultWidth: 160,
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Situation Reports</h2>
        <button
          style={{ width: "auto" }}
          disabled={createSitrep.isPending}
          onClick={() =>
            createSitrep.mutate(
              { prepared_by: user?.display_name },
              { onSuccess: (created) => navigate(`/planning/sitreps/${created.id}`) }
            )
          }
        >
          New SITREP
        </button>
      </div>

      {summary && (
        <KpiStrip
          tiles={[
            { key: "active-teams", value: summary.teams.active ?? 0, label: "Active Teams" },
            { key: "available-teams", value: summary.teams.available ?? 0, label: "Available Teams" },
            { key: "tasks-in-progress", value: summary.tasks.in_progress ?? 0, label: "Tasks In Progress" },
            { key: "checked-in", value: summary.total_checked_in, label: "Checked In" },
            {
              key: "alerts",
              value: summary.alerts.length,
              label: "Active Alerts",
              accent: summary.alerts.length > 0 ? "var(--status-alert-attention-bg)" : undefined,
            },
          ]}
        />
      )}

      {error && <p className="error">Could not load situation reports.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="planning-sitreps-board"
          columns={columns}
          rows={rows}
          rowKey={(s) => s.id}
          onRowActivate={(s) => navigate(`/planning/sitreps/${s.id}`)}
          emptyMessage="No situation reports yet. Click New SITREP to create the first one."
        />
      )}
    </div>
  );
}
