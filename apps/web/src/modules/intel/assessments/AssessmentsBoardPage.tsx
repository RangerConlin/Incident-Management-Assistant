import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import FilterBar from "../../../components/table/FilterBar";
import KpiStrip from "../../../components/KpiStrip";
import StatusPill from "../../../components/table/StatusPill";
import { ASSESSMENT_STATUSES } from "../../../api/endpoints";
import type { IntelAssessment } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { formatDateTime } from "../../../utils/formatDateTime";
import NewAssessmentDialog from "./NewAssessmentDialog";
import { useAssessmentRows, useCreateAssessment } from "./hooks";

function displayNumber(a: IntelAssessment): string {
  return a.assessment_number ? `A-${String(a.assessment_number).padStart(3, "0")}` : "—";
}

export default function AssessmentsBoardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showNew, setShowNew] = useState(false);

  const { data: rows = [], isLoading, error } = useAssessmentRows(incidentId!);
  const createAssessment = useCreateAssessment(incidentId!);

  const filteredRows = useMemo(
    () =>
      rows.filter((a) => {
        if (statusFilter && a.status !== statusFilter) return false;
        if (search && !`${a.title} ${a.summary}`.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      }),
    [rows, search, statusFilter],
  );

  const kpiTiles = useMemo(() => {
    const count = (pred: (a: IntelAssessment) => boolean) => rows.filter(pred).length;
    return [
      { key: "total", value: rows.length, label: "Total" },
      { key: "draft", value: count((a) => a.status === "Draft"), label: "Draft", accent: "var(--status-intel-assessment-status-draft-bg)" },
      { key: "in_progress", value: count((a) => a.status === "In Progress"), label: "In Progress", accent: "var(--status-severity-warning-bg)" },
      { key: "complete", value: count((a) => a.status === "Complete"), label: "Complete", accent: "var(--status-intel-assessment-status-complete-bg)" },
    ];
  }, [rows]);

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Assessments</h2>
        <button style={{ width: "auto" }} onClick={() => setShowNew(true)}>
          + New Assessment
        </button>
      </div>
      <p className="muted" style={{ marginTop: -6 }}>
        Analytical products — findings and recommendations from linked Intel records.
      </p>

      <KpiStrip tiles={kpiTiles} />

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        activeFilters={statusFilter ? [{ key: "status", label: `Status: ${statusFilter}` }] : []}
        onClearFilter={() => setStatusFilter("")}
        onResetAll={() => setStatusFilter("")}
      >
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {ASSESSMENT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load assessments.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable<IntelAssessment>
          tableId="intel-assessments"
          columns={
            [
              { key: "number", header: "#", render: displayNumber, defaultWidth: 70 },
              { key: "title", header: "Title", sortable: true, sortValue: (a) => a.title, defaultWidth: 240 },
              { key: "status", header: "Status", render: (a) => <StatusPill domain="intel-assessment-status" statusKey={a.status} />, defaultWidth: 110 },
              { key: "analyst", header: "Analyst", render: (a) => a.analyst || "—", defaultWidth: 140 },
              {
                key: "findings",
                header: "Findings",
                render: (a) => (a.findings.length > 100 ? `${a.findings.slice(0, 100)}…` : a.findings || "—"),
                defaultWidth: 260,
              },
              { key: "updated_at", header: "Updated", render: (a) => formatDateTime(a.updated_at), defaultWidth: 130 },
            ] as ColumnDef<IntelAssessment>[]
          }
          rows={filteredRows}
          rowKey={(a) => a.id}
          onRowActivate={(a) => navigate(`/intel/assessments/${a.id}`)}
          emptyMessage="No assessments yet. Click New Assessment to add one."
        />
      )}

      {showNew && (
        <NewAssessmentDialog
          busy={createAssessment.isPending}
          onCancel={() => setShowNew(false)}
          onCreate={(body) => createAssessment.mutate({ ...body, created_by: user?.display_name }, { onSuccess: () => setShowNew(false) })}
        />
      )}
    </div>
  );
}
