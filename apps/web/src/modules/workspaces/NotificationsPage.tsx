import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { acknowledgeNotification, dismissNotification, listNotifications } from "../../api/endpoints";
import type { IncidentNotification } from "../../api/types";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import { formatDateTime } from "../../utils/formatDateTime";
import "./workspaces.css";

export default function NotificationsPage() {
  const { incidentId, personnel } = useSession();
  const queryClient = useQueryClient();
  const personRecord = personnel?.person_record;
  const key = ["incident", incidentId, "notifications"];
  const query = useQuery({
    queryKey: [...key, personRecord],
    queryFn: () => listNotifications(incidentId!, personRecord!),
    enabled: Boolean(incidentId && personRecord),
    refetchInterval: 20_000,
  });
  const action = useMutation({
    mutationFn: (row: IncidentNotification) => row.requires_acknowledgement
      ? acknowledgeNotification(incidentId!, row.notification_id)
      : dismissNotification(incidentId!, row.notification_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const columns: ColumnDef<IncidentNotification>[] = [
    { key: "status", header: "Status", render: row => row.read ? "Read" : "Unread" },
    { key: "title", header: "Notification", render: row => <><strong>{row.title}</strong><br /><span>{row.message}</span></> },
    { key: "category", header: "Category" },
    { key: "source", header: "Source", render: row => row.source_label || row.source_type },
    { key: "created", header: "Created", render: row => formatDateTime(row.created_at), sortValue: row => row.created_at },
    { key: "action", header: "Action", render: row => row.read ? "—" : <button disabled={action.isPending} onClick={() => action.mutate(row)}>{row.requires_acknowledgement ? "Acknowledge" : "Mark read"}</button> },
  ];
  return <section className="workspace-page">
    <h1>Notifications</h1>
    <p>Incident alerts and approval requests addressed to you.</p>
    {!personRecord ? <p>Your account must be linked to personnel to receive notifications.</p> :
      query.isPending ? <p>Loading notifications…</p> :
      query.isError ? <p className="error" role="alert">Could not load notifications.</p> :
      <DataTable tableId="incident-notifications" columns={columns} rows={query.data ?? []} rowKey={row => row.notification_id} emptyMessage="No notifications." />}
  </section>;
}
