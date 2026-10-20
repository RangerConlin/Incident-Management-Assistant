import type { LiaisonRecord } from "../../api/types";

export const AGENCY_STATUSES = ["Not Contacted", "Contacted", "Awaiting Response", "Standby", "Supporting", "Active", "Demobilizing", "Released", "Unavailable"];
export const REQUEST_STATUSES = ["Open", "In Progress", "Resolved", "Declined", "Cancelled"];
export const PRIORITIES = ["Low", "Medium", "High", "Critical"];
export const NARRATIVE_CATEGORIES = ["General", "Update", "Follow-up", "Feedback", "Auto", "Resolution"];
export function reportState(record: Record<string, unknown>): string {
  return record.ready_to_report ? "Ready" : String(record.lofr_summary ?? "").trim() ? "In Progress" : "New";
}
export function isOverdue(record: Record<string, unknown>, today: string): boolean {
  if (!["Open", "In Progress"].includes(String(record.status))) return false;
  const due = String(record.due_date ?? "").slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(due)) return false;
  const parsed = new Date(`${due}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === due && due < today;
}
export function needsAttention(record: Record<string, unknown>, today: string): boolean {
  return ["Open", "In Progress"].includes(String(record.status)) &&
    (isOverdue(record, today) || ["High", "Critical"].includes(String(record.priority)));
}
export function localDate(now = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
export function localTimestamp(value: unknown): string {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 19);
}
export function utcTimestamp(value: string): string {
  return value ? new Date(value).toISOString().replace(/\.\d{3}Z$/, "Z") : "";
}
export function filterRecords(rows: LiaisonRecord[], params: URLSearchParams, fields: string[], statusKey: string, today: string): LiaisonRecord[] {
  const search = (params.get("q") ?? "").trim().toLowerCase();
  const priorityOrder = Object.fromEntries(PRIORITIES.map((priority, i) => [priority, i]));
  const sort = params.get("sort") ?? fields[0];
  const value = (r: LiaisonRecord, key: string) => key === "report_state" ? reportState(r) : String(r[key] ?? "");
  return rows.filter(r => (!params.get("status") || value(r, statusKey) === params.get("status")) &&
    (!params.get("agency") || String(r.agency_id) === params.get("agency")) &&
    (!params.get("priority") || r.priority === params.get("priority")) &&
    (params.get("attention") !== "1" || needsAttention(r, today)) &&
    fields.some(field => value(r, field).toLowerCase().includes(search)))
    .sort((a,b) => {
      const comparison = sort === "priority" ? (priorityOrder[value(a, sort)] ?? -1) - (priorityOrder[value(b, sort)] ?? -1) : value(a, sort).localeCompare(value(b, sort), undefined, { numeric: true });
      return comparison * (params.get("direction") === "desc" ? -1 : 1);
    });
}
// PATCH only changed fields; never replay narrative, identity or server timestamps.
export function editPayload(section: string, patch: Record<string, unknown>, author: string): Record<string, unknown> {
  const allowed: Record<string, string[]> = {
    agencies: ["name", "code", "agency_type", "jurisdiction", "current_status", "assigned_liaison", "next_contact_due", "priority", "notes"],
    requests: ["summary", "requested_by", "due_date", "priority", "status", "objective_ids", "task_ids", "resource_request_ids"],
    "reporting-digests": ["lofr_summary", "ready_to_report"],
  };
  const result = Object.fromEntries(Object.entries(patch).filter(([key]) => allowed[section]?.includes(key)));
  if (typeof result.code === "string") result.code = result.code.trim().toUpperCase();
  if (section === "reporting-digests") result.updated_by = author;
  return result;
}

export function addWorkLink(current: (string | number)[], value: string, numeric: boolean): (string | number)[] {
  if (!value || (numeric && (!Number.isInteger(Number(value)) || Number(value) < 1))) return [...current];
  return current.some(existing => String(existing) === value) ? [...current] : [...current, numeric ? Number(value) : value];
}
