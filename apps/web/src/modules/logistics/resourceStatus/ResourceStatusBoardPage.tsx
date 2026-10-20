import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import ElapsedTime from "../../../components/table/ElapsedTime";
import FilterBar from "../../../components/table/FilterBar";
import StatusPill from "../../../components/table/StatusPill";
import type { ResourceStatusRow } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { RESOURCE_STATUS_OPTIONS, RESOURCE_TYPE_OPTIONS, useResourceStatusRows } from "./hooks";

export default function ResourceStatusBoardPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const { data: rows = [], isLoading, error } = useResourceStatusRows(incidentId!, typeFilter);

  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (search) {
        const haystack = `${r.resource_name} ${r.resource_type} ${r.assigned_to ?? ""} ${r.location ?? ""}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [rows, search, statusFilter]);

  const columns: ColumnDef<ResourceStatusRow>[] = [
    { key: "resource_type", header: "Type", sortable: true, sortValue: (r) => r.resource_type, defaultWidth: 110 },
    { key: "resource_name", header: "Name", sortable: true, sortValue: (r) => r.resource_name, defaultWidth: 180 },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (r) => r.status,
      render: (r) => <StatusPill domain="resource" statusKey={r.status} />,
      defaultWidth: 150,
    },
    { key: "assigned_to", header: "Assigned To", defaultWidth: 150, render: (r) => r.assigned_to ?? "—" },
    { key: "location", header: "Location", defaultWidth: 150, render: (r) => r.location ?? "—" },
    {
      key: "eta_utc",
      header: "ETA",
      defaultWidth: 110,
      render: (r) => (r.eta_utc ? new Date(r.eta_utc).toLocaleString() : "—"),
    },
    {
      key: "updated_at",
      header: "Last Update",
      render: (r) => <ElapsedTime since={r.updated_at} />,
      defaultWidth: 110,
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Resource Status Board</h2>
        <button className="secondary" style={{ width: "auto" }} onClick={() => navigate("/logistics/checkin")}>
          Check In a Resource
        </button>
      </div>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        activeFilters={[
          ...(typeFilter ? [{ key: "type", label: `Type: ${typeFilter}` }] : []),
          ...(statusFilter ? [{ key: "status", label: `Status: ${statusFilter}` }] : []),
        ]}
        onClearFilter={(key) => (key === "type" ? setTypeFilter("") : setStatusFilter(""))}
        onResetAll={() => {
          setTypeFilter("");
          setStatusFilter("");
        }}
      >
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          {RESOURCE_TYPE_OPTIONS.map((t) => (
            <option key={t.key} value={t.key}>
              {t.label}
            </option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {RESOURCE_STATUS_OPTIONS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load resources.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="resource-status-board"
          columns={columns}
          rows={filteredRows}
          rowKey={(r) => `${r.entity_type}:${r.record_id}`}
          onRowActivate={(r) => navigate(`/logistics/resources/${r.entity_type}/${r.record_id}`)}
          emptyMessage="No resources checked in yet."
        />
      )}
    </div>
  );
}
