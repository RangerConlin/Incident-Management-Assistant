import { useObjectiveRows } from "../command/objectives/hooks";
import { useTaskRows } from "../operations/taskStatus/hooks";
export default function ReportingSource({ incidentId, values, update }: { incidentId: string; values: Record<string, unknown>; update: (key: string, value: unknown) => void }) {
  const objectives = useObjectiveRows(incidentId); const tasks = useTaskRows(incidentId);
  const kind = String(values.source_type ?? ""); const query = kind === "objective" ? objectives : tasks;
  const options = kind === "objective" ? (objectives.data ?? []).map(o => ({ id: o._id, label: `${o.code} — ${o.text}` })) : (tasks.data ?? []).map(t => ({ id: String(t.id), label: `${t.number} — ${t.name}` }));
  return <><div className="field"><label htmlFor="liaison-source-type">Source type</label><select id="liaison-source-type" value={kind} onChange={e => { update("source_type", e.target.value || null); update("source_id", null); }}><option value="">Standalone note</option><option value="objective">Objective</option><option value="task">Task</option></select></div>
    {kind && <div className="field"><label htmlFor="liaison-source">Source</label><select id="liaison-source" required value={String(values.source_id ?? "")} onChange={e => update("source_id", e.target.value)}><option value="">Select a source</option>{options.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</select>{query.isError && <span className="error">Could not load sources.</span>}</div>}
  </>;
}
