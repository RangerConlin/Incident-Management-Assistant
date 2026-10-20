import type { Facility, RequestItem, ResourceRequest, ResourceStatusRow } from "../../api/types";
export const PRIORITIES = ["ROUTINE", "HIGH", "IMMEDIATE"];
export const TRANSITIONS: Record<string, string[]> = {
  DRAFT: ["SUBMITTED", "CANCELLED"], SUBMITTED: ["REVIEWED", "APPROVED", "DENIED", "CANCELLED"],
  REVIEWED: ["APPROVED", "DENIED", "CANCELLED"], APPROVED: ["ASSIGNED", "DENIED", "CANCELLED"],
  ASSIGNED: ["INTRANSIT", "CANCELLED"], INTRANSIT: ["DELIVERED", "PARTIAL", "CANCELLED"],
  DELIVERED: ["CLOSED", "PARTIAL"], PARTIAL: ["CLOSED", "ASSIGNED"], DENIED: ["REVIEWED"], CANCELLED: ["REVIEWED"], CLOSED: [],
};
export const TERMINAL = ["CLOSED", "DENIED", "CANCELLED"];
export const APPROVAL_TARGETS: Record<string, string> = { SUBMIT: "SUBMITTED", REVIEW: "REVIEWED", APPROVE: "APPROVED", DENY: "DENIED", CANCEL: "CANCELLED", REOPEN: "REVIEWED" };
export const ITEM_KINDS = ["PERSONNEL", "TEAM", "EQUIPMENT", "VEHICLE", "AIRCRAFT", "SUPPLY", "SERVICE", "COMMUNICATIONS"];
export const FULFILLMENT_STATUSES = ["SOURCING", "ASSIGNED", "INTRANSIT", "DELIVERED", "PARTIAL", "FAILED"];
export const FACILITY_TYPES = ["command_post", "staging", "base", "airport", "helibase", "helispot", "medical", "shelter", "supply", "parking", "other"];
export function label(value: string): string { if (value === "INTRANSIT") return "In Transit"; return value.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()); }
export function approvalActions(status: string): string[] {
  return Object.keys(APPROVAL_TARGETS).filter(action => (TRANSITIONS[status] ?? []).includes(APPROVAL_TARGETS[action]) && (action !== "REVIEW" || !["DENIED", "CANCELLED"].includes(status)) && (action !== "REOPEN" || ["DENIED", "CANCELLED"].includes(status)));
}
export function requestPatch(status: string, patch: Record<string, unknown>, actor: string): Record<string, unknown> {
  if (TERMINAL.includes(status)) throw new Error("Reopen this request before editing.");
  const editable = ["needed_by_utc", "delivery_location", "delivery_facility_id", "justification", "comms_requirements", "links"];
  if (status === "DRAFT") editable.push("title", "priority", "requesting_section");
  const invalid = Object.keys(patch).filter(key => !editable.includes(key));
  if (invalid.length) throw new Error(`These fields are locked: ${invalid.join(", ")}. Reload to review the current request.`);
  return { ...patch, actor_id: actor };
}
export function validateItems(items: RequestItem[]): void {
  for (const item of items) {
    if (!item.description.trim()) throw new Error("Every item needs a description.");
    if (!Number.isFinite(item.quantity) || item.quantity <= 0) throw new Error("Item quantities must be greater than zero.");
    if (!item.unit.trim()) throw new Error("Every item needs a unit.");
    if (!ITEM_KINDS.includes(item.kind)) throw new Error("Select a valid item kind.");
  }
}
export function localTimestamp(value: unknown): string {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 19);
}
export function utcTimestamp(value: string): string { return value ? new Date(value).toISOString().replace(/\.\d{3}Z$/, "Z") : ""; }
export function filterRequests(rows: ResourceRequest[], params: URLSearchParams): ResourceRequest[] {
  const q = (params.get("q") ?? "").trim().toLowerCase(); const priorityOrder = Object.fromEntries(PRIORITIES.map((p,i) => [p,i]));
  const sort = params.get("sort") ?? "last_updated_utc";
  return rows.filter(r => (!params.get("status") || r.status === params.get("status")) && (!params.get("priority") || r.priority === params.get("priority")) && `${r.title} ${r.requesting_section} ${r.justification ?? ""}`.toLowerCase().includes(q))
    .sort((a,b) => (sort === "priority" ? (priorityOrder[a.priority] ?? -1) - (priorityOrder[b.priority] ?? -1) : String(a[sort] ?? "").localeCompare(String(b[sort] ?? ""))) * (params.get("direction") === "asc" ? 1 : -1));
}
export function logisticsCounts(requests: ResourceRequest[], resources: ResourceStatusRow[], facilities: Facility[], now: Date) {
  const today = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  return {
    open: requests.filter(r => !TERMINAL.includes(r.status)).length,
    pending: requests.filter(r => ["SUBMITTED", "REVIEWED"].includes(r.status)).length,
    checkins: resources.filter(r => r.checked_in_time && today(new Date(r.checked_in_time)) === today(now)).length,
    vehicles: resources.filter(r => r.entity_type === "vehicle" && r.status === "Available").length,
    facilities: facilities.filter(f => f.status === "active").length,
    demob: resources.filter(r => r.status === "Preparing for Demobilization"),
  };
}
export function facilityPayload(values: Record<string, unknown>): Record<string, unknown> {
  const fields = ["name", "facility_type", "status", "address", "latitude", "longitude", "geocoded_address", "icao_code", "manager_personnel_id", "manager_name", "contact_name", "contact_phone", "notes", "function_tags", "served_sections", "is_primary", "metadata"];
  const payload = Object.fromEntries(fields.filter(key => values[key] !== undefined).map(key => [key, values[key]]));
  for (const [key, limit] of [["latitude",90], ["longitude",180]] as const) {
    const value = payload[key];
    if (value !== undefined && value !== null && (typeof value !== "number" || !Number.isFinite(value) || Math.abs(value) > limit)) throw new Error(`Invalid ${key}.`);
  }
  for (const key of ["function_tags", "served_sections"]) {
    if (typeof payload[key] === "string") payload[key] = String(payload[key]).split(",").map(v => v.trim()).filter(Boolean);
  }
  return payload;
}
