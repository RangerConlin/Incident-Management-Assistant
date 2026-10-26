import { useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import { useExportSources, useFormExportCatalog } from "./hooks";
import FormExportControls from "./FormExportControls";
export default function FormExportsPage() {
  const { incidentId } = useSession(); const catalog = useFormExportCatalog(incidentId!);
  const [formId,setFormId] = useState("ics_202"); const [sourceId,setSourceId] = useState("");
  const form = catalog.data?.find(f => f.form_id === formId); const source = form?.source ?? ""; const sources = useExportSources(incidentId!,source);
  const needsSource = ["work_assignment","resource_request","sitrep"].includes(source);
  return <div className="form-export-page"><h2>ICS Form Exports</h2><p>Download incident forms populated from saved operational records. The form's publishing organization is shown beside its title.</p>
    {catalog.isError ? <p className="error">Could not load export forms. <button onClick={() => void catalog.refetch()}>Retry</button></p> : catalog.isPending ? <p>Loading forms…</p> : <>
      <div className="field"><label htmlFor="export-form">Form</label><select id="export-form" value={formId} onChange={e => { setFormId(e.target.value); setSourceId(""); }}>{catalog.data?.map(f => <option key={f.form_id} value={f.form_id}>{f.label}</option>)}</select></div>
      {needsSource && <div className="field"><label htmlFor="export-source">Saved source record</label><select id="export-source" value={sourceId} onChange={e => setSourceId(e.target.value)}><option value="">Select a record</option>{sources.data?.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select>{sources.isPending && <p role="status">Loading saved records…</p>}{sources.isError && <p className="error">Sources could not be loaded. <button onClick={() => void sources.refetch()}>Retry</button></p>}</div>}
      <FormExportControls key={`${formId}:${sourceId}`} formIds={[formId]} sourceId={sourceId || undefined} />
    </>}
    <p><Link to="/command/objectives">Objectives</Link> · <Link to="/planning/work-assignments">Work assignments</Link> · <Link to="/planning/sitreps">SITREPs</Link> · <Link to="/logistics/resource-requests">Resource requests</Link></p>
  </div>;
}
