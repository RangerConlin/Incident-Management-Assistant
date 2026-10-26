import { useState } from "react";
import { Link } from "react-router-dom";
import { useCreateObjective } from "../command/objectives/hooks";
import { useCreateTask } from "../operations/taskStatus/hooks";
import { useLiaisonWrites } from "./hooks";
import { addWorkLink } from "./model";
export default function RequestConversion({ incidentId, requestId, values, disabled, author }: {
  incidentId: string; requestId: number; values: Record<string, unknown>; disabled: boolean; author: string;
}) {
  const objective = useCreateObjective(incidentId); const task = useCreateTask(incidentId); const writes = useLiaisonWrites(incidentId);
  const [title, setTitle] = useState(String(values.summary ?? ""));
  const [created, setCreated] = useState<{ kind: "objective_ids" | "task_ids"; id: string; path: string } | null>(null);
  const [attached, setAttached] = useState(false); const [error, setError] = useState("");
  const busy = disabled || objective.isPending || task.isPending || writes.save.isPending;
  const attach = async (item: NonNullable<typeof created>) => {
    await writes.save.mutateAsync({ section: "requests", recordId: requestId, body: { [item.kind]: addWorkLink((values[item.kind] ?? []) as (string | number)[], item.id, item.kind === "task_ids") } });
    setAttached(true);
  };
  const create = async (kind: "objective_ids" | "task_ids") => {
    setError("");
    try {
      const body = { text: title.trim(), title: title.trim(), priority: ({ Low: "low", Medium: "normal", High: "high", Critical: "urgent" } as Record<string,string>)[String(values.priority)] ?? "normal", created_by: author, origin_module: "liaison", origin_id: String(requestId) };
      let item: NonNullable<typeof created>;
      if (kind === "objective_ids") { const result = await objective.mutateAsync(body); item = { kind, id: result._id, path: `/command/objectives/${result._id}` }; }
      else { const result = await task.mutateAsync({ ...body, priority: String(values.priority || "Medium") }); item = { kind, id: String(result.int_id), path: `/ops/tasks/${result.int_id}` }; }
      setCreated(item);
      await attach(item);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create or link work."); }
  };
  return <section className="liaison-panel"><h3>Create work from this request</h3>
    {error && <p className="error" role="alert">{error}</p>}
    {created ? <><p><Link to={created.path}>Open created {created.kind === "task_ids" ? "task" : "objective"}</Link> · {attached ? "Linked to this request." : "Created; the request link still needs to be saved."}</p>
      {!attached && <button disabled={busy} onClick={() => { setError(""); void attach(created).catch(e => setError(e instanceof Error ? e.message : "Could not attach the created item.")); }}>Retry linking created item</button>}</> : <>
      <div className="field"><label htmlFor="liaison-work-title">Objective text / task title</label><input id="liaison-work-title" value={title} onChange={e => setTitle(e.target.value)} disabled={busy} /></div>
      <div className="liaison-toolbar"><button disabled={busy || !title.trim()} onClick={() => void create("objective_ids")}>Create linked objective</button><button disabled={busy || !title.trim()} onClick={() => void create("task_ids")}>Create linked task</button></div>
    </>}{disabled && <p>Save request edits before creating linked work.</p>}
  </section>;
}
