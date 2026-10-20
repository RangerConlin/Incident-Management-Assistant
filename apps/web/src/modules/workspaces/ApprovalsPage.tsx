import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { pendingApprovals } from "../../api/endpoints";
import { useSession } from "../../auth/SessionContext";
import ApprovalPanel from "../../components/approvals/ApprovalPanel";
import DataTable from "../../components/table/DataTable";
import { formatDateTime } from "../../utils/formatDateTime";
import "./workspaces.css";

export default function ApprovalsPage() {
  const { incidentId, personnel } = useSession();
  const [params, setParams] = useSearchParams();
  const person = personnel?.person_record;
  const query = useQuery({ queryKey: ["incident", incidentId, "approval_instances", "pending", person], queryFn: () => pendingApprovals(incidentId!, person!), enabled: !!person, refetchInterval: 20_000 });
  return <section className="workspace-page"><h1>Approvals</h1><p>Active approval steps assigned to you or your incident role.</p>
    {!person ? <p>Your account must be linked to a personnel record to view assigned approvals.</p> : <>
      {query.isPending && <p>Loading approvals…</p>}{query.error && <p className="error" role="alert">{query.error.message}</p>}
      <DataTable tableId="pending-approvals" rows={query.data ?? []} rowKey={r => `${r.entity_type}:${r.entity_id}:${r.step_id}`} columns={[
        { key: "label", header: "Approval step" }, { key: "role", header: "Role" }, { key: "entity_type", header: "Record type" }, { key: "entity_id", header: "Record ID" },
        { key: "activated_at", header: "Activated", render: r => formatDateTime(String(r.activated_at ?? "")) },
        { key: "open", header: "Actions", render: r => <button className="secondary" onClick={() => setParams({ type: String(r.entity_type), entity: String(r.entity_id) })}>Review</button> },
      ]} emptyMessage="No pending approvals assigned to you." />
      {params.get("type") && params.get("entity") && <ApprovalPanel key={`${params.get("type")}:${params.get("entity")}`} incidentId={incidentId!} entityType={params.get("type")!} entityId={params.get("entity")} />}
    </>}
  </section>;
}
