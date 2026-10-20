import type { ResourceRequestDetail } from "../../api/types";
import { formatDateTime } from "../../utils/formatDateTime";
import { label } from "./model";
export default function RequestPrintSummary({ request }: { request: ResourceRequestDetail }) {
  return <article className="logistics-print logistics-panel"><h1>Resource request summary</h1><h2>{request.title}</h2><p>Request {request.id} · Version {request.version} · {label(request.status)}</p>
    <p>Priority: {label(request.priority)} · Requesting section: {request.requesting_section || "Not recorded"}</p><p>Needed by: {formatDateTime(request.needed_by_utc)} · Delivery: {request.delivery_location || "Not recorded"}</p>
    <p className="logistics-text">{request.justification}</p><h3>Requested items</h3>{request.items?.length ? request.items.map(item => <p key={item.id}>{item.quantity} {item.unit} · {item.description} · {item.special_instructions}</p>) : <p>No separate line items recorded.</p>}
    <h3>Approvals</h3>{request.approvals?.length ? request.approvals.map((r,i) => <p key={i}>{formatDateTime(String(r.ts_utc ?? ""))} · {String(r.action)} · {String(r.actor_id ?? "")} · {String(r.note ?? "")}</p>) : <p>No approval actions recorded.</p>}
    <h3>Fulfillment</h3>{request.fulfillments?.length ? request.fulfillments.map(r => <p key={r.id}>{label(r.status)} · ETA {formatDateTime(r.eta_utc)} · {r.destination_location || request.delivery_location} · {r.note}</p>) : <p>No fulfillment recorded.</p>}
    <p>Created {formatDateTime(request.created_utc)} by {request.created_by_id} · Updated {formatDateTime(request.last_updated_utc)}</p>
  </article>;
}
