import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { listIncidents } from "../../api/endpoints";
import type { PioMessage, PioApproval } from "../../api/types";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import StatusPill from "../../components/table/StatusPill";
import { formatDateTime } from "../../utils/formatDateTime";
import { usePioApprovals, usePioMessage, usePioRecords, usePioWrites } from "./hooks";
import { AUDIENCES, EDITABLE_STATUSES, LIFECYCLE, MESSAGE_TYPES, PRIORITIES, releasePayload } from "./model";

import ReleasePreview from "./ReleasePreview";

const historyColumns: ColumnDef<PioApproval>[] = [
  { key: "timestamp", header: "When", render: r => formatDateTime(r.timestamp), defaultWidth: 180 },
  { key: "action", header: "Action", defaultWidth: 190 }, { key: "reviewer_name", header: "Reviewer" }, { key: "comment", header: "Comment", defaultWidth: 280 },
];
const initial: Partial<PioMessage> = { title: "", subtitle: "", type: "Press Release", audience: "Public", priority: "Normal", status: "Draft", body: "", template_id: null };

export default function ReleaseDetailPage() {
  const { releaseId } = useParams(); const { incidentId, user } = useSession();
  return <ReleaseEditor key={`${incidentId}:${releaseId}`} id={incidentId!} releaseId={releaseId!} user={user?.display_name || user?.username || ""} />;
}
function ReleaseEditor({ id, releaseId, user }: { id: string; releaseId: string; user: string }) {
  const isNew = releaseId === "new"; const messageId = Number(releaseId); const navigate = useNavigate();
  const query = usePioMessage(id, messageId); const templates = usePioRecords(id, "pio_templates");
  const approvals = usePioApprovals(id, messageId); const writes = usePioWrites(id);
  const incidents = useQuery({ queryKey: ["incidents"], queryFn: listIncidents, refetchInterval: 20_000 });
  const [patch, setPatch] = useState<Partial<PioMessage>>({}); const [comment, setComment] = useState("");
  const [tab, setTab] = useState("edit"); const [notice, setNotice] = useState(""); const [failure, setFailure] = useState("");
  const dirty = Object.keys(patch).length > 0;
  useEffect(() => { if (!dirty) return; const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  const message = { ...initial, ...(query.data ?? {}), ...patch };
  const status = query.data?.status ?? "Draft";
  const editable = isNew || EDITABLE_STATUSES.includes(status);
  const busy = writes.save.isPending || writes.transition.isPending;
  const template = templates.data?.find(t => t.id === message.template_id);
  const incident = incidents.data?.find(i => i.id === id);
  const update = (key: string, value: unknown) => { setPatch(old => ({ ...old, [key]: value })); setNotice(""); };
  const save = async (target?: string, copy = false) => {
    setFailure(""); setNotice("");
    try {
      if (dirty && !editable) throw new Error("This release changed status while you were editing. Reload to review the current release before continuing.");
      let saved = query.data;
      if (isNew || dirty || copy) {
        saved = await writes.save.mutateAsync(releasePayload(message, user, copy));
        if (!copy) setPatch({});
      }
      if (!saved) return;
      if (target) await writes.transition.mutateAsync({ messageId: saved.id, status: target, user, comment });
      setComment(""); setNotice(target ? `Release status changed to ${target}.` : "Release saved.");
      if (isNew || copy) navigate(`/pio/releases/${saved.id}`, { replace: isNew });
    } catch (error) { setFailure(error instanceof Error ? error.message : "Could not save the release. Your edits are still available."); }
  };
  if (!isNew && (!Number.isInteger(messageId) || messageId < 1)) return <p className="error">Invalid release ID. <Link to="/pio/releases">Back to releases</Link></p>;
  if (!isNew && query.isPending) return <p role="status">Loading release…</p>;
  if (!isNew && (query.isError || !query.data)) return <p className="error" role="alert">Could not load this release. <button onClick={() => void query.refetch()}>Retry</button></p>;
  const select = (key: "type" | "audience" | "priority", label: string, options: string[]) => <div className="field"><label htmlFor={`pio-${key}`}>{label}</label><select id={`pio-${key}`} value={String(message[key] ?? "")} onChange={e => update(key, e.target.value)}>{[...new Set([...options, String(message[key] ?? "")])].filter(Boolean).map(s => <option key={s}>{s}</option>)}</select></div>;
  return <><Link to="/pio/releases">Back to messages / releases</Link><div className="pio-toolbar"><h3>{isNew ? "New release" : message.title || `Release #${messageId}`}</h3><StatusPill domain="pio" statusKey={status} /></div>
    <div className="pio-toolbar"><button className={tab === "edit" ? "" : "secondary"} onClick={() => setTab("edit")}>Compose</button><button className={tab === "preview" ? "" : "secondary"} onClick={() => setTab("preview")}>Preview</button>{tab === "preview" && <button className="secondary" onClick={() => window.print()}>Print preview</button>}{dirty && <span role="status">Unsaved changes</span>}</div>
    {failure && <p className="error" role="alert">{failure}</p>}{notice && <p role="status">{notice}</p>}
    <div className="pio-editor"><div className="pio-stack">
      {tab === "edit" ? <form onSubmit={e => { e.preventDefault(); void save(); }}>
        {!editable && <p>This release is {status.toLowerCase()}. Use the lifecycle actions to revise it or create an update.</p>}
        <fieldset disabled={!editable || busy} className="pio-form pio-panel">
          <legend>Release content</legend>
          {select("type", "Release type", MESSAGE_TYPES)}{select("audience", "Audience", AUDIENCES)}{select("priority", "Priority", PRIORITIES)}
          <div className="field"><label htmlFor="pio-template">Letterhead template</label><select id="pio-template" value={message.template_id ?? ""} onChange={e => update("template_id", e.target.value ? Number(e.target.value) : null)}><option value="">No template</option>{(templates.data ?? []).filter(t => t.is_active || t.id === message.template_id).map(t => <option key={t.id} value={t.id}>{String(t.template_name)}</option>)}</select>
            {templates.isError && <span className="error">Templates could not be loaded.</span>}</div>
          {([ ["title", "Headline"], ["subtitle", "Subtitle"], ["dateline", "Dateline"], ["related_operational_period_id", "Operational period reference"] ] as const).map(([key, label]) => <div className="field" key={key}><label htmlFor={`pio-${key}`}>{label}</label><input id={`pio-${key}`} value={message[key] ?? ""} onChange={e => update(key, e.target.value)} required={key === "title"} /></div>)}
          {([ ["body", "Release body"], ["next_update_statement", "Next update statement"], ["boilerplate", "Boilerplate"] ] as const).map(([key,label]) => <div className="field pio-wide" key={key}><label htmlFor={`pio-${key}`}>{label}</label><textarea id={`pio-${key}`} className={key === "body" ? "pio-body" : ""} value={message[key] ?? ""} onChange={e => update(key, e.target.value)} /></div>)}
          {editable && <div className="pio-wide"><button disabled={busy || !message.title?.trim()} type="submit">{busy ? "Saving…" : "Save draft"}</button></div>}
        </fieldset></form> : <section className="pio-panel pio-preview" aria-label="Release preview">
          {dirty && <p>Preview includes unsaved edits.</p>}<ReleasePreview message={message} template={template} incident={incident} />
        </section>}
      {!isNew && <section className="pio-panel"><h3>Lifecycle / approval history</h3>{approvals.isError ? <p className="error">Could not load approval history.</p> : approvals.isPending ? <p>Loading history…</p> : <DataTable tableId="pio-approvals" columns={historyColumns} rows={approvals.data ?? []} rowKey={r => r.id} emptyMessage="No lifecycle actions recorded." />}</section>}
    </div><aside className="pio-stack"><section className="pio-panel"><h3>Release lifecycle</h3>
      <p>Publication records release status here. Record completed delivery separately in the distribution log.</p>
      <div className="field"><label htmlFor="pio-comment">Reviewer / lifecycle comment</label><textarea id="pio-comment" value={comment} onChange={e => setComment(e.target.value)} disabled={busy} /></div>
      <div className="pio-toolbar">{(!isNew ? LIFECYCLE[status] ?? [] : []).map(action => <button key={action.target} disabled={busy || !message.title?.trim() || !message.body?.trim()} onClick={() => void save(action.target)}>{action.label}</button>)}
        {status === "Published" && <button disabled={busy} onClick={() => void save(undefined, true)}>Create update draft</button>}
      </div><p>{isNew ? "Save the draft before submitting it for approval." : "Headline and body are required to advance the lifecycle."}</p>
      {status === "Published" && <Link to={`/pio/distribution/new?message=${messageId}`}>Record distribution</Link>}
    </section><section className="pio-panel"><h3>Release checks</h3><ul>{[["Headline", message.title], ["Body", message.body], ["Dateline", message.dateline], ["Next update", message.next_update_statement], ["Boilerplate", message.boilerplate]].map(([label,value]) => <li key={label}>{label}: {value?.trim() ? "Ready" : "Missing"}</li>)}</ul></section>
      {!isNew && <section className="pio-panel"><h3>Release record</h3><dl className="pio-meta">{[["Prepared by", query.data?.created_by], ["Approved by", query.data?.approved_by], ["Approved", formatDateTime(query.data?.approved_at)], ["Published by", query.data?.published_by], ["Published", formatDateTime(query.data?.published_at)], ["Archived by", query.data?.archived_by], ["Archived", formatDateTime(query.data?.archived_at)]].map(([label,value]) => <div className="pio-wide" key={label}><dt>{label}</dt><dd>{value || "—"}</dd></div>)}</dl></section>}
    </aside></div></>;
}
