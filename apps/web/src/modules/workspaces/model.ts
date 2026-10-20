import type { Dataset, Field, RecordData } from "./config";

export function datasetUrl(dataset: Dataset, incidentId: string): string {
  return dataset.master ? dataset.endpoint : `/api/incidents/${encodeURIComponent(incidentId)}/${dataset.endpoint}`;
}
export function recordUrl(dataset: Dataset, incidentId: string, id: string): string {
  const [base, query] = datasetUrl(dataset, incidentId).split("?");
  // List limits/search arguments do not belong on record operations.
  const params = new URLSearchParams(query);
  const scope = new URLSearchParams();
  for (const key of ["op", "version"]) if (params.has(key)) scope.set(key, params.get(key)!);
  return `${base}/${encodeURIComponent(id)}${scope.size ? `?${scope}` : ""}`;
}
export function recordId(dataset: Dataset, row: RecordData): string {
  return String(row[dataset.idKey ?? "id"] ?? "");
}
export function defaultValues(fields: Field[]): RecordData {
  return Object.fromEntries(fields.map(field => [field.key, field.initial ?? field.options?.[0] ?? (field.kind === "checkbox" ? false : field.kind === "list" ? [] : "")]));
}
export function fieldValue(values: RecordData, key: string): unknown {
  if (Object.prototype.hasOwnProperty.call(values, key)) return values[key];
  return key.split(".").reduce<unknown>((value, part) => value && typeof value === "object" ? (value as RecordData)[part] : undefined, values);
}
export function payloadFor(dataset: Dataset, values: RecordData, creating: boolean, incidentId: string): RecordData {
  const payload: RecordData = {};
  for (const field of dataset.fields) {
    if (creating ? field.editOnly : field.createOnly) continue;
    let value = fieldValue(values, field.key);
    if (value === undefined) continue;
    if (field.kind === "number") value = value === "" || value === null ? null : Number(value);
    if (field.kind === "datetime-local") {
      value = value ? new Date(String(value)).toISOString().replace(/\.\d{3}Z$/, "Z") : null;
    }
    if (typeof value === "string") value = value.trim();
    if (field.required && (value === "" || value === null)) throw new Error(`${field.label} is required.`);
    if (typeof value === "number" && (!Number.isFinite(value) || (field.min !== undefined && value < field.min) || (field.max !== undefined && value > field.max))) throw new Error(`${field.label} is outside the allowed range.`);
    if (field.kind === "list" && Array.isArray(value)) value = value.map(v => String(v).trim()).filter(Boolean);
    if (creating && (value === "" || value === null) && !field.required) continue;
    const parts = (field.writeKey ?? field.key).split(".");
    let target = payload;
    for (const part of parts.slice(0, -1)) {
      target[part] ??= {};
      target = target[part] as RecordData;
    }
    target[parts[parts.length - 1]] = value;
  }
  if (creating && dataset.endpoint.startsWith("initialresponse/")) payload.incident_id = incidentId;
  if (creating && dataset.endpoint.startsWith("safety/orm/hazards")) payload.op_period = Number(new URLSearchParams(dataset.endpoint.split("?")[1]).get("op") ?? 1);
  return payload;
}
export function filterRows(rows: RecordData[], fields: string[], params: URLSearchParams): RecordData[] {
  const q = (params.get("q") ?? "").trim().toLowerCase();
  const state = params.get("status") ?? "";
  const sort = params.get("sort") ?? fields[0];
  const direction = params.get("direction") === "desc" ? -1 : 1;
  return rows.filter(row => (!state || row.status === state) && (!q || fields.some(key => String(fieldValue(row, key) ?? "").toLowerCase().includes(q))))
    .sort((a, b) => {
      const av = fieldValue(a, sort), bv = fieldValue(b, sort);
      return direction * (typeof av === "number" && typeof bv === "number" ? av - bv : String(av ?? "").localeCompare(String(bv ?? "")));
    });
}
export function localDatetime(value: unknown): string {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 19);
}
