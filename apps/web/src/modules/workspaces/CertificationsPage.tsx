import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { assignPersonCertification, listCertificationTypes, listPersonCertifications, listWorkspaceRecords, removePersonCertification } from "../../api/endpoints";
import DataTable from "../../components/table/DataTable";
import { WORKSPACES } from "./config";
import "./workspaces.css";

export default function CertificationsPage() {
  const [params, setParams] = useSearchParams();
  const person = params.get("person") ?? "";
  const [cert, setCert] = useState("");
  const [level, setLevel] = useState(0);
  const [removing, setRemoving] = useState<string | null>(null);
  const client = useQueryClient();
  const roster = useQuery({ queryKey: ["master", "personnel", "certification-picker"], queryFn: () => listWorkspaceRecords(WORKSPACES.find(w => w.path === "/personnel")!.datasets[0], ""), refetchInterval: 20_000 });
  const types = useQuery({ queryKey: ["master", "certification_types"], queryFn: listCertificationTypes, refetchInterval: 20_000 });
  const assignments = useQuery({ queryKey: ["master", "personnel", person, "certifications"], queryFn: () => listPersonCertifications(person), enabled: !!person, refetchInterval: 20_000 });
  const mutation = useMutation({ mutationFn: async ({ remove, certId }: { remove: boolean; certId: string }) => { if (remove) await removePersonCertification(person, certId); else await assignPersonCertification(person, certId, level); },
    onSuccess: async () => { setRemoving(null); await client.invalidateQueries({ queryKey: ["master", "personnel"] }); } });
  const error = roster.error ?? types.error ?? assignments.error ?? mutation.error;
  return <section className="workspace-page"><h1>Personnel certifications</h1><p>Assign certification levels from the shared catalog.</p>
    {error && <p className="error" role="alert">{error.message}</p>}
    <label className="field">Person<select value={person} onChange={e => { setParams(e.target.value ? { person: e.target.value } : {}); setRemoving(null); mutation.reset(); }}><option value="">Select a person</option>{roster.data?.filter(r => r.person_record != null).map(r => <option key={String(r.person_record)} value={String(r.person_record)}>{String(r.name)} ({String(r.person_id ?? r.person_record)})</option>)}</select></label>
    {person && <>
      {assignments.isPending && <p>Loading assignments…</p>}
      <DataTable tableId="person-certifications" rows={assignments.data ?? []} rowKey={r => String(r.cert_type_id)} columns={[
        { key: "name", header: "Certification", render: r => String(types.data?.find(t => t.id === r.cert_type_id)?.name ?? r.cert_type_id) },
        { key: "level", header: "Level" }, { key: "actions", header: "Actions", render: r => <button disabled={mutation.isPending} className="secondary" onClick={() => setRemoving(String(r.cert_type_id))}>Remove</button> },
      ]} />
      {removing && <div className="workspace-actions"><p>Remove the selected certification assignment?</p><button disabled={mutation.isPending} className="danger" onClick={() => mutation.mutate({ remove: true, certId: removing })}>Confirm removal</button><button className="secondary" onClick={() => setRemoving(null)}>Cancel</button></div>}
      <form className="workspace-form" onSubmit={e => { e.preventDefault(); mutation.mutate({ remove: false, certId: cert }); }}>
        <label className="field">Certification<select required value={cert} onChange={e => setCert(e.target.value)}><option value="">Select certification</option>{types.data?.map(t => <option key={String(t.id)} value={String(t.id)}>{String(t.code)} — {String(t.name)}</option>)}</select></label>
        <label className="field">Level<select value={level} onChange={e => setLevel(Number(e.target.value))}>{[0, 1, 2, 3].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        <button disabled={!cert || mutation.isPending || assignments.isPending}>Save assignment</button>
      </form>
    </>}
  </section>;
}
