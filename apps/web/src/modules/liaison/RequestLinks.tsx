import { useState } from "react";
import { Link } from "react-router-dom";
import { useObjectiveRows } from "../command/objectives/hooks";
import { useTaskRows } from "../operations/taskStatus/hooks";
import { addWorkLink } from "./model";
import { useLiaisonResourceLinks } from "./hooks";

export default function RequestLinks({ incidentId, values, update, disabled }: {
  incidentId: string; values: Record<string, unknown>; update: (key: string, value: unknown) => void; disabled: boolean;
}) {
  const objectives = useObjectiveRows(incidentId); const tasks = useTaskRows(incidentId); const resources = useLiaisonResourceLinks(incidentId);
  const [kind, setKind] = useState("objective_ids"); const [selection, setSelection] = useState("");
  const lists = {
    objective_ids: (objectives.data ?? []).map(o => ({ id: o._id, label: `${o.code} — ${o.text}`, path: `/command/objectives/${o._id}` })),
    task_ids: (tasks.data ?? []).map(t => ({ id: String(t.id), label: `${t.number} — ${t.name}`, path: `/ops/tasks/${t.id}` })),
    resource_request_ids: (resources.data ?? []).map(r => ({ id: r.id, label: `${r.request_number || r.id} — ${r.title}`, path: "" })),
  };
  const typedKind = kind as keyof typeof lists; const queries = { objective_ids: objectives, task_ids: tasks, resource_request_ids: resources };
  const query = queries[typedKind]; const options = lists[typedKind];
  return <section className="liaison-panel"><h3>Linked work</h3>
    <div className="liaison-toolbar"><select aria-label="Link type" disabled={disabled} value={kind} onChange={e => { setKind(e.target.value); setSelection(""); }}><option value="objective_ids">Objective</option><option value="task_ids">Task</option><option value="resource_request_ids">Resource request</option></select>
      <select aria-label="Work item" disabled={disabled || query.isPending || query.isError} value={selection} onChange={e => setSelection(e.target.value)}><option value="">Select an existing item</option>{options.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</select>
      <button type="button" disabled={disabled || !selection} onClick={() => { const current = (values[kind] ?? []) as (string | number)[]; update(kind, addWorkLink(current, selection, kind === "task_ids")); setSelection(""); }}>Add link</button>
    </div>{query.isError && <p className="error">Could not load available items. <button type="button" onClick={() => void query.refetch()}>Retry</button></p>}
    {(Object.keys(lists) as (keyof typeof lists)[]).map(key => <ul className="liaison-link-list" key={key}>{((values[key] ?? []) as (string | number)[]).map(value => {
      const item = lists[key].find(o => o.id === String(value));
      const path = key === "objective_ids" ? `/command/objectives/${value}` : key === "task_ids" ? `/ops/tasks/${value}` : "";
      return <li key={value}>{path ? <Link to={path}>{item?.label || `${key === "task_ids" ? "Task" : "Objective"} #${value}`}</Link> : <span>{item?.label || `Resource request #${value}`}</span>} <button type="button" className="secondary" disabled={disabled} aria-label={`Remove link ${value}`} onClick={() => update(key, ((values[key] ?? []) as (string | number)[]).filter(v => String(v) !== String(value)))}>Remove</button></li>;
    })}</ul>)}<p>Save the request to apply link changes.</p>
  </section>;
}
