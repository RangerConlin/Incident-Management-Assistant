import { Link, useNavigate } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { attention, plannedVsActual, varianceLabel, type PlannedRecord } from "./model";

export default function ScheduleTable({ rows, now, emptyMessage }: { rows: PlannedRecord[]; now: number; emptyMessage: string }) {
  const navigate = useNavigate();
  const columns: ColumnDef<PlannedRecord>[] = [
    { key: "title", header: "Activity", defaultWidth: 260, sortable: true, sortValue: r => r.title.toLowerCase(), render: r => <Link to={`${r.id}`}>{r.title || `Activity #${r.id}`}</Link> },
    { key: "status", header: "Status", defaultWidth: 130, sortable: true, sortValue: r => r.status, render: r => <StatusPill domain="planned-schedule" statusKey={r.status} /> },
    { key: "flag", header: "Attention", defaultWidth: 220, render: r => { const a = attention(r, now); return a ? <span className={"pe-flag" + (a.kind === "starting-soon" ? " pe-flag-soft" : "")}>{a.label}</span> : "—"; } },
    { key: "starts_at", header: "Planned start", defaultWidth: 150, sortable: true, sortValue: r => r.starts_at, render: r => formatDateTime(r.starts_at) },
    { key: "ends_at", header: "Planned end", defaultWidth: 150, sortable: true, sortValue: r => r.ends_at, render: r => formatDateTime(r.ends_at) },
    { key: "actual_start_at", header: "Actual start", defaultWidth: 150, defaultVisible: true, sortable: true, sortValue: r => r.actual_start_at, render: r => formatDateTime(r.actual_start_at) },
    { key: "variance", header: "Start variance", defaultWidth: 140, render: r => varianceLabel(plannedVsActual(r).startVarianceMin) },
    { key: "kind", header: "Kind", defaultWidth: 110, sortable: true, sortValue: r => r.kind },
    { key: "owner", header: "Responsible", defaultWidth: 170, sortable: true, sortValue: r => r.assigned_to || r.owner, render: r => r.assigned_to || r.owner || "—" },
    { key: "location", header: "Location", defaultWidth: 160, defaultVisible: false, render: r => r.location || "—" },
  ];
  return <DataTable tableId="planned-schedule" columns={columns} rows={rows} rowKey={r => r.id} onRowActivate={r => navigate(`${r.id}`)} emptyMessage={emptyMessage} />;
}
