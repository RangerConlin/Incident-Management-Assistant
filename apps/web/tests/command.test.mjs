import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/modules/command/dashboardModel.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { tasksDueSoon, formatCommandTime } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("deadlines include overdue and the next 24 hours, exclude closed, invalid and undated tasks", () => {
  const now = Date.parse("2026-10-20T00:00:00Z");
  const row = (id, status, due_datetime) => ({ id, status, due_datetime });
  const rows = [row(1, "planned", "2026-10-20T12:00:00Z"), row(2, "assigned", "2026-10-19T12:00:00Z"),
    row(3, "complete", "2026-10-19T12:00:00Z"), row(4, "cancelled", "2026-10-20T12:00:00Z"),
    row(5, "created", null), row(6, "planned", "bad"), row(7, "planned", "2026-10-21T00:00:01Z"),
    row(8, "planned", "2026-10-21T00:00:00Z")];
  assert.deepEqual(tasksDueSoon(rows, now).map(r => r.id), [2, 1, 8]);
  assert.equal(rows[0].id, 1);
});
test("timestamps handle missing and invalid values and omit subsecond precision", () => {
  assert.equal(formatCommandTime(null), "Not set");
  assert.equal(formatCommandTime("bad"), "Invalid date");
  assert.equal(formatCommandTime("2026-10-20T00:00:00.123Z"), formatCommandTime("2026-10-20T00:00:00Z"));
});
