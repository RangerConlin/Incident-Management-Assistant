import { AUDIENCES, MESSAGE_TYPES } from "./model";
export interface Field { key: string; label: string; kind?: "text" | "textarea" | "select" | "checkbox" | "number"; options?: string[]; required?: boolean; }
export interface RecordConfig { collection: string; title: string; singular: string; labelKey: string; fields: Field[]; timestamp?: string; }
const field = (key: string, label: string, kind: Field["kind"] = "text", options?: string[], required = false): Field => ({ key, label, kind, options, required });
export const RECORD_CONFIG: Record<string, RecordConfig> = {
  media: { collection: "pio_media_log", title: "Media inquiries", singular: "Media inquiry", labelKey: "topic", fields: [
    field("topic", "Topic", "text", undefined, true), field("time", "Received at"), field("outlet_agency", "Outlet / agency"), field("contact_name", "Contact name"), field("contact_info", "Contact information"), field("deadline", "Deadline"), field("assigned_to", "Assigned to"),
    field("status", "Status", "select", ["New", "Assigned", "Drafting Response", "Waiting Approval", "Responded", "Follow-Up Needed", "Closed"]), field("related_message_id", "Related release ID", "number"), field("follow_up_needed", "Follow-up needed", "checkbox"),
  ] },
  misinformation: { collection: "pio_misinformation_items", title: "Misinformation / rumors", singular: "Misinformation item", labelKey: "claim_rumor", timestamp: "last_update", fields: [
    field("claim_rumor", "Claim / rumor", "textarea", undefined, true), field("source", "Source"), field("platform", "Platform"), field("first_seen", "First observed"), field("last_seen", "Last observed"), field("reported_by", "Reported by"), field("assigned_to", "Assigned to"),
    field("severity", "Severity", "select", ["Low", "Moderate", "High", "Critical"]), field("operational_impact", "Operational impact", "select", ["None", "Public Confusion", "Media Escalation", "Family Impact", "Volunteer Convergence", "Responder Safety Issue", "Access / Traffic Issue", "Investigation Sensitive", "Command-Level Concern"]),
    field("status", "Status", "select", ["New", "Verifying", "Monitoring", "Response Needed", "Drafting Correction", "Pending Approval", "Corrected", "Escalated", "Closed"]),
    field("verification_status", "Verification status", "select", ["Unknown", "False", "Partially True", "True", "Unable to Verify"]), field("source_reliability", "Source reliability"), field("verification_notes", "Verification notes", "textarea"), field("related_confirmed_facts", "Confirmed facts", "textarea"),
    field("response_decision", "Response decision", "select", ["Monitor Only", "Internal Advisory", "Public Correction", "Media Talking Point", "Partner Agency Coordination", "Escalate to Command", "Escalate to Law Enforcement"]), field("linked_response", "Linked response"), field("approval_status", "Approval status"), field("distribution_channels", "Distribution channels"), field("attachments_note", "Attachment reference"),
  ] },
  "talking-points": { collection: "pio_talking_points", title: "Talking points", singular: "Talking point", labelKey: "title", timestamp: "updated_at", fields: [
    field("title", "Title", "text", undefined, true), field("category", "Category", "select", ["Approved to Say", "Do Not Release", "Holding Statement", "Safety Instructions", "Media Q&A", "Next Update"]), field("body", "Body", "textarea"), field("status", "Status", "select", ["Draft", "Approved", "Retired"]), field("created_by", "Created by"), field("approved_by", "Approved by"),
  ] },
  templates: { collection: "pio_templates", title: "Letterhead / templates", singular: "Template", labelKey: "template_name", fields: [
    field("template_name", "Template name", "text", undefined, true), field("template_type", "Type", "select", [...MESSAGE_TYPES, "Media Statement", "Joint Agency Release"]), field("agency_name", "Agency name"), field("header_text", "Header", "textarea"), field("footer_text", "Footer", "textarea"), field("contact_block", "Contact block", "textarea"), field("logo_path", "Logo / asset reference"), field("release_label", "Release label"), field("default_classification_label", "Classification label"), field("default_font_name", "Font name"), field("default_footer_disclaimer", "Footer disclaimer", "textarea"), field("is_active", "Active", "checkbox"), field("version", "Version", "number"),
  ] },
  distribution: { collection: "pio_distribution_log", title: "Distribution log", singular: "Distribution record", labelKey: "recipient_outlet", fields: [
    field("message_id", "Release ID", "number", undefined, true), field("channel", "Channel", "select", ["Press Release Email", "Website", "Social Media", "Partner Agency", "Printed Handout", "Public Briefing", "Radio Announcement", "Internal Bulletin", "EOC Update"]), field("distributed_at", "Distributed at"), field("distributed_by", "Distributed by"), field("audience", "Audience", "select", AUDIENCES), field("recipient_outlet", "Recipient / outlet", "text", undefined, true), field("confirmation_notes", "Confirmation notes", "textarea"), field("attachment_export_path", "Attachment / export reference"),
  ] },
};
export function recordDefaults(config: RecordConfig): Record<string, unknown> {
  return Object.fromEntries(config.fields.map(f => [f.key, f.kind === "checkbox" ? (f.key === "is_active" ? 1 : 0) : f.kind === "select" ? f.options?.[0] ?? "" : f.key === "version" ? 1 : ""]));
}
