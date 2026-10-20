import type { Facility } from "../../api/types";
import { label, localTimestamp, utcTimestamp } from "./model";
export interface LogisticsField { key: string; label: string; kind?: "text" | "textarea" | "number" | "datetime" | "select" | "facility" | "checkbox" | "tags"; options?: string[]; required?: boolean; disabled?: boolean; min?: number; max?: number; }
export default function LogisticsFields({ fields, values, update, facilities = [] }: { fields: LogisticsField[]; values: Record<string, unknown>; update: (key: string, value: unknown) => void; facilities?: Facility[] }) {
  return <>{fields.map(field => {
    const id = `logistics-${field.key}`; const value = values[field.key]; const text = Array.isArray(value) ? value.join(", ") : String(value ?? "");
    return <div className={`field ${field.kind === "textarea" ? "logistics-wide" : ""}`} key={field.key}><label htmlFor={id}>{field.label}{field.required ? " *" : ""}</label>
      {field.kind === "textarea" ? <textarea id={id} value={text} disabled={field.disabled} required={field.required} onChange={e => update(field.key, e.target.value)} /> :
       field.kind === "checkbox" ? <input id={id} type="checkbox" checked={Boolean(value)} disabled={field.disabled} onChange={e => update(field.key, e.target.checked)} /> :
       field.kind === "datetime" ? <input id={id} type="datetime-local" step="1" value={localTimestamp(value)} disabled={field.disabled} onChange={e => update(field.key, utcTimestamp(e.target.value))} /> :
       field.kind === "facility" ? <select id={id} value={text} disabled={field.disabled} onChange={e => { update(field.key, e.target.value || null); }}><option value="">No facility selected</option>{facilities.map(f => <option key={f.id} value={f.id}>{f.name} · {label(f.facility_type)}</option>)}</select> :
       field.kind === "select" ? <select id={id} value={text} disabled={field.disabled} onChange={e => update(field.key, e.target.value)}>{[...new Set([...(field.options ?? []), text])].filter(Boolean).map(option => <option key={option} value={option}>{label(option)}</option>)}</select> :
       <input id={id} type={field.kind === "number" ? "number" : "text"} step={field.kind === "number" ? "any" : undefined} min={field.min} max={field.max} required={field.required} disabled={field.disabled} value={text} onChange={e => update(field.key, field.kind === "number" ? e.target.value === "" ? null : Number(e.target.value) : e.target.value)} />}
    </div>;
  })}</>;
}
