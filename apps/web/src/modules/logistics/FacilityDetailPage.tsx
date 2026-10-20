import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import { useFacility, useFacilityPersonnel, useFacilityWrites } from "./hooks";
import { FACILITY_TYPES, facilityPayload } from "./model";
import LogisticsFields from "./LogisticsFields";
import "./logistics.css";
const initial = { name: "",facility_type: "other",status: "active",address: "",latitude: null,longitude: null,geocoded_address: "",icao_code: "",manager_personnel_id: "",manager_name: "",contact_name: "",contact_phone: "",notes: "",function_tags: [],served_sections: [],is_primary: false,metadata: {} };
export default function FacilityDetailPage() {
  const { facilityId } = useParams(); const { incidentId } = useSession();
  return <Editor key={`${incidentId}:${facilityId}`} incidentId={incidentId!} facilityId={facilityId!} />;
}
function Editor({ incidentId,facilityId }: { incidentId: string; facilityId: string }) {
  const isNew = facilityId === "new"; const query = useFacility(incidentId,facilityId); const writes = useFacilityWrites(incidentId,facilityId); const navigate = useNavigate();
  const [patch,setPatch] = useState<Record<string,unknown>>({}); const [search,setSearch] = useState(""); const [error,setError] = useState(""); const [notice,setNotice] = useState("");
  const people = useFacilityPersonnel(incidentId,search); const values = { ...initial,...query.data,...patch }; const dirty = Object.keys(patch).length > 0; const busy = writes.save.isPending || writes.remove.isPending;
  useEffect(() => { if (!dirty) return; const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; }; window.addEventListener("beforeunload",warn); return () => window.removeEventListener("beforeunload",warn); },[dirty]);
  const update = (key: string,value: unknown) => { setPatch(old => ({ ...old,[key]:value })); setNotice(""); };
  if (!isNew && query.isPending) return <p>Loading facility…</p>;
  if (!isNew && (query.isError || !query.data)) return <p className="error" role="alert">Could not load this facility. <button onClick={() => void query.refetch()}>Retry</button> <Link to="/logistics/facilities">Facilities</Link></p>;
  return <div className="logistics-page"><Link to="/logistics/facilities">Back to Facilities</Link><div className="logistics-toolbar"><h2>{isNew ? "New facility" : String(values.name)}</h2>{dirty && <span>Unsaved changes</span>}</div>
    {error && <p className="error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <form onSubmit={async e => { e.preventDefault(); setError(""); try { const saved = await writes.save.mutateAsync(facilityPayload(values)); setPatch({}); setNotice("Facility saved."); if (isNew) navigate(`/logistics/facilities/${saved.id}`,{ replace: true }); } catch(e) { setError(e instanceof Error ? e.message : "Could not save facility."); } }}>
      <fieldset className="logistics-form logistics-panel" disabled={busy}><legend>Facility record</legend>
        <LogisticsFields values={values} update={update} fields={[
          { key: "name",label: "Name",required: true },{ key: "facility_type",label: "Type",kind: "select",options: FACILITY_TYPES },{ key: "status",label: "Status",kind: "select",options: ["active","planned","closed"] },
          { key: "is_primary",label: "Primary facility for this type",kind: "checkbox" },{ key: "address",label: "Address" },{ key: "geocoded_address",label: "Verified location address" },
          { key: "latitude",label: "Latitude",kind: "number",min: -90,max: 90 },{ key: "longitude",label: "Longitude",kind: "number",min: -180,max: 180 },{ key: "icao_code",label: "ICAO code" },
          { key: "contact_name",label: "Contact name" },{ key: "contact_phone",label: "Contact phone" },{ key: "function_tags",label: "Functions (comma-separated)",kind: "tags" },{ key: "served_sections",label: "Served sections (comma-separated)",kind: "tags" },{ key: "notes",label: "Notes",kind: "textarea" },
        ]} />
        <div className="field"><label htmlFor="facility-person-search">Find a facility manager</label><input id="facility-person-search" type="search" value={search} onChange={e => setSearch(e.target.value)} />
          {people.isError && <span className="error">Personnel search unavailable.</span>}
          {search && <select aria-label="Manager search results" value="" onChange={e => { const person = people.data?.find(p => String(p.person_record) === e.target.value); if (person) { update("manager_personnel_id",String(person.person_record)); update("manager_name",person.name); setSearch(""); } }}><option value="">Select a person</option>{people.data?.map(p => <option key={p.person_record} value={p.person_record ?? ""}>{p.name} · {p.person_id}</option>)}</select>}
        </div><div className="field"><label>Current manager</label><span>{String(values.manager_name || "Not assigned")}</span><button type="button" className="secondary" onClick={() => { update("manager_personnel_id",""); update("manager_name",""); }}>Clear manager</button></div>
        <div className="logistics-wide logistics-toolbar"><button>{busy ? "Saving…" : "Save facility"}</button>{!isNew && <button type="button" className="danger" onClick={() => { if (window.confirm("Delete this facility?")) { setError(""); writes.remove.mutate(undefined,{ onSuccess: () => navigate("/logistics/facilities"),onError: e => setError(e.message) }); } }}>Delete facility</button>}</div>
      </fieldset>
    </form><p>Setting a primary facility replaces the previous primary of the same type on the server.</p>
  </div>;
}
