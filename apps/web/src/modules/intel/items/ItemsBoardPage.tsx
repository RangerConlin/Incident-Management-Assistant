import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import FilterBar from "../../../components/table/FilterBar";
import KpiStrip from "../../../components/KpiStrip";
import StatusPill from "../../../components/table/StatusPill";
import { ITEM_TREND_VALUES, ITEM_TYPES, LEAD_PRIORITIES } from "../../../api/endpoints";
import type { IntelItem } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { formatDateTime } from "../../../utils/formatDateTime";
import NewItemDialog from "./NewItemDialog";
import { useCreateItem, useItemRows } from "./hooks";

export default function ItemsBoardPage() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [trendFilter, setTrendFilter] = useState("");
  const [showNew, setShowNew] = useState(false);

  const { data: rows = [], isLoading, error } = useItemRows(incidentId!);
  const createItem = useCreateItem(incidentId!);

  const filteredRows = useMemo(
    () =>
      rows.filter((i) => {
        if (typeFilter && i.item_type !== typeFilter) return false;
        if (priorityFilter && i.priority !== priorityFilter) return false;
        if (trendFilter && i.trend !== trendFilter) return false;
        if (search && !`${i.title} ${i.item_type}`.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      }),
    [rows, search, typeFilter, priorityFilter, trendFilter],
  );

  const kpiTiles = useMemo(() => {
    const count = (pred: (i: IntelItem) => boolean) => rows.filter(pred).length;
    return [
      { key: "total", value: rows.length, label: "Total" },
      { key: "critical", value: count((i) => i.priority === "Critical"), label: "Critical", accent: "var(--status-severity-critical-bg)" },
      { key: "worsening", value: count((i) => i.trend === "Worsening"), label: "Worsening Trend", accent: "var(--status-intel-trend-worsening-bg)" },
      { key: "ruled_out", value: count((i) => i.confidence === "Ruled Out"), label: "Ruled Out", accent: "var(--status-severity-info-bg)" },
    ];
  }, [rows]);

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Intel Items</h2>
        <button style={{ width: "auto" }} onClick={() => setShowNew(true)}>
          + New Intel Item
        </button>
      </div>

      <KpiStrip tiles={kpiTiles} />

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        activeFilters={[
          ...(typeFilter ? [{ key: "type", label: `Type: ${typeFilter}` }] : []),
          ...(priorityFilter ? [{ key: "priority", label: `Priority: ${priorityFilter}` }] : []),
          ...(trendFilter ? [{ key: "trend", label: `Trend: ${trendFilter}` }] : []),
        ]}
        onClearFilter={(key) => (key === "type" ? setTypeFilter("") : key === "priority" ? setPriorityFilter("") : setTrendFilter(""))}
        onResetAll={() => {
          setTypeFilter("");
          setPriorityFilter("");
          setTrendFilter("");
        }}
      >
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          {ITEM_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
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
        <select value={trendFilter} onChange={(e) => setTrendFilter(e.target.value)}>
          <option value="">All trends</option>
          {ITEM_TREND_VALUES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load intel items.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable<IntelItem>
          tableId="intel-items"
          columns={
            [
              { key: "item_type", header: "Type", sortable: true, sortValue: (i) => i.item_type, defaultWidth: 150 },
              { key: "title", header: "Description", sortable: true, sortValue: (i) => i.title, defaultWidth: 260 },
              { key: "status", header: "Status", render: (i) => i.status, defaultWidth: 90 },
              { key: "priority", header: "Priority", render: (i) => <StatusPill domain="intel-priority" statusKey={i.priority} />, defaultWidth: 100 },
              { key: "confidence", header: "Confidence", render: (i) => <StatusPill domain="intel-confidence" statusKey={i.confidence} />, defaultWidth: 120 },
              { key: "trend", header: "Trend", render: (i) => <StatusPill domain="intel-trend" statusKey={i.trend} />, defaultWidth: 100 },
              { key: "observations", header: "Obs", render: (i) => String(i.observations.length), defaultWidth: 60 },
              { key: "location_text", header: "Location", render: (i) => i.location_text || "—", defaultWidth: 160 },
              { key: "updated_at", header: "Updated", render: (i) => formatDateTime(i.updated_at), defaultWidth: 130 },
            ] as ColumnDef<IntelItem>[]
          }
          rows={filteredRows}
          rowKey={(i) => i.id}
          onRowActivate={(i) => navigate(`/intel/items/${i.id}`)}
          emptyMessage="No intel items yet. Click New Intel Item to add one."
        />
      )}

      {showNew && (
        <NewItemDialog
          busy={createItem.isPending}
          onCancel={() => setShowNew(false)}
          onCreate={(body) => createItem.mutate({ ...body, created_by: user?.display_name }, { onSuccess: () => setShowNew(false) })}
        />
      )}
    </div>
  );
}
