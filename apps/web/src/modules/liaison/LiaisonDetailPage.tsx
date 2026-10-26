import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import type { LiaisonNarrative } from "../../api/types";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import { formatDateTime } from "../../utils/formatDateTime";
import { CONFIG, fieldDefaults } from "./config";
import { editPayload, NARRATIVE_CATEGORIES, reportState } from "./model";
import { useLiaisonRecords, useLiaisonWrites } from "./hooks";
import Fields from "./Fields";
import RequestLinks from "./RequestLinks";
import ReportingSource from "./ReportingSource";
import AgencyRelations from "./AgencyRelations";
import RequestConversion from "./RequestConversion";

const narrativeColumns: ColumnDef<LiaisonNarrative & { index: number }>[] = [
  { key: "ts", header: "When", render: r => formatDateTime(r.ts), defaultWidth: 190 },
  { key: "category", header: "Category" }, { key: "author", header: "Author" }, { key: "text", header: "Narrative", defaultWidth: 420 },
];
export default function LiaisonDetailPage() {
  const { section, recordId } = useParams(); const { incidentId } = useSession();
  return CONFIG[section!] ? <Editor key={`${incidentId}:${section}:${recordId}`} section={section!} recordId={recordId!} /> : <p>Unknown workspace. <Link to="/liaison">Overview</Link></p>;
}
function Editor({ section, recordId }: { section: string; recordId: string }) {
  const config = CONFIG[section]; const isNew = recordId === "new"; const intId = Number(recordId);
  const { incidentId, user } = useSession(); const id = incidentId!; const author = user?.display_name || user?.username || "";
  const query = useLiaisonRecords(id, config.section); const agencies = useLiaisonRecords(id, "agencies"); const writes = useLiaisonWrites(id);
  const navigate = useNavigate(); const [params] = useSearchParams(); const existing = query.data?.find(r => r.int_id === intId);
  const [patch, setPatch] = useState<Record<string, unknown>>({}); const [failure, setFailure] = useState(""); const [notice, setNotice] = useState("");
  const [entry, setEntry] = useState(""); const [category, setCategory] = useState("Update");
  const dirty = Object.keys(patch).length > 0;
  useEffect(() => { if (!dirty) return; const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  const defaults = fieldDefaults(config);
  if (isNew && params.get("agency")) defaults.agency_id = Number(params.get("agency"));
  const values = { ...defaults, ...(isNew ? {} : existing), ...patch };
  const update = (key: string, value: unknown) => { setPatch(old => ({ ...old, [key]: value })); setNotice(""); };
  const busy = writes.save.isPending || writes.remove.isPending || writes.narrative.isPending;
  const run = async (action: () => Promise<unknown>) => { setFailure(""); setNotice(""); try { await action(); } catch (error) { setFailure(error instanceof Error ? error.message : "The request failed. Your edits remain available."); } };
  const save = async () => {
    if (section === "reporting" && values.ready_to_report && !String(values.lofr_summary ?? "").trim()) throw new Error("Write the external summary before marking this entry ready to report.");
    if (section === "requests" && isNew) {
      const agency = agencies.data?.find(a => a.int_id === values.agency_id);
      if (!agency?.code) throw new Error("Add an Agency Code in the Agency Directory before creating a request for this agency.");
    }
    const body = isNew ? Object.fromEntries(config.fields.filter(f => !f.editOnly).map(f => [f.key, values[f.key]])) : editPayload(config.section, patch, author);
    if (isNew) {
      body.created_by = author;
      if (typeof body.code === "string") body.code = body.code.trim().toUpperCase();
      if (section === "requests") for (const key of ["objective_ids", "task_ids", "resource_request_ids"]) body[key] = values[key] ?? [];
      if (section === "reporting") Object.assign(body, { source_type: values.source_type || null, source_id: values.source_id || null, submitted_by: author });
    }
    const saved = await writes.save.mutateAsync({ section: config.section, recordId: isNew ? undefined : intId, body });
    setPatch({}); setNotice("Saved."); if (isNew) navigate(`/liaison/${section}/${saved.int_id}`, { replace: true });
  };
  if (!isNew && (!Number.isInteger(intId) || intId < 1)) return <p className="error">Invalid record ID.</p>;
  if (!isNew && query.isPending) return <p role="status">Loading record…</p>;
  if (!isNew && (query.isError || !existing)) return <p className="error" role="alert">{query.isError ? "Could not load this record." : "Record not found."} <Link to={`/liaison/${section}`}>Back to {config.title.toLowerCase()}</Link>{query.isError && <button onClick={() => void query.refetch()}>Retry</button>}</p>;
  const readOnly = section === "interactions" && !isNew;
  return <><Link to={`/liaison/${section}`}>Back to {config.title.toLowerCase()}</Link><div className="liaison-toolbar"><h3>{isNew ? `New ${config.singular.toLowerCase()}` : String(values[config.labelKey] || (section === "reporting" ? "Standalone reporting entry" : config.singular))}</h3>{dirty && <span>Unsaved changes</span>}</div>
    {failure && <p className="error" role="alert">{failure}</p>}{notice && <p role="status">{notice}</p>}
    {!isNew && section === "requests" && <p>Code: <strong>{String(values.code)}</strong> · {String(values.request_type)} · <Link to={`/liaison/agencies/${values.agency_id}`}>{String(agencies.data?.find(a => a.int_id === values.agency_id)?.name ?? `Agency #${values.agency_id}`)}</Link></p>}
    {!isNew && section === "reporting" && <section className="liaison-panel"><h3>Internal source note</h3><p className="liaison-record-text">{String(values.raw_note ?? "")}</p><p>Submitted by {String(values.submitted_by || "Not recorded")} · {formatDateTime(String(values.created_at ?? ""))}</p>
      {values.source_type === "task" || values.source_type === "objective" ? <Link to={values.source_type === "task" ? `/ops/tasks/${values.source_id}` : `/command/objectives/${values.source_id}`}>{String(values.source_title || "Open source")}</Link> : <p>Standalone entry</p>}<p>Readiness: {reportState(values)}</p></section>}
    <form onSubmit={e => { e.preventDefault(); void run(save); }}><fieldset className="liaison-form liaison-panel" disabled={busy || readOnly}>
      <legend>{config.singular}</legend>
      <Fields fields={config.fields.filter(f => isNew ? !f.editOnly : !f.createOnly)} values={values} agencies={agencies.data ?? []} update={update} />
      {isNew && section === "reporting" && <ReportingSource incidentId={id} values={values} update={update} />}
      {!readOnly && <div className="liaison-wide liaison-toolbar"><button type="submit">{busy ? "Saving…" : "Save"}</button>
        {!isNew && (section === "requests" || section === "reporting") && <button type="button" className="danger" onClick={() => { if (window.confirm(`Delete this ${config.singular.toLowerCase()}?`)) void run(async () => { await writes.remove.mutateAsync({ section: section === "requests" ? "requests" : "reporting-digests", recordId: intId }); navigate(`/liaison/${section}`); }); }}>Delete</button>}
      </div>}
    </fieldset></form>
    {agencies.isError && <p className="error">Agency names and selection could not be loaded. <button onClick={() => void agencies.refetch()}>Retry</button></p>}
    {readOnly && <p>Recorded interactions are read-only with the current API. <Link to={`/liaison/interactions/new?agency=${values.agency_id}`}>Log another interaction</Link></p>}
    {section === "requests" && <RequestLinks incidentId={id} values={values} update={update} disabled={busy} />}
    {section === "requests" && !isNew && <section className="liaison-panel"><h3>Request narrative</h3>
      <DataTable tableId="liaison-request-narrative" columns={narrativeColumns} rows={((existing?.narrative ?? []) as LiaisonNarrative[]).map((r,index) => ({ ...r, index }))} rowKey={r => r.index} emptyMessage="No narrative entries yet." />
      <form onSubmit={e => { e.preventDefault(); void run(async () => { await writes.narrative.mutateAsync({ requestId: intId, text: entry.trim(), category, author }); setEntry(""); setNotice("Narrative entry added."); }); }}>
        <div className="field"><label htmlFor="liaison-category">Category</label><select id="liaison-category" value={category} onChange={e => setCategory(e.target.value)}>{NARRATIVE_CATEGORIES.map(c => <option key={c}>{c}</option>)}</select></div>
        <div className="field"><label htmlFor="liaison-entry">Update / feedback</label><textarea id="liaison-entry" value={entry} onChange={e => setEntry(e.target.value)} /></div><button disabled={busy || !entry.trim()}>Add narrative entry</button>
      </form></section>}
    {section === "requests" && !isNew && <RequestConversion incidentId={id} requestId={intId} values={values} author={author} disabled={busy || dirty} />}
    {section === "agencies" && !isNew && <AgencyRelations incidentId={id} agencyId={intId} />}
    {section === "reporting" && <p>Ready to report marks a curated summary as shareable. Delivery to external agencies is handled separately.</p>}
  </>;
}
