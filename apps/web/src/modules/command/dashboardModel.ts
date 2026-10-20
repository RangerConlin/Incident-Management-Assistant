import type { TaskRow } from "../../api/types";

export function formatCommandTime(value: string | null | undefined): string {
  if (!value) return "Not set";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Invalid date" : date.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export function tasksDueSoon(rows: TaskRow[], now: number): TaskRow[] {
  return rows.filter((row) => !["complete", "cancelled"].includes(row.status.toLowerCase()) &&
    row.due_datetime && new Date(row.due_datetime).getTime() <= now + 24 * 60 * 60 * 1000)
    .sort((a, b) => new Date(a.due_datetime!).getTime() - new Date(b.due_datetime!).getTime());
}

