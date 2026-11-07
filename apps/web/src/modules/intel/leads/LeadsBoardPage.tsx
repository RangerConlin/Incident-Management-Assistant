import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import FilterBar from "../../../components/table/FilterBar";
import KpiStrip from "../../../components/KpiStrip";
import StatusPill from "../../../components/table/StatusPill";
import { INFORMATION_CONFIDENCE_VALUES, LEAD_PRIORITIES, LEAD_SOURCE_CATEGORIES, LEAD_STATUSES } from "../../../api/endpoints";
import type { IntelLead } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { formatDateTime } from "../../../utils/formatDateTime";
import AssignLeadDialog from "./AssignLeadDialog";
import NewLeadDialog from "./NewLeadDialog";
import { useAssignLead, useConvertLead, useCreateLead, useLeadRows } from "./hooks";

function displayNumber(l: IntelLead): string {
  return l.lead_number ? `L-${String(l.lead_number).padStart(3, "0")}` : "—";
}

export default function LeadsBoardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [confidenceFilter, setConfidenceFilter] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [assigning, setAssigning] = useState<IntelLead | null>(null);

  const { data: rows = [], isLoading, error } = useLeadRows(incidentId!);
  const createLead = useCreateLead(incidentId!);
  const convertLead = useConvertLead(incidentId!);
  const assignLead = useAssignLead(incidentId!);

  const filteredRows = useMemo(
    () =>
      rows.filter((l) => {
        if (statusFilter && l.status !== statusFilter) return false;
        if (priorityFilter && l.priority !== priorityFilter) return false;
        if (sourceFilter && l.source_category !== sourceFilter) return false;
        if (confidenceFilter && l.information_confidence !== confidenceFilter) return false;
        if (search && !`${l.title} ${l.summary}`.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      }),
    [rows, search, statusFilter, priorityFilter, sourceFilter, confidenceFilter],
  );

  const kpiTiles = useMemo(() => {
    const count = (pred: (l: IntelLead) => boolean) => rows.filter(pred).length;
    return [
      { key: "total", value: rows.length, label: "Total" },
      { key: "open", value: count((l) => !["Closed", "Rejected", "Converted"].includes(l.status)), label: "Open", accent: "var(--status-severity-info-bg)" },
      { key: "unassigned", value: count((l) => !l.assigned_to), label: "Unassigned", accent: "var(--status-severity-warning-bg)" },
      { key: "critical", value: count((l) => ["Critical", "High"].includes(l.priority)), label: "Critical / High Priority", accent: "var(--status-severity-critical-bg)" },
      { key: "converted", value: count((l) => l.status === "Converted"), label: "Converted", accent: "var(--status-intel-lead-status-converted-bg)" },
    ];
  }, [rows]);

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Leads</h2>
        <button style={{ width: "auto" }} onClick={() => setShowNew(true)}>
          + New Lead
        </button>
      </div>

      <KpiStrip tiles={kpiTiles} />

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        activeFilters={[
          ...(statusFilter ? [{ key: "status", label: `Status: ${statusFilter}` }] : []),
          ...(priorityFilter ? [{ key: "priority", label: `Priority: ${priorityFilter}` }] : []),
          ...(sourceFilter ? [{ key: "source", label: `Source: ${sourceFilter}` }] : []),
          ...(confidenceFilter ? [{ key: "confidence", label: `Confidence: ${confidenceFilter}` }] : []),
        ]}
        onClearFilter={(key) =>
          key === "status" ? setStatusFilter("") : key === "priority" ? setPriorityFilter("") : key === "source" ? setSourceFilter("") : setConfidenceFilter("")
        }
        onResetAll={() => {
          setStatusFilter("");
          setPriorityFilter("");
          setSourceFilter("");
          setConfidenceFilter("");
        }}
      >
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {LEAD_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
          <option value="">All priorities</option>
          {LEAD_PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
          <option value="">All sources</option>
          {LEAD_SOURCE_CATEGORIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={confidenceFilter} onChange={(e) => setConfidenceFilter(e.target.value)}>
          <option value="">All confidence</option>
          {INFORMATION_CONFIDENCE_VALUES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load leads.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable<IntelLead>
          tableId="intel-leads"
          columns={
            [
              { key: "number", header: "#", render: displayNumber, defaultWidth: 70 },
              { key: "title", header: "Title", sortable: true, sortValue: (l) => l.title, defaultWidth: 240 },
              { key: "priority", header: "Priority", render: (l) => <StatusPill domain="intel-priority" statusKey={l.priority} />, defaultWidth: 100 },
              { key: "status", header: "Status", render: (l) => <StatusPill domain="intel-lead-status" statusKey={l.status} />, defaultWidth: 110 },
              { key: "source_category", header: "Source", render: (l) => l.source_category || l.source_type || "—", defaultWidth: 130 },
              { key: "information_confidence", header: "Confidence", render: (l) => (l.information_confidence ? <StatusPill domain="intel-confidence" statusKey={l.information_confidence} /> : "—"), defaultWidth: 120 },
              { key: "location_text", header: "Location", render: (l) => l.location_text || "—", defaultWidth: 150 },
              { key: "assigned_to", header: "Assigned To", render: (l) => l.assigned_to || "Unassigned", defaultWidth: 130 },
              { key: "updated_at", header: "Updated", render: (l) => formatDateTime(l.updated_at), defaultWidth: 130 },
              {
                key: "actions",
                header: "Actions",
                render: (l) => (
                  <div style={{ display: "flex", gap: 6 }}>
                    <button className="secondary" style={{ width: "auto" }} onClick={() => navigate(`/intel/leads/${l.id}`)}>
                      View
                    </button>
                    <button className="secondary" style={{ width: "auto" }} onClick={() => setAssigning(l)}>
                      Assign
                    </button>
                    <button
                      className="secondary"
                      style={{ width: "auto" }}
                      disabled={l.status === "Converted" || convertLead.isPending}
                      onClick={() => convertLead.mutate({ lead: l, actor: user?.display_name })}
                    >
                      → Item
                    </button>
                  </div>
                ),
                defaultWidth: 220,
              },
            ] as ColumnDef<IntelLead>[]
          }
          rows={filteredRows}
          rowKey={(l) => l.id}
          onRowActivate={(l) => navigate(`/intel/leads/${l.id}`)}
          emptyMessage="No leads yet. Click New Lead to add one."
        />
      )}

      {showNew && (
        <NewLeadDialog
          busy={createLead.isPending}
          onCancel={() => setShowNew(false)}
          onCreate={(body) => createLead.mutate({ ...body, created_by: user?.display_name }, { onSuccess: () => setShowNew(false) })}
        />
      )}

      {assigning && (
        <AssignLeadDialog
          leadLabel={displayNumber(assigning)}
          initialValue={assigning.assigned_to ?? ""}
          onCancel={() => setAssigning(null)}
          onAssign={(name) => {
            assignLead.mutate({ leadId: assigning.id, name }, { onSuccess: () => setAssigning(null) });
          }}
        />
      )}
    </div>
  );
}
