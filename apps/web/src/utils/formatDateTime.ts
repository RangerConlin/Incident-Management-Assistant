// Human-readable timestamp formatting for UI text — no sub-minute precision,
// never a raw ISO string. Web analog of agents.md's "trim milliseconds/
// microseconds from UI text" rule for the desktop app.
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}
