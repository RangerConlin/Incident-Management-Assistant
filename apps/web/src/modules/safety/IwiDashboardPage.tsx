import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import { severityVar, type SeverityKey } from "../../styles/statusColors";
import { IWI_SEVERITIES, type IwiReport } from "../../api/types";
import { useCreateIwiReport, useIwiReports } from "./iwiHooks";

function severityKey(severity: string | null): SeverityKey {
  switch (severity) {
    case "CRITICAL":
      return "critical";
    case "SERIOUS":
      return "warning";
    case "MODERATE":
      return "info";
    default:
      return "good";
  }
}

function SeverityBadge({ severity }: { severity: string | null }) {
  if (!severity) return <span className="muted">—</span>;
  const sev = severityVar(severityKey(severity));
  return (
    <span className="flag" style={{ background: sev.bg, color: sev.fg }}>
      {severity}
    </span>
  );
}

// Matches desktop's modules/safety/panels/iwi_dashboard.py board — filters,
// columns, and severity coloring. The detail dialog is IwiDetailPage,
// reached by clicking a row (desktop opens iwi_detail_dialog.py the same
// way).
export default function IwiDashboardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const { data: reports = [], isLoading, error } = useIwiReports(incidentId!, { severity, status });
  const createReport = useCreateIwiReport(incidentId!);

  if (!incidentId) return null;

  const columns: ColumnDef<IwiReport>[] = [
    { key: "form_number", header: "Form #", sortable: true, sortValue: (r) => r.form_number, defaultWidth: 90, render: (r) => `IWI-${String(r.form_number).padStart(3, "0")}` },
    { key: "date_of_occurrence", header: "Date", defaultWidth: 120, render: (r) => r.date_of_occurrence || "—" },
    { key: "time_of_occurrence", header: "Time", defaultWidth: 90, render: (r) => r.time_of_occurrence || "—" },
    { key: "incident_types", header: "Type(s)", defaultWidth: 160, render: (r) => r.incident_types.join(", ") || "—" },
    { key: "actual_severity", header: "Severity", defaultWidth: 110, render: (r) => <SeverityBadge severity={r.actual_severity} /> },
    { key: "location_general", header: "Location", defaultWidth: 160, render: (r) => r.location_general || "—" },
    { key: "persons_involved", header: "Persons", defaultWidth: 80, render: (r) => r.persons_involved.length },
    { key: "status", header: "Status", defaultWidth: 100 },
  ];

  const newReport = () => {
    createReport.mutate(
      { prepared_by: user?.display_name || user?.username || "" },
      { onSuccess: (created) => navigate(`/safety/iwi/${created._id}`) }
    );
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>IWI Dashboard</h2>
        <button type="button" style={{ width: "auto" }} disabled={createReport.isPending} onClick={newReport}>
          + New Report
        </button>
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">All severities</option>
          {IWI_SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="submitted">Submitted</option>
          <option value="reviewed">Reviewed</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      {error && <p className="error">Could not load IWI reports.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="iwi-dashboard"
          columns={columns}
          rows={reports}
          rowKey={(r) => r._id}
          onRowActivate={(r) => navigate(`/safety/iwi/${r._id}`)}
          emptyMessage="No IWI reports yet. Click + New Report to create one."
        />
      )}
    </div>
  );
}
