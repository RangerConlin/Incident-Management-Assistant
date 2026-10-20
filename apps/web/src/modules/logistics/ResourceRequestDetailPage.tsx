import FormExportControls from "../forms/FormExportControls";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { useFacilities, useResourceRequest, useRequestWrites } from "./hooks";
import { approvalActions, APPROVAL_TARGETS, label, PRIORITIES, requestPatch, TERMINAL, TRANSITIONS } from "./model";
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
  const navigate = useNavigate(); const [params,setParams] = useSearchParams(); const tab = params.get("tab") ?? "details";
  const [patch,setPatch] = useState<Record<string,unknown>>({}); const [note,setNote] = useState(""); const [error,setError] = useState(""); const [notice,setNotice] = useState("");
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
  if (!isNew && query.isPending) return <p role="status">Loading request…</p>;
  if (!isNew && (query.isError || !query.data)) return <p className="error" role="alert">Could not load this request. <button onClick={() => void query.refetch()}>Retry</button> <Link to="/logistics/resource-requests">Requests</Link></p>;
  const setTab = (value: string) => { if (itemsDirty && value !== "items") { setError("Save or discard item edits before switching sections."); return; } setParams(old => { const next = new URLSearchParams(old); next.set("tab",value); return next; },{ replace: true }); };
  return <div className="logistics-page"><Link to="/logistics/resource-requests">Back to Resource Requests</Link><div className="logistics-toolbar"><h2>{isNew ? "New resource request" : String(values.title)}</h2><StatusPill domain="logistics-request" statusKey={status} label={label(status)} />{dirty && <span>Unsaved header changes</span>}</div>
    {!isNew && <FormExportControls formIds={["ics_213rr"]} sourceId={requestId} disabled={dirty || itemsDirty} />}
    {error && <p className="error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {!isNew && <nav className="logistics-tabs" aria-label="Request sections">{["details","items","fulfillment","history","print"].map(t => <button key={t} className={tab === t ? "" : "secondary"} onClick={() => setTab(t)}>{label(t)}</button>)}</nav>}
    {(isNew || tab === "details") && <form onSubmit={e => { e.preventDefault(); void run(save); }}><fieldset className="logistics-form logistics-panel" disabled={terminal || busy}><legend>Request details</legend>
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
    </fieldset></form>}
    {facilities.isError && <p className="error">Facility selection is unavailable. <button onClick={() => void facilities.refetch()}>Retry</button></p>}
    {!isNew && tab === "items" && <RequestItems onDirtyChange={setItemsDirty} key={requestId} items={query.data?.items ?? []} disabled={busy || terminal} save={items => writes.items.mutateAsync(items)} />}
    {!isNew && tab === "fulfillment" && <RequestFulfillments incidentId={incidentId} records={query.data?.fulfillments ?? []} facilities={facilities.data ?? []} disabled={busy || terminal} save={(fulfillmentId,body) => writes.fulfillment.mutateAsync({ fulfillmentId,body })} />}
    {!isNew && tab === "history" && <RequestHistory approvals={query.data?.approvals ?? []} audit={query.data?.audit ?? []} />}
    {!isNew && tab === "print" && query.data && <><div className="logistics-toolbar"><button onClick={() => window.print()}>Print / save summary as PDF</button></div><RequestPrintSummary request={query.data} /></>}
    {!isNew && tab !== "print" && <section className="logistics-panel"><h3>Lifecycle</h3><p>Version {query.data?.version} · Updated {formatDateTime(query.data?.last_updated_utc)}</p>
      <div className="field"><label htmlFor="request-lifecycle-note">Action note (required for denial)</label><textarea id="request-lifecycle-note" value={note} disabled={busy} onChange={e => setNote(e.target.value)} /></div>
      <div className="logistics-toolbar">{approvalActions(status).map(action => <button key={action} disabled={busy || dirty || itemsDirty || action === "DENY" && !note.trim()} onClick={() => void run(async () => { await writes.approval.mutateAsync({ action,actor,note: note.trim() }); setNote(""); setNotice(`${label(action)} recorded.`); })}>{label(action)}</button>)}
        {(TRANSITIONS[status] ?? []).filter(target => !Object.values(APPROVAL_TARGETS).includes(target)).map(target => <button key={target} disabled={busy || dirty || itemsDirty} onClick={() => void run(async () => { await writes.status.mutateAsync({ status: target,actor,note: note.trim() }); setNote(""); setNotice(`Request marked ${label(target).toLowerCase()}.`); })}>Mark {label(target)}</button>)}
      </div>{dirty && <p>Save header edits before changing the request lifecycle.</p>}{terminal && <p>{status === "CLOSED" ? "Closed requests are read-only." : "Reopen the request to make changes."}</p>}
    </section>}
  </div>;
}
