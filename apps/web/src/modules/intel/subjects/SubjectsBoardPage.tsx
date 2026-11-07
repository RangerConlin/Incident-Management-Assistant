import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import FilterBar from "../../../components/table/FilterBar";
import KpiStrip from "../../../components/KpiStrip";
import StatusPill from "../../../components/table/StatusPill";
import { SUBJECT_STATUSES, SUBJECT_TYPES } from "../../../api/endpoints";
import type { IntelSubject } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { formatDateTime } from "../../../utils/formatDateTime";
import NewSubjectDialog from "./NewSubjectDialog";
import { useCreateSubject, useSubjectRows } from "./hooks";

// Matches desktop's subjects_tab.py profile_box exactly: 8 per-type
// quick-create buttons (Missing Person – Quick styled primary — fastest
// path to get a profile on record), not folded into one generic button.
const CREATE_BUTTONS: { label: string; type: string; quick: boolean; primary?: boolean }[] = [
  { label: "Missing Person – Quick", type: "Missing Person", quick: true, primary: true },
  { label: "Missing Person – Full", type: "Missing Person", quick: false },
  { label: "Witness", type: "Witness", quick: false },
  { label: "Reporting Party", type: "Reporting Party", quick: false },
  { label: "Contact", type: "Contact", quick: false },
  { label: "Patient", type: "Patient", quick: false },
  { label: "Vehicle", type: "Vehicle", quick: false },
  { label: "Aircraft", type: "Aircraft", quick: false },
];

function context(s: IntelSubject): string {
  if (s.subject_type === "Missing Person") return [s.lkp_place, s.lkp_time].filter(Boolean).join(", ") || "—";
  return s.description || s.relationship_to_incident || "—";
}

export default function SubjectsBoardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [newDialog, setNewDialog] = useState<{ type: string; quick: boolean } | null>(null);

  const { data: rows = [], isLoading, error } = useSubjectRows(incidentId!);
  const createSubject = useCreateSubject(incidentId!);

  const filteredRows = useMemo(
    () =>
      rows.filter((s) => {
        if (typeFilter && s.subject_type !== typeFilter) return false;
        if (statusFilter && s.status !== statusFilter) return false;
        if (search && !s.name.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      }),
    [rows, search, typeFilter, statusFilter],
  );

  const kpiTiles = useMemo(() => {
    const count = (pred: (s: IntelSubject) => boolean) => rows.filter(pred).length;
    return [
      { key: "total", value: rows.length, label: "Total" },
      { key: "missing", value: count((s) => s.subject_type === "Missing Person"), label: "Missing Person", accent: "var(--status-severity-warning-bg)" },
      { key: "located", value: count((s) => s.status === "Located"), label: "Located", accent: "var(--status-intel-subject-status-located-bg)" },
      { key: "deceased", value: count((s) => s.status === "Deceased"), label: "Deceased", accent: "var(--status-intel-subject-status-deceased-bg)" },
    ];
  }, [rows]);

  if (!incidentId) return null;

  return (
    <div>
      <h2>Subjects</h2>
      <KpiStrip tiles={kpiTiles} />

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
          {SUBJECT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {SUBJECT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </FilterBar>

      <div className="command-panel" style={{ marginBottom: 14 }}>
        <h3>Create Profiles</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {CREATE_BUTTONS.map((b) => (
            <button
              key={b.label}
              className={b.primary ? undefined : "secondary"}
              style={{ width: "auto" }}
              onClick={() => setNewDialog({ type: b.type, quick: b.quick })}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="error">Could not load subjects.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable<IntelSubject>
          tableId="intel-subjects"
          columns={
            [
              { key: "name", header: "Name", sortable: true, sortValue: (s) => s.name, defaultWidth: 180 },
              { key: "subject_type", header: "Type", sortable: true, sortValue: (s) => s.subject_type, defaultWidth: 140 },
              {
                key: "status",
                header: "Status",
                render: (s) => <StatusPill domain="intel-subject-status" statusKey={s.status} />,
                defaultWidth: 110,
              },
              { key: "context", header: "LKP / Context", render: context, defaultWidth: 260 },
              { key: "age", header: "Age", render: (s) => (s.age != null ? String(s.age) : "—"), defaultWidth: 70 },
              { key: "updated_at", header: "Updated", render: (s) => formatDateTime(s.updated_at), defaultWidth: 130 },
            ] as ColumnDef<IntelSubject>[]
          }
          rows={filteredRows}
          rowKey={(s) => s.id}
          onRowActivate={(s) => navigate(`/intel/subjects/${s.id}`)}
          emptyMessage="No subjects yet. Use Create Profiles above to add one."
        />
      )}

      <p style={{ fontSize: "0.75rem", opacity: 0.6, marginTop: 10 }}>
        <StatusPill domain="intel-subject-status" statusKey="Active" label="Missing Person" /> ·{" "}
        <StatusPill domain="intel-subject-status" statusKey="Located" label="Located" /> ·{" "}
        <StatusPill domain="intel-subject-status" statusKey="Deceased" label="Deceased" />
      </p>

      {newDialog && (
        <NewSubjectDialog
          initialType={newDialog.type}
          initialQuick={newDialog.quick}
          busy={createSubject.isPending}
          onCancel={() => setNewDialog(null)}
          onCreate={(body) =>
            createSubject.mutate(
              { ...body, created_by: user?.display_name },
              { onSuccess: () => setNewDialog(null) },
            )
          }
        />
      )}
    </div>
  );
}
