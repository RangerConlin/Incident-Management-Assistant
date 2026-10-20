import { useState } from "react";
import type { Facility, RequestFulfillment } from "../../api/types";
import { useTeamRows } from "../operations/teamStatus/hooks";
import { useResourceStatusRows } from "./resourceStatus/hooks";
import { formatDateTime } from "../../utils/formatDateTime";
import { FULFILLMENT_STATUSES, label } from "./model";
import LogisticsFields from "./LogisticsFields";
export default function RequestFulfillments({ incidentId, records, facilities, disabled, save }: {
  incidentId: string; records: RequestFulfillment[]; facilities: Facility[]; disabled: boolean;
  save: (id: string | undefined, body: Record<string, unknown>) => Promise<unknown>;
}) {
  const [adding,setAdding] = useState(false);
  return <><section className="logistics-panel"><div className="logistics-toolbar"><h3>Fulfillment</h3><button disabled={disabled || adding} onClick={() => setAdding(true)}>Add fulfillment</button></div><p>Track sourcing, assignments and delivery here. Update the overall request status separately in its lifecycle controls.</p>
    {!records.length && !adding && <p>No fulfillment recorded.</p>}
    {adding && <FulfillmentEditor incidentId={incidentId} facilities={facilities} disabled={disabled} save={body => save(undefined,body)} onDone={() => setAdding(false)} />}
  </section>{records.map(record => <section className="logistics-panel" key={record.id}><h3>{label(record.status)} · {formatDateTime(record.ts_utc)}</h3><p>Supplier: {String(record.supplier_id || "Not recorded")} · Team: {String(record.assigned_team_id || "Not assigned")} · Vehicle: {String(record.assigned_vehicle_id || "Not assigned")}</p>
    <FulfillmentEditor incidentId={incidentId} record={record} facilities={facilities} disabled={disabled} save={body => save(record.id,body)} />
  </section>)}</>;
}
function FulfillmentEditor({ incidentId, record, facilities, disabled, save, onDone }: { incidentId: string; record?: RequestFulfillment; facilities: Facility[]; disabled: boolean; save: (body: Record<string,unknown>) => Promise<unknown>; onDone?: () => void }) {
  const [patch,setPatch] = useState<Record<string,unknown>>({}); const [error,setError] = useState(""); const [notice,setNotice] = useState("");
  const teams = useTeamRows(incidentId); const vehicles = useResourceStatusRows(incidentId,"vehicle");
  const values = { status: "SOURCING", destination_location: "", destination_facility_id: null, eta_utc: "", note: "", ...(record ?? {}), ...patch };
  const update = (key: string,value: unknown) => { setPatch(old => {
    const next = { ...old,[key]:value };
    if (key === "destination_facility_id" && value) {
      const facility = facilities.find(f => f.id === value);
      if (facility) next.destination_location = facility.name;
    }
    return next;
  }); setNotice(""); };
  return <form onSubmit={async e => { e.preventDefault(); setError(""); try { await save(record ? patch : values); setPatch({}); setNotice("Fulfillment saved."); onDone?.(); } catch(e) { setError(e instanceof Error ? e.message : "Could not save fulfillment."); } }}>
    {error && <p className="error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <fieldset className="logistics-form" disabled={disabled}><legend>{record ? "Update fulfillment" : "New fulfillment"}</legend>
      {!record && <><div className="field"><label htmlFor="fulfillment-supplier">Supplier reference</label><input id="fulfillment-supplier" value={String(patch.supplier_id ?? "")} onChange={e => update("supplier_id", e.target.value || null)} /></div>
        <div className="field"><label htmlFor="fulfillment-team">Assigned team</label><select id="fulfillment-team" value={String(patch.team_id ?? "")} onChange={e => update("team_id",e.target.value ? Number(e.target.value) : null)}><option value="">No team</option>{teams.data?.map(t => <option key={t.team_id} value={t.team_id}>{t.name}</option>)}</select>{teams.isError && <span className="error">Teams unavailable.</span>}</div>
        <div className="field"><label htmlFor="fulfillment-vehicle">Assigned vehicle</label><select id="fulfillment-vehicle" value={String(patch.vehicle_id ?? "")} onChange={e => update("vehicle_id",e.target.value || null)}><option value="">No vehicle</option>{vehicles.data?.map(v => <option key={v.record_id} value={v.record_id}>{v.resource_name}</option>)}</select>{vehicles.isError && <span className="error">Vehicles unavailable.</span>}</div></>}
      <LogisticsFields values={values} facilities={facilities} update={update} fields={[
        ...(record ? [{ key: "status", label: "Fulfillment status", kind: "select" as const, options: FULFILLMENT_STATUSES }] : []),
        { key: "destination_location",label: "Destination location" }, { key: "destination_facility_id",label: "Destination facility",kind: "facility" },
        { key: "eta_utc",label: "ETA",kind: "datetime" }, { key: "note",label: "Note",kind: "textarea" },
      ]} /><div className="logistics-wide logistics-toolbar"><button>{record ? "Save fulfillment update" : "Assign / start sourcing"}</button>{onDone && <button type="button" className="secondary" onClick={onDone}>Cancel</button>}</div>
    </fieldset>
  </form>;
}
