import { useMemo, useState } from "react";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import ElapsedTime from "../../../components/table/ElapsedTime";
import FilterBar from "../../../components/table/FilterBar";
import { useSession } from "../../../auth/SessionContext";
import type { CommsLogEntry } from "../../../api/types";
import { COMMS_DISPOSITION_OPTIONS, COMMS_PRIORITY_OPTIONS, useAddCommsLogEntry, useCommsLog, useUpdateCommsLogEntry } from "./hooks";

export default function CommsLogPage() {
  const { incidentId, user } = useSession();
  const [search, setSearch] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [dispositionFilter, setDispositionFilter] = useState("");
  const [followUpOnly, setFollowUpOnly] = useState(false);
  const [showNewEntry, setShowNewEntry] = useState(false);

  const filters = useMemo(() => {
    const f: Record<string, string | boolean> = {};
    if (search) f.text_search = search;
    if (priorityFilter) f.priorities = priorityFilter;
    if (dispositionFilter) f.dispositions = dispositionFilter;
    if (followUpOnly) f.follow_up_required = true;
    return f;
  }, [search, priorityFilter, dispositionFilter, followUpOnly]);

  const { data: rows = [], isLoading, error } = useCommsLog(incidentId!, filters);
  const updateEntry = useUpdateCommsLogEntry(incidentId!);

  const columns: ColumnDef<CommsLogEntry>[] = [
    {
      key: "ts_utc",
      header: "Time",
      sortable: true,
      sortValue: (r) => r.ts_utc,
      render: (r) => <ElapsedTime since={r.ts_utc} />,
      defaultWidth: 100,
    },
    {
      key: "priority",
      header: "Priority",
      defaultWidth: 110,
      render: (r) => (
        <select value={r.priority} onChange={(e) => r.id != null && updateEntry.mutate({ entryId: r.id, patch: { priority: e.target.value } })}>
          {COMMS_PRIORITY_OPTIONS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      ),
    },
    { key: "from_unit", header: "From", defaultWidth: 120 },
    { key: "to_unit", header: "To", defaultWidth: 120 },
    { key: "message", header: "Message", defaultWidth: 280 },
    { key: "resource_label", header: "Resource", defaultWidth: 130 },
    {
      key: "disposition",
      header: "Disposition",
      defaultWidth: 120,
      render: (r) => (
        <select
          value={r.disposition}
          onChange={(e) => r.id != null && updateEntry.mutate({ entryId: r.id, patch: { disposition: e.target.value } })}
        >
          {COMMS_DISPOSITION_OPTIONS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "follow_up_required",
      header: "Follow-Up",
      defaultWidth: 90,
      render: (r) => (r.follow_up_required ? "⚠ Yes" : "—"),
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Communications Traffic Log</h2>
        <button style={{ width: "auto" }} onClick={() => setShowNewEntry(true)}>
          New Entry
        </button>
      </div>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        activeFilters={[
          ...(priorityFilter ? [{ key: "priority", label: `Priority: ${priorityFilter}` }] : []),
          ...(dispositionFilter ? [{ key: "disposition", label: `Disposition: ${dispositionFilter}` }] : []),
          ...(followUpOnly ? [{ key: "followup", label: "Follow-Up Required" }] : []),
        ]}
        onClearFilter={(key) => {
          if (key === "priority") setPriorityFilter("");
          if (key === "disposition") setDispositionFilter("");
          if (key === "followup") setFollowUpOnly(false);
        }}
        onResetAll={() => {
          setPriorityFilter("");
          setDispositionFilter("");
          setFollowUpOnly(false);
        }}
      >
        <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
          <option value="">All priorities</option>
          {COMMS_PRIORITY_OPTIONS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select value={dispositionFilter} onChange={(e) => setDispositionFilter(e.target.value)}>
          <option value="">All dispositions</option>
          {COMMS_DISPOSITION_OPTIONS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <input type="checkbox" checked={followUpOnly} onChange={(e) => setFollowUpOnly(e.target.checked)} />
          Follow-up required
        </label>
      </FilterBar>

      {error && <p className="error">Could not load the traffic log.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="comms-traffic-log"
          columns={columns}
          rows={rows}
          rowKey={(r) => r.comms_id}
          getRowClassName={(r) => (r.priority === "Emergency" ? "row-emergency" : undefined)}
          emptyMessage="No traffic logged yet."
        />
      )}

      {showNewEntry && (
        <NewEntryDialog
          incidentId={incidentId}
          operatorName={user?.display_name}
          onClose={() => setShowNewEntry(false)}
        />
      )}
    </div>
  );
}

function NewEntryDialog({
  incidentId,
  operatorName,
  onClose,
}: {
  incidentId: string;
  operatorName?: string;
  onClose: () => void;
}) {
  const addEntry = useAddCommsLogEntry(incidentId);
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState("Routine");
  const [fromUnit, setFromUnit] = useState("");
  const [toUnit, setToUnit] = useState("");
  const [resourceLabel, setResourceLabel] = useState("");

  const submit = () => {
    if (!message.trim()) return;
    addEntry.mutate(
      {
        message: message.trim(),
        priority,
        from_unit: fromUnit,
        to_unit: toUnit,
        resource_label: resourceLabel,
        operator_display_name: operatorName,
        follow_up_required: priority === "Emergency",
      },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Traffic Log Entry</h3>
        <div className="field">
          <label>Message</label>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label>Priority</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            {COMMS_PRIORITY_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>From</label>
          <input value={fromUnit} onChange={(e) => setFromUnit(e.target.value)} />
        </div>
        <div className="field">
          <label>To</label>
          <input value={toUnit} onChange={(e) => setToUnit(e.target.value)} />
        </div>
        <div className="field">
          <label>Resource</label>
          <input value={resourceLabel} onChange={(e) => setResourceLabel(e.target.value)} />
        </div>
        <div className="modal-actions">
          <button className="secondary" style={{ width: "auto" }} onClick={onClose}>
            Cancel
          </button>
          <button style={{ width: "auto" }} disabled={!message.trim() || addEntry.isPending} onClick={submit}>
            Log Entry
          </button>
        </div>
      </div>
    </div>
  );
}
