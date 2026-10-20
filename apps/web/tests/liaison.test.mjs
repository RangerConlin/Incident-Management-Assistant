import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
function loadTs(path, replacements = {}) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", compiled)(id => replacements[id] ?? require(id), module, module.exports);
  return module.exports;
}
const model = loadTs("../src/modules/liaison/model.ts");

test("request attention follows open status, priority, and local calendar deadlines", () => {
  assert.equal(model.isOverdue({ status: "Open", due_date: "2026-10-19" }, "2026-10-20"), true);
  assert.equal(model.isOverdue({ status: "In Progress", due_date: "2026-10-20" }, "2026-10-20"), false);
  for (const due_date of ["", "invalid", "2026-02-30"]) assert.equal(model.isOverdue({ status: "Open", due_date }, "2026-10-20"), false);
  for (const status of ["Resolved", "Declined", "Cancelled"]) assert.equal(model.needsAttention({ status, priority: "Critical", due_date: "2026-01-01" }, "2026-10-20"), false);
  assert.equal(model.needsAttention({ status: "Open", priority: "High" }, "2026-10-20"), true);
});
test("report readiness distinguishes raw notes, curated drafts and ready summaries", () => {
  assert.equal(model.reportState({ raw_note: "Internal", lofr_summary: "  " }), "New");
  assert.equal(model.reportState({ lofr_summary: "Curated" }), "In Progress");
  assert.equal(model.reportState({ lofr_summary: "Curated", ready_to_report: true }), "Ready");
});
test("editing requests cannot replay or erase narrative, identity or server timestamps", () => {
  assert.deepEqual(model.editPayload("requests", { summary: "Updated", narrative: [], code: "BAD", agency_id: 9, int_id: 10, task_ids: [3], updated_at: "old" }, "Author"), { summary: "Updated", task_ids: [3] });
  assert.deepEqual(model.editPayload("reporting-digests", { raw_note: "Overwrite", source_id: "Other", lofr_summary: "Safe", ready_to_report: true }, "Reviewer"), { lofr_summary: "Safe", ready_to_report: true, updated_by: "Reviewer" });
  assert.deepEqual(model.editPayload("agencies", { code: " county ", last_contact: "old" }, "User"), { code: "COUNTY" });
});
test("URL search, status, agency and priority filters compose with semantic priority sorting", () => {
  const rows = [{ int_id: 1, summary: "Access", agency_id: 2, status: "Open", priority: "Low" }, { int_id: 2, summary: "Access", agency_id: 2, status: "Open", priority: "Critical" }, { int_id: 3, summary: "Other", agency_id: 3, status: "Resolved", priority: "High" }];
  const result = model.filterRecords(rows, new URLSearchParams("q=ACCESS&agency=2&status=Open&sort=priority&direction=desc"), ["summary"], "status", "2026-10-20");
  assert.deepEqual(result.map(r => r.int_id), [2, 1]); assert.equal(rows[0].int_id, 1);
  assert.deepEqual(model.filterRecords(rows, new URLSearchParams("attention=1"), ["summary"], "status", "2026-10-20").map(r => r.int_id), [2]);
});
test("work links retain canonical numeric task IDs and string objective/resource IDs without duplicates", () => {
  assert.deepEqual(model.addWorkLink([2], "2", true), [2]);
  assert.deepEqual(model.addWorkLink([2], "3", true), [2,3]);
  assert.deepEqual(model.addWorkLink([], "objective-id", false), ["objective-id"]);
  assert.deepEqual(model.addWorkLink([], "not-a-number", true), []);
});
test("timestamp controls round-trip local time and omit subsecond precision", () => {
  assert.equal(model.utcTimestamp(model.localTimestamp("2026-10-20T10:20:30.123Z")), "2026-10-20T10:20:30Z");
  assert.equal(model.localTimestamp("invalid"), ""); assert.equal(model.utcTimestamp(""), "");
});
test("Liaison API calls preserve incident scope and supported HTTP methods", async () => {
  const calls = [];
  const fakeApi = Object.fromEntries(["get", "post", "patch", "delete"].map(method => [method, async (...args) => { calls.push([method, ...args]); return {}; }]));
  const api = loadTs("../src/api/endpoints.ts", { "./client": { api: fakeApi } });
  await api.listLiaisonRecords("INC/1", "requests");
  await api.updateLiaisonRecord("INC/1", "requests", 7, { status: "Resolved" });
  await api.addLiaisonNarrative("INC/1", 7, { category: "Feedback", text: "Note", author: "Liaison" });
  await api.deleteLiaisonRecord("INC/1", "reporting-digests", 8);
  assert.deepEqual(calls.map(c => c.slice(0,2)), [
    ["get", "/api/incidents/INC%2F1/liaison/requests"], ["patch", "/api/incidents/INC%2F1/liaison/requests/7"],
    ["post", "/api/incidents/INC%2F1/liaison/requests/7/narrative"], ["delete", "/api/incidents/INC%2F1/liaison/reporting-digests/8"],
  ]);
  assert.deepEqual(calls[1][2], { status: "Resolved" });
});
test("agency fields render escaped text, required selections and timestamps without fractions", () => {
  const React = require("react"); const { renderToStaticMarkup } = require("react-dom/server");
  const Fields = loadTs("../src/modules/liaison/Fields.tsx", { "./model": model }).default;
  const html = renderToStaticMarkup(React.createElement(Fields, { fields: [{ key: "notes", label: "Notes", kind: "textarea" }, { key: "agency_id", label: "Agency", kind: "agency", required: true }, { key: "occurred_at", label: "Occurred", kind: "datetime" }], values: { notes: "<script>alert(1)</script>", occurred_at: "2026-10-20T10:20:30.123Z" }, agencies: [{ int_id: 1, name: "<Agency>" }], update() {} }));
  assert.equal(html.includes("<script>"), false); assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(html.includes("&lt;Agency&gt;")); assert.ok(html.includes('required=""')); assert.equal(html.includes(".123"), false);
});
