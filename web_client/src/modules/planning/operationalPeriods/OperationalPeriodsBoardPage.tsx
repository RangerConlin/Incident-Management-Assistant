import { useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import StatusPill from "../../../components/table/StatusPill";
import { ApiError } from "../../../api/client";
import type { OperationalPeriod } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import NewOperationalPeriodDialog from "./NewOperationalPeriodDialog";
import {
  useCloneOperationalPeriod,
  useCreateOperationalPeriod,
  useOperationalPeriods,
  useSetActiveOperationalPeriod,
} from "./hooks";

export default function OperationalPeriodsBoardPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [showNew, setShowNew] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const { data: rows = [], isLoading, error } = useOperationalPeriods(incidentId!);
  const createPeriod = useCreateOperationalPeriod(incidentId!);
  const setActive = useSetActiveOperationalPeriod(incidentId!);
  const clonePeriod = useCloneOperationalPeriod(incidentId!);

  const columns: ColumnDef<OperationalPeriod>[] = [
    { key: "number", header: "OP #", sortable: true, sortValue: (p) => p.number, defaultWidth: 70 },
    { key: "name", header: "Name", render: (p) => p.name || "—", defaultWidth: 200 },
    {
      key: "status",
      header: "Status",
      render: (p) => <StatusPill domain="op-period" statusKey={p.status} />,
      defaultWidth: 100,
    },
    { key: "start_time", header: "Start", render: (p) => (p.start_time ? new Date(p.start_time).toLocaleString() : "—"), defaultWidth: 170 },
    { key: "end_time", header: "End", render: (p) => (p.end_time ? new Date(p.end_time).toLocaleString() : "—"), defaultWidth: 170 },
    {
      key: "actions",
      header: "",
      render: (p) => (
        <div style={{ display: "flex", gap: 6 }}>
          {p.status !== "Active" && (
            <button
              className="secondary"
              style={{ width: "auto", padding: "4px 10px", fontSize: "0.78rem" }}
              onClick={(e) => {
                e.stopPropagation();
                setActive.mutate(p.id);
              }}
            >
              Set Active
            </button>
          )}
          <button
            className="secondary"
            style={{ width: "auto", padding: "4px 10px", fontSize: "0.78rem" }}
            onClick={(e) => {
              e.stopPropagation();
              clonePeriod.mutate(p.id);
            }}
          >
            Clone Next
          </button>
        </div>
      ),
      defaultWidth: 180,
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Operational Periods</h2>
        <button style={{ width: "auto" }} onClick={() => setShowNew(true)}>
          New Operational Period
        </button>
      </div>

      {error && <p className="error">Could not load operational periods.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="planning-operational-periods"
          columns={columns}
          rows={rows}
          rowKey={(p) => p.id}
          onRowActivate={(p) => navigate(`/planning/operational-periods/${p.id}`)}
          emptyMessage="No operational periods yet. Click New Operational Period to create the first one."
        />
      )}

      {showNew && (
        <NewOperationalPeriodDialog
          busy={createPeriod.isPending}
          error={createError}
          onCancel={() => {
            setShowNew(false);
            setCreateError(null);
          }}
          onCreate={(body) => {
            setCreateError(null);
            createPeriod.mutate(body, {
              onSuccess: () => setShowNew(false),
              onError: (err) => setCreateError(err instanceof ApiError ? err.message : "Could not create."),
            });
          }}
        />
      )}
    </div>
  );
}
