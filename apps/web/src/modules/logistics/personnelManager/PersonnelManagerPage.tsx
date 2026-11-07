import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import "../logistics.css";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import StatusPill from "../../../components/table/StatusPill";
import type { CheckinRosterRow } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { useCheckinHistory, useCheckinRoster, useSetCheckinStatus } from "../checkin/hooks";

const STATUS_FILTER_OPTIONS = [
  "All",
  "Available",
  "Assigned",
  "Checked In",
  "Enroute",
  "Out of Service",
  "Preparing for Demobilization",
  "Demobilized",
  "Cancelled",
];

const QUICK_STATUSES = ["Available", "Assigned", "Preparing for Demobilization", "Demobilized"];

export default function PersonnelManagerPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [selected, setSelected] = useState<CheckinRosterRow | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  if (!incidentId) return null;

  const { data: roster = [], isLoading, refetch } = useCheckinRoster(incidentId, {
    q: search,
    ci_status: statusFilter === "All" ? undefined : statusFilter,
    include_no_show: includeInactive,
  });
  const setStatus = useSetCheckinStatus(incidentId);

  const summary = useMemo(() => {
    const total = roster.length;
    const assigned = roster.filter((r) => r.status === "Assigned").length;
    const available = roster.filter((r) => r.status === "Available" || r.status === "Checked In").length;
    const demob = roster.filter((r) => r.status === "Demobilized").length;
    return `${total} personnel · ${available} available · ${assigned} assigned · ${demob} demobilized`;
  }, [roster]);

  const columns: ColumnDef<CheckinRosterRow>[] = [
    { key: "name", header: "Name", sortable: true, sortValue: (r) => r.name, defaultWidth: 190 },
    { key: "person_id", header: "ID", defaultWidth: 100 },
    { key: "role", header: "Role", defaultWidth: 140, render: (r) => r.role ?? "—" },
    { key: "team", header: "Team", defaultWidth: 140, render: (r) => r.team || "—" },
    { key: "callsign", header: "Callsign", defaultWidth: 110, render: (r) => r.callsign || "—" },
    { key: "phone", header: "Phone", defaultWidth: 130, render: (r) => r.phone || "—" },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (r) => r.status,
      render: (r) => <StatusPill domain="resource" statusKey={r.status} />,
      defaultWidth: 170,
    },
    { key: "updated_at", header: "Updated", defaultWidth: 150, render: (r) => r.updated_at || "—" },
  ];

  return (
    <div>
      <div className="page-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Personnel Manager</h2>
        <div style={{ color: "#9aa0a8", fontSize: "0.85rem", textAlign: "right" }}>{summary}</div>
      </div>

      <div className="logistics-toolbar">
        <div className="field" style={{ minWidth: 220 }}>
          <label>Search</label>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, ID, callsign, or phone" />
        </div>
        <div className="field">
          <label>Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            {STATUS_FILTER_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>&nbsp;</label>
          <select value={includeInactive ? "include" : "active"} onChange={(e) => setIncludeInactive(e.target.value === "include")}>
            <option value="active">Active only</option>
            <option value="include">Include not coming</option>
          </select>
        </div>
        <button className="ghost" style={{ width: "auto" }} onClick={() => refetch()}>
          Refresh
        </button>
        <button className="secondary" style={{ width: "auto" }} onClick={() => navigate("/logistics/checkin")}>
          Open Check-In
        </button>
        <button
          className="ghost"
          style={{ width: "auto" }}
          disabled={!selected}
          onClick={() => selected && navigate(`/logistics/resources/personnel/${selected.person_record}`)}
        >
          Open Selected
        </button>
        <button className="ghost" style={{ width: "auto" }} disabled={!selected} onClick={() => setShowHistory(true)}>
          History
        </button>
      </div>

      <div className="action-row">
        {QUICK_STATUSES.map((status) => (
          <button
            key={status}
            className="secondary"
            disabled={!selected || setStatus.isPending}
            onClick={() => selected && setStatus.mutate({ personRecord: selected.person_record, status })}
          >
            {status === "Preparing for Demobilization" ? "Prep Demob" : status}
          </button>
        ))}
        <span className="hint" style={{ alignSelf: "center" }}>
          Select a row, then apply a status.
        </span>
      </div>

      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="personnel-manager-roster"
          columns={columns}
          rows={roster}
          rowKey={(r) => r.person_record}
          onRowClick={(r) => setSelected(r)}
          onRowActivate={(r) => navigate(`/logistics/resources/personnel/${r.person_record}`)}
          emptyMessage="No personnel match these filters."
        />
      )}

      {showHistory && selected && (
        <PersonnelHistoryDialog incidentId={incidentId} person={selected} onClose={() => setShowHistory(false)} />
      )}
    </div>
  );
}

function PersonnelHistoryDialog({
  incidentId,
  person,
  onClose,
}: {
  incidentId: string;
  person: CheckinRosterRow;
  onClose: () => void;
}) {
  const { data: history = [], isLoading } = useCheckinHistory(incidentId, person.person_record);
  return (
    <div className="modal-backdrop open">
      <div className="modal" style={{ maxWidth: 560 }}>
        <h3>
          Status History — {person.name} {person.person_id ? `(${person.person_id})` : ""}
        </h3>
        {isLoading ? (
          <p>Loading…</p>
        ) : history.length === 0 ? (
          <p style={{ opacity: 0.6 }}>No history recorded yet.</p>
        ) : (
          <table className="team-roster">
            <thead>
              <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Actor</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i}>
                  <td>{h.ts}</td>
                  <td>{h.event_type}</td>
                  <td>{h.actor || "—"}</td>
                  <td>{String(h.payload?.status ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="modal-actions">
          <button className="ghost" onClick={onClose} style={{ flex: "none" }}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
