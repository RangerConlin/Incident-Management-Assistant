import type { LiaisonRecord } from "../../api/types";
import type { LiaisonField } from "./config";
import { localTimestamp, utcTimestamp } from "./model";
export default function Fields({ fields, values, agencies, update }: {
  fields: LiaisonField[]; values: Record<string, unknown>; agencies: LiaisonRecord[];
  update: (key: string, value: unknown) => void;
}) {
  return <>{fields.map(field => {
    const id = `liaison-${field.key}`; const text = String(values[field.key] ?? "");
    return <div className={`field ${field.kind === "textarea" ? "liaison-wide" : ""}`} key={field.key}>
      <label htmlFor={id}>{field.label}{field.required ? " *" : ""}</label>
      {field.kind === "textarea" ? <textarea id={id} required={field.required} value={text} onChange={e => update(field.key, e.target.value)} /> :
       field.kind === "checkbox" ? <input id={id} type="checkbox" checked={Boolean(values[field.key])} onChange={e => update(field.key, e.target.checked)} /> :
       field.kind === "datetime" ? <input id={id} type="datetime-local" step="1" value={localTimestamp(values[field.key])} onChange={e => update(field.key, utcTimestamp(e.target.value))} /> :
       field.kind === "agency" ? <select id={id} required={field.required} value={text} onChange={e => update(field.key, e.target.value ? Number(e.target.value) : "")}><option value="">Select an agency</option>{agencies.map(a => <option key={a.int_id} value={a.int_id}>{String(a.name)}{a.code ? ` (${a.code})` : ""}</option>)}</select> :
       field.kind === "select" ? <select id={id} value={text} onChange={e => update(field.key, e.target.value)}>{[...new Set([...(field.options ?? []), text])].filter(Boolean).map(option => <option key={option}>{option}</option>)}</select> :
       <input id={id} required={field.required} type={field.kind === "date" ? "date" : "text"} value={field.kind === "date" ? text.slice(0,10) : text} onChange={e => update(field.key, e.target.value)} />}
    </div>;
  })}</>;
}
