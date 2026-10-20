import type { PioMessage, PioRecord } from "../../api/types";

export const MESSAGE_TYPES = ["Press Release", "Public Advisory", "Situation Update", "Missing Person Bulletin", "Road / Access Notice", "Safety Notice", "Internal Bulletin", "Agency Update", "Misinformation Correction", "Holding Statement", "Social Media Post"];
export const MESSAGE_STATUSES = ["Draft", "Pending Approval", "Returned for Revision", "Approved", "Published", "Needs Corrections", "Archived"];
export const AUDIENCES = ["Public", "Media", "Agency", "Internal"];
export const PRIORITIES = ["Low", "Normal", "High", "Critical"];
export const EDITABLE_STATUSES = ["Draft", "Returned for Revision", "Needs Corrections"];
export const RELEASE_FIELDS = ["title", "subtitle", "type", "audience", "priority", "dateline", "body", "next_update_statement", "boilerplate", "related_operational_period_id", "template_id"] as const;
export interface LifecycleAction { label: string; target: string; }
export const LIFECYCLE: Record<string, LifecycleAction[]> = {
  Draft: [{ label: "Submit for approval", target: "Pending Approval" }],
  "Returned for Revision": [{ label: "Resubmit for approval", target: "Pending Approval" }],
  "Pending Approval": [{ label: "Approve", target: "Approved" }, { label: "Return for revision", target: "Returned for Revision" }],
  Approved: [{ label: "Mark published / released", target: "Published" }, { label: "Return for revision", target: "Returned for Revision" }],
  Published: [{ label: "Flag corrections needed", target: "Needs Corrections" }, { label: "Archive", target: "Archived" }],
  "Needs Corrections": [{ label: "Submit correction for approval", target: "Pending Approval" }],
};

// Never copy lifecycle metadata/history into a new draft or overwrite it while editing.
export function releasePayload(message: Partial<PioMessage>, user: string, copy = false): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const key of RELEASE_FIELDS) if (message[key] !== undefined) payload[key] = message[key];
  if (copy || !message.id) Object.assign(payload, { status: "Draft", created_by: user });
  else Object.assign(payload, {
    id: message.id, created_at: message.created_at, created_by: message.created_by,
    approved_by: message.approved_by ?? "", approved_at: message.approved_at ?? "",
    published_by: message.published_by ?? "", published_at: message.published_at ?? "",
    archived_by: message.archived_by ?? "", archived_at: message.archived_at ?? "",
  });
  payload._revision_user = user;
  return payload;
}

export function filterPioRows<T>(rows: T[], search: string, status: string, fields: string[], sort: string, direction: string): T[] {
  const value = (row: T, key: string) => String((row as Record<string, unknown>)[key] ?? "");
  return rows.filter(row => (!status || value(row, "status") === status) &&
    fields.some(key => value(row, key).toLowerCase().includes(search.trim().toLowerCase())))
    .sort((a, b) => value(a, sort).localeCompare(value(b, sort), undefined, { numeric: true }) * (direction === "asc" ? 1 : -1));
}

export function mergePreview(text: string, message: Partial<PioMessage>, template: PioRecord | undefined,
  incident: { name?: string; number?: string } | undefined): string {
  const values: Record<string, string> = {
    incident_name: incident?.name ?? "", incident_number: incident?.number ?? "",
    operational_period: message.related_operational_period_id ?? "", release_datetime: message.published_at || message.updated_at ? new Date(message.published_at || message.updated_at!).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" }) : "",
    prepared_by: message.created_by ?? "", approved_by: message.approved_by ?? "", pio_contact_name: "", pio_contact_phone: "",
    agency_name: String(template?.agency_name ?? ""), release_title: message.title ?? "", release_subtitle: message.subtitle ?? "",
    release_body: message.body ?? "", next_update_time: message.next_update_statement ?? "", public_summary: (message.body ?? "").slice(0, 500), boilerplate: message.boilerplate ?? "",
  };
  return text.replace(/\{([a-z_]+)\}/g, (match, key: string) => values[key] ?? match);
}

export function localTimestamp(value: unknown): string {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 19);
}
export function utcTimestamp(value: string): string {
  if (!value) return "";
  return new Date(value).toISOString().replace(/\.\d{3}Z$/, "Z");
}
