// TS analog of styles/styles.py's team_status_colors()/task_status_colors()
// accessors — resolves a domain + status key to CSS var references instead
// of a QBrush. Values live in statusColors.css; this just gives autocomplete
// and a compile error on a typo'd key. Theme switching is a `data-theme`
// attribute flip on <html>, no re-render needed for color.

export type ThemeName = "dark" | "light";

export type TeamStatusKey =
  | "aol"
  | "arrival"
  | "assigned"
  | "available"
  | "break"
  | "briefed"
  | "crew rest"
  | "enroute"
  | "out of service"
  | "report writing"
  | "returning"
  | "tol"
  | "wheels down"
  | "post incident"
  | "find"
  | "complete";

export type TaskStatusKey = "created" | "planned" | "assigned" | "in progress" | "complete" | "cancelled";

export type ResourceStatusKey =
  | "pending"
  | "enroute"
  | "checked in"
  | "assigned"
  | "available"
  | "out of service"
  | "preparing for demobilization"
  | "demobilized"
  | "cancelled";

export type TeamTypeKey = "gt" | "udf" | "lsar" | "df" | "gt/uas" | "udf/uas" | "uas" | "air" | "k9" | "util";

export type ObjectiveStatusKey = "draft" | "active" | "deferred" | "completed" | "cancelled";

export type ObjectivePriorityKey = "low" | "normal" | "high" | "urgent";

export type OperationalPeriodStatusKey = "Planned" | "Active" | "Complete" | "Canceled";

export type MeetingStatusKey = "draft" | "scheduled" | "ready" | "completed" | "canceled";

export type SitrepStatusKey =
  | "draft"
  | "ready_for_review"
  | "needs_revision"
  | "approved"
  | "distributed"
  | "archived";

type StatusDomain =
  | "team"
  | "task"
  | "resource"
  | "objective"
  | "objective-priority"
  | "op-period"
  | "meeting"
  | "sitrep"
  | "pio"
  | "liaison-agency"
  | "liaison-request"
  | "liaison-priority"
  | "liaison-report"
  | "logistics-request"
  | "logistics-priority"
  | "facility"
  | "approval"
  | "approval-step"
  | "intel-priority";

function slug(key: string): string {
  return key.trim().toLowerCase().replace(/\s+/g, "-").replace(/\//g, "-");
}

export function statusVar(domain: StatusDomain, key: string): { bg: string; fg: string } {
  const s = slug(key);
  return { bg: `var(--status-${domain}-${s}-bg)`, fg: `var(--status-${domain}-${s}-fg)` };
}

export function teamStatusVar(key: TeamStatusKey | string) {
  return statusVar("team", key);
}

export function taskStatusVar(key: TaskStatusKey | string) {
  return statusVar("task", key);
}

export function resourceStatusVar(key: ResourceStatusKey | string) {
  return statusVar("resource", key);
}

export function objectiveStatusVar(key: ObjectiveStatusKey | string) {
  return statusVar("objective", key);
}

export function objectivePriorityVar(key: ObjectivePriorityKey | string) {
  return statusVar("objective-priority", key);
}

export function operationalPeriodStatusVar(key: OperationalPeriodStatusKey | string) {
  return statusVar("op-period", key);
}

export function meetingStatusVar(key: MeetingStatusKey | string) {
  return statusVar("meeting", key);
}

export function sitrepStatusVar(key: SitrepStatusKey | string) {
  return statusVar("sitrep", key);
}

export function teamTypeVar(key: TeamTypeKey | string): string {
  return `var(--team-type-${slug(key)})`;
}

const THEME_KEY = "sarapp.theme";

export function getStoredTheme(): ThemeName {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage unavailable — fall through to default
  }
  return "dark";
}

export function applyTheme(theme: ThemeName): void {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // best-effort persistence only
  }
}

export type PioStatusKey = "Draft" | "Pending Approval" | "Returned for Revision" | "Approved" | "Published" | "Needs Corrections" | "Archived";
export function pioStatusVar(key: PioStatusKey | string) { return statusVar("pio", key); }

export type LiaisonAgencyStatusKey = "Not Contacted" | "Contacted" | "Awaiting Response" | "Standby" | "Supporting" | "Active" | "Demobilizing" | "Released" | "Unavailable";
export type LiaisonRequestStatusKey = "Open" | "In Progress" | "Resolved" | "Declined" | "Cancelled";
export type LiaisonPriorityKey = "Low" | "Medium" | "High" | "Critical";
export function liaisonAgencyStatusVar(key: LiaisonAgencyStatusKey | string) { return statusVar("liaison-agency", key); }
export function liaisonRequestStatusVar(key: LiaisonRequestStatusKey | string) { return statusVar("liaison-request", key); }
export function liaisonPriorityVar(key: LiaisonPriorityKey | string) { return statusVar("liaison-priority", key); }
export function liaisonReportStateVar(key: "ready" | "not_ready" | string) { return statusVar("liaison-report", key); }

export type LogisticsRequestStatusKey = "DRAFT" | "SUBMITTED" | "REVIEWED" | "APPROVED" | "ASSIGNED" | "INTRANSIT" | "DELIVERED" | "PARTIAL" | "DENIED" | "CANCELLED" | "CLOSED";
export function logisticsRequestStatusVar(key: LogisticsRequestStatusKey | string) { return statusVar("logistics-request",key); }
export function logisticsPriorityVar(key: "ROUTINE" | "HIGH" | "IMMEDIATE" | string) { return statusVar("logistics-priority",key); }
export function facilityStatusVar(key: "active" | "planned" | "closed" | string) { return statusVar("facility",key); }

export type ApprovalStatusKey = "not_started" | "pending" | "approved" | "rejected";
export type ApprovalStepStatusKey = "waiting" | "active" | "completed" | "skipped";
export function approvalStatusVar(key: ApprovalStatusKey | string) { return statusVar("approval", key); }
export function approvalStepStatusVar(key: ApprovalStepStatusKey | string) { return statusVar("approval-step", key); }

export type IntelPriorityKey = "Critical" | "High" | "Medium" | "Low";
export function intelPriorityVar(key: IntelPriorityKey | string) { return statusVar("intel-priority", key); }
