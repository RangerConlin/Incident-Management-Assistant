import type { PlannedTool } from "./model";

/** Config for the simple record boards (messaging, vendors, permits, health inspections). */
export interface RecordConfig {
  tool: Exclude<PlannedTool, "quick-assignments">;
  path: string;
  title: string;
  singular: string;
  intro: string;
  /** Status the server assigns when none is given; offered as the starting suggestion. */
  defaultStatus: string;
  scheduledLabel: string;
  /** Values the backend stores under `metadata` for this tool. */
  meta: { key: string; label: string; kind?: "date" }[];
}

export const RECORD_CONFIGS: Record<string, RecordConfig> = {
  messaging: {
    tool: "promotions", path: "messaging", title: "Messaging", singular: "Message", defaultStatus: "Draft", scheduledLabel: "Send at",
    intro: "Plan announcements and public messages for the event: who they reach, how, and when.",
    meta: [{ key: "audience", label: "Audience" }, { key: "channel", label: "Channel" }],
  },
  vendors: {
    tool: "vendors", path: "vendors", title: "Vendors", singular: "Vendor", defaultStatus: "Pending", scheduledLabel: "Expected arrival",
    intro: "Track vendors working the event, their contact, and where they are set up.",
    meta: [{ key: "contact", label: "Contact" }],
  },
  permits: {
    tool: "permits", path: "permits", title: "Permits", singular: "Permit", defaultStatus: "Pending", scheduledLabel: "Applied / due",
    intro: "Keep the permits the event depends on, who issued them, and when they expire.",
    meta: [{ key: "issuer", label: "Issuer" }, { key: "expires_on", label: "Expires on", kind: "date" }],
  },
  health: {
    tool: "health-inspections", path: "health", title: "Health inspections", singular: "Inspection", defaultStatus: "Scheduled", scheduledLabel: "Inspection time",
    intro: "Schedule health and safety inspections and record what was found.",
    meta: [{ key: "target", label: "Inspection target" }, { key: "result", label: "Result" }],
  },
};
