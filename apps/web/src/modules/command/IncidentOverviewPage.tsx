import { useEffect, useState } from "react";
import { useSession } from "../../auth/SessionContext";
import { useFacilities } from "../logistics/hooks";
import { useIncidentProfile, useProfileSave } from "./hooks";
import "./command.css";

const local = (v: string | null) => v ? v.slice(0,16) : "";
export default function IncidentOverviewPage() {
  const { incidentId }=useSession(); const id=incidentId!; const query=useIncidentProfile(id); const facilities=useFacilities(id); const save=useProfileSave(id);
  const [draft,setDraft]=useState<Record<string,unknown>>({}); const [message,setMessage]=useState("");
  useEffect(() => { if(query.data) setDraft({...query.data,start_time:local(query.data.start_time),end_time:local(query.data.end_time)}); },[query.data]);
  const set=(key:string,value:unknown)=>setDraft(old=>({...old,[key]:value}));
  if(query.isPending) return <p>Loading incident profile…</p>; if(query.isError) return <p className="error">Could not load the incident profile.</p>;
  return <div className="command-page"><div className="command-heading"><div><h2>Incident Overview</h2><p>Maintain the incident identity, command post, location, and lifecycle status.</p></div></div>
    {message && <p role="status">{message}</p>}<form className="command-panel command-form" onSubmit={async e=>{e.preventDefault();setMessage(""); try { await save.mutateAsync({...draft,start_time:draft.start_time||null,end_time:draft.end_time||null,icp_facility_id:draft.icp_facility_id||null}); setMessage("Incident profile saved."); } catch(err){setMessage(err instanceof Error?err.message:"Could not save incident profile.");}}}>
      <label>Incident name<input required value={String(draft.name??"")} onChange={e=>set("name",e.target.value)}/></label><label>Incident number<input required value={String(draft.number??"")} onChange={e=>set("number",e.target.value)}/></label>
      <label>Type<input value={String(draft.type??"")} onChange={e=>set("type",e.target.value)}/></label><label>Status<select value={String(draft.status??"active")} onChange={e=>set("status",e.target.value)}>{["planned","active","contained","closed","cancelled"].map(v=><option key={v}>{v}</option>)}</select></label>
      <label>Start time<input type="datetime-local" value={String(draft.start_time??"")} onChange={e=>set("start_time",e.target.value)}/></label><label>End time<input type="datetime-local" value={String(draft.end_time??"")} onChange={e=>set("end_time",e.target.value)}/></label>
      <label>ICP facility<select value={String(draft.icp_facility_id??"")} onChange={e=>{set("icp_facility_id",e.target.value); const f=facilities.data?.find(x=>x.id===e.target.value); if(f)set("icp_location",f.name);}}><option value="">No linked facility</option>{facilities.data?.map(f=><option value={f.id} key={f.id}>{f.name}</option>)}</select></label><label>ICP location<input value={String(draft.icp_location??"")} onChange={e=>set("icp_location",e.target.value)}/></label>
      <label>Latitude<input type="number" step="any" value={draft.latitude==null?"":String(draft.latitude)} onChange={e=>set("latitude",e.target.value?Number(e.target.value):null)}/></label><label>Longitude<input type="number" step="any" value={draft.longitude==null?"":String(draft.longitude)} onChange={e=>set("longitude",e.target.value?Number(e.target.value):null)}/></label>
      <label className="command-wide">Description<textarea rows={5} value={String(draft.description??"")} onChange={e=>set("description",e.target.value)}/></label><label className="command-check"><input type="checkbox" checked={Boolean(draft.is_training)} onChange={e=>set("is_training",e.target.checked)}/> Training incident</label>
      <div className="command-wide"><button disabled={save.isPending}>{save.isPending?"Saving…":"Save incident profile"}</button></div>
    </form></div>;
}
