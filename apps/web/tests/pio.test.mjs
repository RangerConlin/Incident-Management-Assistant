import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";
const source = readFileSync(new URL("../src/modules/publicInformation/model.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { releasePayload, filterPioRows, mergePreview, LIFECYCLE, localTimestamp, utcTimestamp } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("new update drafts clear identity, lifecycle metadata, and embedded approval history", () => {
  const source = { id: 9, title: "Update", body: "Facts", status: "Published", template_id: 2,
    approved_by: "Reviewer", published_at: "2026-10-19T12:00:00Z", approvals: [{ id: 1 }], created_at: "yesterday" };
  const result = releasePayload(source, "Editor", true);
  assert.equal(result.status, "Draft"); assert.equal(result.created_by, "Editor"); assert.equal(result.template_id, 2);
  for (const key of ["id", "approved_by", "published_at", "approvals", "created_at"]) assert.equal(key in result, false);
  assert.equal(source.status, "Published");
});
test("editing preserves release metadata without overwriting status or approval history", () => {
  const result = releasePayload({ id: 2, title: "Correction", status: "Needs Corrections", created_at: "created", created_by: "Writer", approved_by: "Approver", published_at: "published", approvals: [{ id: 1 }] }, "Editor");
  assert.equal(result.id, 2); assert.equal(result.approved_by, "Approver"); assert.equal(result.published_at, "published");
  assert.equal(result.created_at, "created"); assert.equal(result._revision_user, "Editor");
  assert.equal("status" in result, false); assert.equal("approvals" in result, false);
});
test("release workflow only publishes approved releases and leaves archives closed", () => {
  assert.deepEqual(LIFECYCLE.Draft.map(a => a.target), ["Pending Approval"]);
  assert.equal(LIFECYCLE.Approved.some(a => a.target === "Published"), true);
  for (const status of ["Draft", "Pending Approval", "Returned for Revision", "Needs Corrections"]) assert.equal(LIFECYCLE[status].some(a => a.target === "Published"), false);
  assert.equal(LIFECYCLE.Archived, undefined);
});
test("search combines status filtering and numeric sorting without changing source rows", () => {
  const rows = [{ title: "Release 10", status: "Draft" }, { title: "Release 2", status: "Draft" }, { title: "Release 1", status: "Approved" }];
  assert.deepEqual(filterPioRows(rows, " RELEASE ", "Draft", ["title"], "title", "asc").map(r => r.title), ["Release 2", "Release 10"]);
  assert.equal(rows[0].title, "Release 10");
});
test("preview resolves incident identity and keeps user content as plain text", () => {
  assert.equal(mergePreview("{incident_name} / {incident_number} / {release_title} / {unknown}", { title: "<script>alert(1)</script>" }, undefined, { name: "Incident", number: "123" }), "Incident / 123 / <script>alert(1)</script> / {unknown}");
  assert.equal(mergePreview("{release_body}", { body: "{approved_by}" }, undefined, undefined), "{approved_by}");
});
test("timestamp inputs round-trip local time and remove subsecond precision", () => {
  const iso = "2026-10-19T12:15:30Z";
  assert.equal(utcTimestamp(localTimestamp(iso)), iso);
  assert.equal(localTimestamp("invalid"), ""); assert.equal(utcTimestamp(""), "");
  assert.equal(utcTimestamp(localTimestamp("2026-10-19T12:15:30.123Z")), iso);
});


test("rendered preview escapes message and template HTML and preserves multiline text", async () => {
  const { createRequire } = await import("node:module");
  const require = createRequire(import.meta.url);
  const React = require("react"); const { renderToStaticMarkup } = require("react-dom/server");
  const previewSource = readFileSync(new URL("../src/modules/publicInformation/ReleasePreview.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(previewSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", compiled)(id => id === "./model" ? { mergePreview } : require(id), module, module.exports);
  const html = renderToStaticMarkup(React.createElement(module.exports.default, {
    message: { title: "<script>alert(1)</script>", body: "First line\nSecond line", type: "Press Release" },
    template: { id: 1, header_text: "<img src=x onerror=alert(1)> {incident_name}" }, incident: { name: "Incident" },
  }));
  assert.equal(html.includes("<script>"), false); assert.equal(html.includes("<img"), false);
  assert.ok(html.includes("&lt;script&gt;")); assert.ok(html.includes("First line\nSecond line"));
  assert.ok(html.includes("Incident"));
});
