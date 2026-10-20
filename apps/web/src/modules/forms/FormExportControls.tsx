import { useState } from "react";
import { useIsMutating } from "@tanstack/react-query";
import { useSession } from "../../auth/SessionContext";
import { useOperationalPeriods } from "../planning/operationalPeriods/hooks";
import { useDownloadForm, useFormExportCatalog } from "./hooks";
import "./forms.css";
export default function FormExportControls({ formIds, sourceId, operationalPeriodId, disabled = false }: {
  formIds: string[]; sourceId?: string; operationalPeriodId?: string | number | null; disabled?: boolean;
}) {
  const { incidentId,user } = useSession(); const catalog = useFormExportCatalog(incidentId!); const periods = useOperationalPeriods(incidentId!);
  const download = useDownloadForm(incidentId!); const mutations = useIsMutating();
  const [formId,setFormId] = useState(formIds[0] ?? ""); const [period,setPeriod] = useState(String(operationalPeriodId ?? "")); const [notice,setNotice] = useState("");
  const choices = (catalog.data ?? []).filter(f => formIds.includes(f.form_id)); const selected = choices.find(f => f.form_id === formId);
  const needsSource = selected && ["work_assignment","sitrep","resource_request"].includes(selected.source);
  const busy = download.isPending || mutations > 0;
  return <section className="form-export-controls" aria-label="Form exports"><h3>Download forms</h3>
    <p>Exports use saved records. Extra rows and continued text are included; signatures remain blank.</p>
    {selected?.source === "objectives" && !sourceId && <p>Includes active objectives for the selected period, or incident-wide when no period is selected.</p>}
    {selected?.source === "meetings" && !sourceId && <p>Includes meetings marked for the ICS 230 schedule.</p>}
    {selected?.source === "checkin" && <p>Includes checked-in resources across the incident. Board search filters do not change this export.</p>}
    <div className="form-export-row"><label>Form<select value={formId} onChange={e => { setFormId(e.target.value); setNotice(""); download.reset(); }} disabled={busy || disabled}>{choices.map(f => <option key={f.form_id} value={f.form_id}>{f.label}</option>)}</select></label>
      <label>Operational period<select value={period} onChange={e => setPeriod(e.target.value)} disabled={busy || disabled || Boolean(operationalPeriodId)}><option value="">{sourceId ? "Use the source record's period" : "All incident records / no period"}</option>{periods.data?.map(p => <option key={p.id} value={p.id}>OP {p.number} - {p.name}</option>)}</select></label>
      <button type="button" disabled={busy || disabled || !selected || Boolean(needsSource && !sourceId)} onClick={() => { setNotice(""); download.mutate({ form_id: formId,...(sourceId ? { source_id: sourceId } : {}),...(period ? { operational_period_id: Number(period) } : {}),prepared_by: user?.display_name || user?.username || "" },{ onSuccess: result => {
        const url = URL.createObjectURL(result.blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = result.filename; document.body.appendChild(anchor); anchor.click(); anchor.remove(); window.setTimeout(() => URL.revokeObjectURL(url),1000); setNotice("PDF downloaded.");
      } }); }}>{download.isPending ? "Generating PDF…" : "Download PDF"}</button>
    </div>{catalog.isError && <p className="error" role="alert">Export catalog unavailable. <button onClick={() => void catalog.refetch()}>Retry</button></p>}
    {catalog.isPending && <p role="status">Loading available forms…</p>}{periods.isError && <p className="error">Operational-period choices unavailable. <button onClick={() => void periods.refetch()}>Retry</button></p>}
    {needsSource && !sourceId && <p>Select a saved source record to export this form.</p>}
    {download.error && <p className="error" role="alert">{download.error.message}</p>}{notice && <p role="status">{notice}</p>}{disabled && <p>Save or discard edits before exporting.</p>}
  </section>;
}
