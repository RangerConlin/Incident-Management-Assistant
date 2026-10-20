import FormExportControls from "../../forms/FormExportControls";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import FilterBar from "../../../components/table/FilterBar";
import StatusPill from "../../../components/table/StatusPill";
import type { Meeting } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import NewMeetingDialog from "./NewMeetingDialog";
import { useCreateMeeting, useMeetings } from "./hooks";

const STATUSES = ["draft", "scheduled", "ready", "completed", "canceled"];

export default function MeetingsBoardPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showNew, setShowNew] = useState(false);

  const { data: rows = [], isLoading, error } = useMeetings(incidentId!);
  const createMeeting = useCreateMeeting(incidentId!);

  const filteredRows = useMemo(() => {
    return rows.filter((m) => {
      if (statusFilter && m.status !== statusFilter) return false;
      if (search) {
        const haystack = `${m.title} ${m.owner} ${m.location}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [rows, search, statusFilter]);

  const columns: ColumnDef<Meeting>[] = [
    { key: "title", header: "Title", sortable: true, sortValue: (m) => m.title, defaultWidth: 220 },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (m) => m.status,
      render: (m) => <StatusPill domain="meeting" statusKey={m.status} />,
      defaultWidth: 110,
    },
    { key: "meeting_date", header: "Date", defaultWidth: 110 },
    { key: "start_time", header: "Start", defaultWidth: 90 },
    { key: "location", header: "Location", render: (m) => m.location || "—", defaultWidth: 150 },
    { key: "owner", header: "Owner", render: (m) => m.owner || "—", defaultWidth: 150 },
    {
      key: "attendees",
      header: "Attendees",
      render: (m) => m.attendees.length,
      defaultWidth: 90,
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <FormExportControls formIds={["ics_230"]} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Meetings</h2>
        <button style={{ width: "auto" }} onClick={() => setShowNew(true)}>
          New Meeting
        </button>
      </div>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        activeFilters={statusFilter ? [{ key: "status", label: `Status: ${statusFilter}` }] : []}
        onClearFilter={() => setStatusFilter("")}
        onResetAll={() => setStatusFilter("")}
      >
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <p className="error">Could not load meetings.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="planning-meetings-board"
          columns={columns}
          rows={filteredRows}
          rowKey={(m) => m.id}
          onRowActivate={(m) => navigate(`/planning/meetings/${m.id}`)}
          emptyMessage="No meetings yet. Click New Meeting to create one."
        />
      )}

      {showNew && (
        <NewMeetingDialog
          busy={createMeeting.isPending}
          onCancel={() => setShowNew(false)}
          onCreate={(body) => createMeeting.mutate(body, { onSuccess: () => setShowNew(false) })}
        />
      )}
    </div>
  );
}
