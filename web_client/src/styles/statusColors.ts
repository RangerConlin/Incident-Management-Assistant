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
  | "demobilized";

export type TeamTypeKey = "gt" | "udf" | "lsar" | "df" | "gt/uas" | "udf/uas" | "uas" | "air";

type StatusDomain = "team" | "task" | "resource";

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
