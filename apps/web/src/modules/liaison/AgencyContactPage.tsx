import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import { useAgencyDetail, useLiaisonWrites } from "./hooks";
import Fields from "./Fields";
export default function AgencyContactPage() {
  const { agencyId: rawId } = useParams(); const agencyId = Number(rawId); const { incidentId } = useSession();
  const agency = useAgencyDetail(incidentId!, agencyId); const writes = useLiaisonWrites(incidentId!); const navigate = useNavigate();
  const [values, setValues] = useState<Record<string, unknown>>({}); const [failure, setFailure] = useState("");
  if (!Number.isInteger(agencyId) || agencyId < 1) return <p className="error">Invalid agency ID.</p>;
  if (agency.isPending) return <p>Loading agency…</p>;
  if (agency.isError || !agency.data) return <p className="error">Could not load this agency. <button onClick={() => void agency.refetch()}>Retry</button></p>;
  return <><Link to={`/liaison/agencies/${agencyId}?tab=contacts`}>Back to agency</Link><h3>Add contact · {String(agency.data.agency.name)}</h3>
    {failure && <p className="error" role="alert">{failure}</p>}
    <form onSubmit={e => { e.preventDefault(); setFailure(""); writes.contact.mutate({ agencyId, body: values }, { onSuccess: () => navigate(`/liaison/agencies/${agencyId}?tab=contacts`), onError: error => setFailure(error.message) }); }}>
      <fieldset disabled={writes.contact.isPending} className="liaison-form liaison-panel"><legend>Agency contact</legend>
        <Fields fields={[{ key: "name", label: "Name", required: true }, { key: "role", label: "Role / title" }, { key: "phone", label: "Phone" }, { key: "email", label: "Email" }, { key: "notes", label: "Notes", kind: "textarea" }]} values={values} agencies={[]} update={(key,value) => setValues(old => ({ ...old, [key]: value }))} />
        <div className="liaison-wide"><button>{writes.contact.isPending ? "Saving…" : "Add contact"}</button></div>
      </fieldset>
    </form></>;
}
