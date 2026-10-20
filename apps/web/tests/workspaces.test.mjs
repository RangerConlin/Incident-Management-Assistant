import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
import React from "react";
import { renderToString } from "react-dom/server";
import { Routes, Route } from "react-router-dom";
import { StaticRouter } from "react-router-dom/server.js";

const require = createRequire(import.meta.url);
function load(path, replacements = {}) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", compiled)(id => replacements[id] ?? (id.endsWith(".css") ? {} : require(id)), module, module.exports);
  return module.exports;
}
const { WORKSPACES } = load("../src/modules/workspaces/config.ts");
const model = load("../src/modules/workspaces/model.ts");
const workspace = path => WORKSPACES.find(w => w.path === path);

test("workspace payloads allow only supported fields and protect create-only data", () => {
  const expenses = workspace("/finance").datasets[0];
  assert.deepEqual(model.payloadFor(expenses, { description: "Overwrite", amount_subtotal: 1, status: "Approved", approved_by: "Other", notes: "New", receipt_attached: true, int_id: 9 }, false, "INC"), { receipt_attached: true, notes: "New" });
  const hasty = workspace("/toolkits/initial-response").datasets[0];
  assert.deepEqual(model.payloadFor(hasty, { area: "North", priority: "High", operations_task_id: "12" }, true, "INC"), { area: "North", priority: "High", operations_task_id: 12, incident_id: "INC" });
  assert.deepEqual(model.payloadFor(hasty, { area: "Overwrite", operations_task_id: "13", _id: "bad" }, false, "INC"), { operations_task_id: 13 });
});

test("SPE uses canonical nested numeric inputs without replaying computed score", () => {
  const hazards = workspace("/safety").datasets[1];
  const body = model.payloadFor(hazards, { title: "Slope", default_spe: { severity: 3, probability: 2, exposure: 4, score: 24 }, "default_spe.severity": "4", controls: [" Rope ", "", "Spotter"], id: 5 }, true, "INC");
  assert.deepEqual(body, { title: "Slope", default_spe: { severity: 4, probability: 2, exposure: 4 }, controls: ["Rope", "Spotter"] });
  assert.throws(() => model.payloadFor(hazards, { title: "Slope", "default_spe.severity": 9 }, true, "INC"), /range/);
  assert.throws(() => model.payloadFor(hazards, { title: " " }, true, "INC"), /required/);
});

test("URL filters compose, numeric sorting is numeric, input arrays remain unchanged", () => {
  const rows = [{ id: 1, title: "North", status: "Active", amount: 20 }, { id: 2, title: "North trail", status: "Active", amount: 3 }, { id: 3, title: "South", status: "Closed", amount: 1 }];
  assert.deepEqual(model.filterRows(rows, ["title", "amount"], new URLSearchParams("q=NORTH&status=Active&sort=amount")).map(r => r.id), [2, 1]);
  assert.deepEqual(model.filterRows(rows, ["title"], new URLSearchParams("sort=amount&direction=desc")).map(r => r.id), [1, 2, 3]);
  assert.deepEqual(rows.map(r => r.id), [1, 2, 3]);
});

test("canonical IDs, incident escaping, master scope, and datetime precision", () => {
  assert.equal(model.datasetUrl(workspace("/intel").datasets[0], "A/B"), "/api/incidents/A%2FB/intel/subjects");
  assert.equal(model.recordUrl(workspace("/personnel").datasets[0], "INC", "23"), "/api/master/personnel/23");
  assert.equal(model.recordId(workspace("/finance").datasets[0], { id: 5, _id: "private" }), "5");
  assert.equal(model.recordId(workspace("/safety").datasets[1], { id: 7, _id: "private" }), "7");
  assert.equal(model.localDatetime("invalid"), "");
  const reports = workspace("/safety").datasets[0];
  assert.equal(model.payloadFor(reports, { time: "2026-10-20T10:11:12.123Z" }, true, "INC").time, "2026-10-20T10:11:12Z");
});

test("CAP ORM preserves operational period on record operations and supplies it in create payloads", () => {
  const dataset = { ...workspace("/safety").datasets.find(d => d.key === "orm"), endpoint: "safety/orm/hazards?op=3" };
  assert.equal(model.recordUrl(dataset, "A/B", "8"), "/api/incidents/A%2FB/safety/orm/hazards/8?op=3");
  const values = { sub_activity: "Climbing", hazard_outcome: "Fall", initial_risk: "H", control_text: "Rope", residual_risk: "M" };
  assert.equal(model.payloadFor(dataset, values, true, "INC").op_period, 3);
  assert.equal(model.payloadFor(dataset, values, false, "INC").op_period, undefined);
  assert.equal(model.defaultValues(dataset.fields).initial_risk, "");
});

test("event schedule read DTO maps to its explicit write contract", () => {
  const dataset = workspace("/toolkits/planned-event").datasets.find(d => d.key === "schedule");
  assert.deepEqual(model.payloadFor(dataset, { title: "Briefing", summary: "At the command post", status: "Scheduled", id: 3 }, false, "INC"), { name: "Briefing", notes: "At the command post", status: "Scheduled" });
});

test("new module endpoints honor supported methods and reject unsupported writes", async () => {
  const calls = [];
  const api = Object.fromEntries(["get", "post", "put", "patch", "delete"].map(method => [method, async (...args) => { calls.push([method, ...args]); return []; }]));
  const endpoints = load("../src/api/endpoints.ts", { "./client": { api }, "../modules/workspaces/model": model });
  const person = workspace("/personnel").datasets[0];
  await endpoints.saveWorkspaceRecord(person, "INC", "3", { name: "Updated" });
  assert.deepEqual(calls.pop(), ["put", "/api/master/personnel/3", { name: "Updated" }]);
  const subject = workspace("/intel").datasets[0];
  await endpoints.deleteWorkspaceRecord(subject, "A/B", "subject/id");
  assert.deepEqual(calls.pop(), ["delete", "/api/incidents/A%2FB/intel/subjects/subject%2Fid"]);
  const reports = workspace("/safety").datasets[0];
  assert.throws(() => endpoints.saveWorkspaceRecord(reports, "INC", "5", {}), /unavailable/);
  assert.throws(() => endpoints.deleteWorkspaceRecord(reports, "INC", "5"), /unavailable/);
  await endpoints.assignPersonCertification("3", "7", 2);
  assert.deepEqual(calls.pop(), ["post", "/api/master/certifications/personnel/3/7", { level: 2 }]);
  await endpoints.weatherHistory("A/B", "station/a");
  assert.deepEqual(calls.pop(), ["get", "/api/incidents/A%2FB/weather/history?location_id=station%2Fa"]);
});

test("every registry page resolves to an existing screen and workspace routes are unique", () => {
  const { MODULE_REGISTRY } = load("../src/shell/moduleRegistry.ts");
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  const explicit = [...app.matchAll(/<Route\s+path="([^"]+)"/g)].map(m => `/${m[1]}`);
  assert.equal(new Set(WORKSPACES.map(w => w.path)).size, WORKSPACES.length);
  for (const section of MODULE_REGISTRY) for (const entry of section.modules) {
    assert.equal(entry.status, "live", entry.path);
    assert.ok(explicit.includes(entry.path) || WORKSPACES.some(w => w.path === entry.path), `Missing route: ${entry.path}`);
  }
  const { findLiveModule } = load("../src/shell/moduleRegistry.ts");
  assert.equal(findLiveModule("/personnel/certifications").key, "certifications");
  assert.equal(findLiveModule("/personnel-missing"), undefined);
});

test("all dataset boards and create/detail routes render, with write restrictions reflected in controls", () => {
  let rows = [];
  const actions = { save: { isPending: false, reset() {} }, remove: { isPending: false, reset() {} } };
  const Page = load("../src/modules/workspaces/WorkspacePage.tsx", {
    "../../auth/SessionContext": { useSession: () => ({ incidentId: "INC" }) },
    "../../components/table/DataTable": { default: ({ rows, rowKey }) => React.createElement("div", null, rows.map(r => React.createElement("span", { key: rowKey(r) }, rowKey(r)))) },
    "../../components/table/StatusPill": { default: ({ statusKey }) => React.createElement("span", null, statusKey) },
    "../../utils/formatDateTime": { formatDateTime: value => String(value).replace(/\.\d+Z$/, "Z") },
    "./hooks": { useDataset: () => ({ data: rows, isPending: false, isError: false }), useRecordActions: () => actions }, "./model": model,
  }).default;
  function render(w, dataset, suffix = "") {
    return renderToString(React.createElement(StaticRouter, { location: `${w.path}/${dataset.key}${suffix}` }, React.createElement(Routes, null,
      React.createElement(Route, { path: `${w.path}/:datasetKey/:recordId?`, element: React.createElement(Page, { workspace: w }) }))));
  }
  for (const w of WORKSPACES) for (const dataset of w.datasets) {
    rows = [{ [dataset.idKey ?? "id"]: 4, title: "Existing record", name: "Existing name" }];
    assert.match(render(w, dataset), /1<!-- --> records/);
    assert.match(render(w, dataset, "/4"), /Record details/);
    if (dataset.create) assert.match(render(w, dataset, "/new"), /Create record/);
    if (!dataset.update) assert.doesNotMatch(render(w, dataset, "/4"), /Save changes/);
    if (!dataset.remove) assert.doesNotMatch(render(w, dataset, "/4"), /Remove record/);
  }
});

test("specialized pages render their empty and account-link states", () => {
  const session = { useSession: () => ({ incidentId: "INC", personnel: null }) };
  const Table = { default: () => React.createElement("p", null, "Table") };
  const query = {
    useQuery: options => ({ data: options.queryKey.includes("weather_config") ? { locations: [] } : options.queryKey.includes("weather_history") ? { samples: [] } : [], isPending: false }),
    useMutation: () => ({ isPending: false, reset() {} }), useQueryClient: () => ({ invalidateQueries() {} }),
  };
  for (const name of ["Approvals", "Certifications", "Weather", "Demobilization", "Customization"]) {
    const Page = load(`../src/modules/workspaces/${name}Page.tsx`, {
      "@tanstack/react-query": query, "../../api/endpoints": {}, "../../auth/SessionContext": session,
      "../../components/table/DataTable": Table, "../../components/approvals/ApprovalPanel": { default: () => null },
      "../../utils/formatDateTime": { formatDateTime: String }, "./config": { WORKSPACES },
      "../logistics/resourceStatus/hooks": { useResourceStatusRows: () => ({ data: [] }) },
      "../../styles/statusColors": { getStoredTheme: () => "dark" },
    }).default;
    const html = renderToString(React.createElement(StaticRouter, { location: "/" }, React.createElement(Page)));
    assert.match(html, /<h1>/, name);
    assert.doesNotMatch(html, /undefined|NaN/, name);
  }
});
