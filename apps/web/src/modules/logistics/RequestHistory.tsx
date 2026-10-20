import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import type { LogisticsRecord } from "../../api/types";
import { formatDateTime } from "../../utils/formatDateTime";
export default function RequestHistory({ approvals, audit }: { approvals: LogisticsRecord[]; audit: LogisticsRecord[] }) {
  const columns: ColumnDef<LogisticsRecord & { row: number }>[] = [
    { key: "ts_utc", header: "When", defaultWidth: 190, render: r => formatDateTime(String(r.ts_utc ?? "")) },
    { key: "event", header: "Event / action", defaultWidth: 200, render: r => String(r.event ?? r.action ?? "") },
    { key: "actor_id", header: "Actor" }, { key: "note", header: "Note", defaultWidth: 260 },
    { key: "change", header: "Change", defaultWidth: 220, render: r => r.old || r.new ? `${r.old ?? ""} → ${r.new ?? ""}` : Array.isArray(r.fields) ? r.fields.join(", ") : "" },
  ];
  return <><section className="logistics-panel"><h3>Approval history</h3><DataTable tableId="logistics-request-approvals" columns={columns} rows={approvals.map((r,row) => ({ ...r,row }))} rowKey={r => r.row} emptyMessage="No approvals recorded." /></section>
    <section className="logistics-panel"><h3>Audit history</h3><DataTable tableId="logistics-request-audit" columns={columns} rows={audit.map((r,row) => ({ ...r,row }))} rowKey={r => r.row} emptyMessage="No audit events recorded." /></section></>;
}
