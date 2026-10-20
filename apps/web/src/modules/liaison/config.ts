import type { LiaisonSection } from "../../api/endpoints";
import { AGENCY_STATUSES, PRIORITIES, REQUEST_STATUSES } from "./model";
export interface LiaisonField {
  key: string; label: string; kind?: "text" | "textarea" | "select" | "datetime" | "date" | "checkbox" | "agency";
  options?: string[]; required?: boolean; createOnly?: boolean; editOnly?: boolean;
}
export interface LiaisonConfig {
  section: LiaisonSection; title: string; singular: string; labelKey: string; statusKey: string;
  statuses: string[]; columns: { key: string; label: string }[]; fields: LiaisonField[];
}
export const CONFIG: Record<string, LiaisonConfig> = {
  agencies: { section: "agencies", title: "Agency directory", singular: "Agency", labelKey: "name", statusKey: "current_status", statuses: AGENCY_STATUSES,
    columns: [{ key: "name", label: "Agency" }, { key: "code", label: "Code" }, { key: "current_status", label: "Status" }, { key: "agency_type", label: "Type" }, { key: "jurisdiction", label: "Jurisdiction" }, { key: "assigned_liaison", label: "Assigned liaison" }, { key: "priority", label: "Priority" }, { key: "last_contact", label: "Last contact" }, { key: "next_contact_due", label: "Next contact due" }],
    fields: [
      { key: "name", label: "Agency name", required: true }, { key: "code", label: "Agency code", required: true },
      { key: "agency_type", label: "Agency type" }, { key: "jurisdiction", label: "Jurisdiction" },
      { key: "current_status", label: "Status", kind: "select", options: AGENCY_STATUSES },
      { key: "assigned_liaison", label: "Assigned liaison" }, { key: "priority", label: "Priority", kind: "select", options: PRIORITIES },
      { key: "next_contact_due", label: "Next contact due", kind: "datetime" }, { key: "notes", label: "Notes", kind: "textarea" },
    ] },
  requests: { section: "requests", title: "Agency requests / offers", singular: "Request / offer", labelKey: "summary", statusKey: "status", statuses: REQUEST_STATUSES,
    columns: [{ key: "code", label: "Request code" }, { key: "summary", label: "Summary" }, { key: "agency_id", label: "Agency" }, { key: "request_type", label: "Type" }, { key: "status", label: "Status" }, { key: "priority", label: "Priority" }, { key: "requested_by", label: "Requested by" }, { key: "due_date", label: "Due date" }],
    fields: [
      { key: "agency_id", label: "Agency", kind: "agency", required: true, createOnly: true },
      { key: "request_type", label: "Type", kind: "select", options: ["Request", "Offer"], createOnly: true },
      { key: "summary", label: "Summary", kind: "textarea", required: true },
      { key: "requested_by", label: "Requested by" }, { key: "due_date", label: "Due date", kind: "date" },
      { key: "priority", label: "Priority", kind: "select", options: PRIORITIES },
      { key: "status", label: "Status", kind: "select", options: REQUEST_STATUSES },
    ] },
  reporting: { section: "reporting-digests", title: "Reporting board", singular: "Reporting entry", labelKey: "source_title", statusKey: "report_state", statuses: ["New", "In Progress", "Ready"],
    columns: [{ key: "source_title", label: "Source" }, { key: "report_state", label: "Readiness" }, { key: "lofr_summary", label: "External summary" }, { key: "submitted_by", label: "Submitted by" }, { key: "updated_at", label: "Updated" }],
    fields: [
      { key: "raw_note", label: "Internal source note", kind: "textarea", required: true, createOnly: true },
      { key: "lofr_summary", label: "Summary for external agencies", kind: "textarea", editOnly: true },
      { key: "ready_to_report", label: "Ready to report", kind: "checkbox", editOnly: true },
    ] },
  interactions: { section: "interactions", title: "Interaction log", singular: "Interaction", labelKey: "subject", statusKey: "", statuses: [],
    columns: [{ key: "subject", label: "Subject" }, { key: "agency_id", label: "Agency" }, { key: "interaction_type", label: "Type" }, { key: "occurred_at", label: "Occurred" }, { key: "summary", label: "Summary" }, { key: "followup_action", label: "Follow-up" }, { key: "followup_due", label: "Due" }],
    fields: [
      { key: "agency_id", label: "Agency", kind: "agency", required: true },
      { key: "interaction_type", label: "Type", kind: "select", options: ["Meeting", "Call", "Email", "Radio Contact", "Briefing", "Site Visit", "Video Conference", "Other"] },
      { key: "occurred_at", label: "Occurred at", kind: "datetime" }, { key: "subject", label: "Subject", required: true },
      { key: "summary", label: "Summary", kind: "textarea", required: true }, { key: "followup_action", label: "Follow-up action" },
      { key: "followup_assigned_to", label: "Follow-up assigned to" }, { key: "followup_due", label: "Follow-up due", kind: "datetime" },
    ] },
};
export function fieldDefaults(config: LiaisonConfig): Record<string, unknown> {
  return Object.fromEntries(config.fields.map(f => [f.key, f.key === "priority" ? "Medium" : f.kind === "checkbox" ? false : f.options?.[0] ?? ""]));
}
