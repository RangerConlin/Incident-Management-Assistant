import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { useFacilities, useResourceRequest, useRequestWrites } from "./hooks";
import { approvalActions, APPROVAL_TARGETS, label, PRIORITIES, requestPatch, TERMINAL, TRANSITIONS, type ApprovalSection } from "./model";
import LogisticsFields from "./LogisticsFields";
import RequestItems from "./RequestItems";
import RequestFulfillments from "./RequestFulfillments";
import RequestHistory from "./RequestHistory";
import RequestPrintSummary from "./RequestPrintSummary";
import "./logistics.css";
const initial = { title: "", priority: "ROUTINE", requesting_section: "", needed_by_utc: "", delivery_location: "", delivery_facility_id: null, justification: "", comms_requirements: "", links: "" };
export default function ResourceRequestDetailPage() {
  const { requestId } = useParams(); const { incidentId } = useSession();
  return <Editor key={`${incidentId}:${requestId}`} incidentId={incidentId!} requestId={requestId!} />;
}
function Editor({ incidentId,requestId }: { incidentId: string; requestId: string }) {
  const isNew = requestId === "new"; const query = useResourceRequest(incidentId,requestId); const facilities = useFacilities(incidentId);
  const writes = useRequestWrites(incidentId,requestId); const { user } = useSession(); const actor = user?.user_id || user?.username || "";
  const navigate = useNavigate();
  const [patch,setPatch] = useState<Record<string,unknown>>({}); const [error,setError] = useState(""); const [notice,setNotice] = useState("");
  const [itemsDirty,setItemsDirty] = useState(false);
  const dirty = Object.keys(patch).length > 0;
  useEffect(() => { if (!dirty && !itemsDirty) return; const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; }; window.addEventListener("beforeunload",warn); return () => window.removeEventListener("beforeunload",warn); },[dirty,itemsDirty]);
  const values = { ...initial,...query.data,...patch }; const status = query.data?.status ?? "DRAFT"; const terminal = TERMINAL.includes(status);
  const busy = Object.values(writes).some(w => w.isPending); const update = (key: string,value: unknown) => { setPatch(old => {
    const next = { ...old,[key]:value };
    if (key === "delivery_facility_id" && value) {
      const facility = facilities.data?.find(f => f.id === value);
      if (facility) next.delivery_location = facility.name;
    }
    return next;
  }); setNotice(""); };
  const run = async (action: () => Promise<unknown>) => { setError(""); setNotice(""); try { await action(); } catch(e) { setError(e instanceof Error ? e.message : "Request failed. Your edits remain available."); } };
  const save = async () => {
    if (!String(values.title).trim()) throw new Error("Enter what is needed.");
    const body = isNew ? { ...values,status: "DRAFT",created_by_id: actor } : requestPatch(status,patch,actor);
    const saved = await writes.save.mutateAsync(body); setPatch({}); setNotice("Request saved."); if (isNew) navigate(`/logistics/resource-requests/${saved.id}`,{ replace: true });
  };
  const onApprovalAction = (action: string,section: ApprovalSection,note: string) => void run(async () => {
    await writes.approval.mutateAsync({ action,actor,note,section });
    setNotice(`${label(action.replace(/^FINANCE_/,""))} recorded.`);
  });
  const onStatusTransition = (target: string) => void run(async () => {
    await writes.status.mutateAsync({ status: target,actor,note: "" });
    setNotice(`Request marked ${label(target).toLowerCase()}.`);
  });
  if (!isNew && query.isPending) return <p role="status">Loading request…</p>;
  if (!isNew && (query.isError || !query.data)) return <p className="error" role="alert">Could not load this request. <button onClick={() => void query.refetch()}>Retry</button> <Link to="/logistics/resource-requests">Requests</Link></p>;
  // One scrollable page, no tabs: Details/Items/Fulfillment/Approvals all
  // stack top-to-bottom. Print drops to two toolbar buttons — the summary
  // itself stays in the DOM (off screen) so window.print() still has
  // content to render.
  const nonApprovalTargets = (TRANSITIONS[status] ?? []).filter(target => !Object.values(APPROVAL_TARGETS).includes(target));
  return <div className="logistics-page"><Link to="/logistics/resource-requests">Back to Resource Requests</Link>
    <div className="logistics-toolbar"><h2>{isNew ? "New resource request" : String(values.title)}</h2><StatusPill domain="logistics-request" statusKey={status} label={label(status)} />{dirty && <span>Unsaved header changes</span>}</div>
    {error && <p className="error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {!isNew && query.data && <div className="logistics-toolbar">
      <button onClick={() => window.print()}>Print / save summary as PDF</button>
      <button className="secondary">Download filled ICS-213RR</button>
      <span className="muted">Version {query.data.version} · Updated {formatDateTime(query.data.last_updated_utc)}</span>
    </div>}
    {!isNew && query.data && <div className="screen-hide"><RequestPrintSummary request={query.data} /></div>}
    <form onSubmit={e => { e.preventDefault(); void run(save); }}><fieldset className="logistics-form logistics-panel" disabled={terminal || busy}><legend>Request details</legend>
      <LogisticsFields values={values} update={update} facilities={facilities.data ?? []} fields={[
        { key: "title",label: "What is needed?",required: true,disabled: status !== "DRAFT" },
        { key: "priority",label: "Priority",kind: "select",options: PRIORITIES,disabled: status !== "DRAFT" },
        { key: "needed_by_utc",label: "Needed by",kind: "datetime" },
        { key: "delivery_location",label: "Delivery location" }, { key: "delivery_facility_id",label: "Delivery facility",kind: "facility" },
        { key: "justification",label: "Reason / additional details",kind: "textarea" },
      ]} />
      <details className="logistics-wide"><summary>More request details</summary><div className="logistics-form">
        <LogisticsFields values={values} update={update} fields={[{ key: "requesting_section",label: "Requesting section",disabled: status !== "DRAFT" },{ key: "comms_requirements",label: "Communications requirements" },{ key: "links",label: "Related references" }]} />
      </div></details><div className="logistics-wide"><button>{busy ? "Saving…" : isNew ? "Save request" : "Save header changes"}</button></div>
    </fieldset></form>
    {facilities.isError && <p className="error">Facility selection is unavailable. <button onClick={() => void facilities.refetch()}>Retry</button></p>}
    {!isNew && <RequestItems onDirtyChange={setItemsDirty} key={requestId} items={query.data?.items ?? []} disabled={busy || terminal} save={items => writes.items.mutateAsync(items)} />}
    {!isNew && <RequestFulfillments incidentId={incidentId} records={query.data?.fulfillments ?? []} facilities={facilities.data ?? []} disabled={busy || terminal} save={(fulfillmentId,body) => writes.fulfillment.mutateAsync({ fulfillmentId,body })} />}
    {/* Fulfillment-driven lifecycle moves (ASSIGNED → INTRANSIT → DELIVERED
       → CLOSED, etc.) aren't section approvals, so they stay a plain
       toolbar here rather than rows in the Required Approvals table. */}
    {!isNew && nonApprovalTargets.length > 0 && <div className="logistics-toolbar">
      {nonApprovalTargets.map(target => <button key={target} disabled={busy || dirty || itemsDirty} onClick={() => onStatusTransition(target)}>Mark {label(target)}</button>)}
    </div>}
    {!isNew && <RequestHistory
      approvals={query.data?.approvals ?? []}
      audit={query.data?.audit ?? []}
      availableActions={approvalActions(status)}
      terminal={terminal}
      busy={busy || dirty || itemsDirty}
      onApprovalAction={onApprovalAction}
    />}
    {dirty && <p>Save header edits before changing the request lifecycle.</p>}{terminal && <p>{status === "CLOSED" ? "Closed requests are read-only." : "Reopen the request to make changes."}</p>}
  </div>;
}
