import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
function loadTs(path,replacements = {}) {
  const source = readFileSync(new URL(path,import.meta.url),"utf8");
  const code = ts.transpileModule(source,{ compilerOptions: { module: ts.ModuleKind.CommonJS,jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const module = { exports: {} };
  new Function("require","module","exports",code)(name => replacements[name] ?? require(name),module,module.exports);
  return module.exports;
}
const model = loadTs("../src/modules/logistics/model.ts");
test("approval actions match current server transitions and reopen only denied/cancelled requests",() => {
  assert.deepEqual(model.approvalActions("DRAFT"),["SUBMIT","CANCEL"]);
  assert.deepEqual(model.approvalActions("DENIED"),["REOPEN"]);
  assert.deepEqual(model.approvalActions("CANCELLED"),["REOPEN"]);
  assert.deepEqual(model.approvalActions("CLOSED"),[]);
  for (const status of Object.keys(model.TRANSITIONS)) for (const action of model.approvalActions(status)) assert.ok(model.TRANSITIONS[status].includes(model.APPROVAL_TARGETS[action]));
});
test("post-submission header saves cannot rewrite critical fields, histories or identity",() => {
  assert.deepEqual(model.requestPatch("DRAFT",{ title: "Need supplies",priority: "HIGH" },"actor"),{ title: "Need supplies",priority: "HIGH",actor_id: "actor" });
  assert.deepEqual(model.requestPatch("APPROVED",{ delivery_location: "ICP" },"actor"),{ delivery_location: "ICP",actor_id: "actor" });
  for (const key of ["title","priority","requesting_section","id","status","items","audit","approvals","fulfillments"]) assert.throws(() => model.requestPatch("SUBMITTED",{ [key]: "bad" },"actor"),/locked/);
  for (const status of ["CLOSED","DENIED","CANCELLED"]) assert.throws(() => model.requestPatch(status,{},"actor"),/Reopen/);
});
test("items validate quantities and preserve supplied IDs and catalog references",() => {
  const item = { id: "existing",kind: "SUPPLY",description: "Water",quantity: 2,unit: "case",ref_id: "catalog" };
  model.validateItems([item]); assert.equal(item.id,"existing"); assert.equal(item.ref_id,"catalog");
  for (const quantity of [0,-1,NaN,Infinity]) assert.throws(() => model.validateItems([{ ...item,quantity }]),/greater/);
  assert.throws(() => model.validateItems([{ ...item,description: " " }]),/description/);
  assert.throws(() => model.validateItems([{ ...item,kind: "invalid" }]),/kind/);
});
test("dashboard counts use request lifecycle and resource status without mixing closed or unavailable resources",() => {
  const counts = model.logisticsCounts([{ status: "DRAFT" },{ status: "SUBMITTED" },{ status: "CLOSED" },{ status: "DENIED" }],
    [{ entity_type: "vehicle",status: "Available",checked_in_time: "2026-10-20T12:00:00" },{ entity_type: "vehicle",status: "Out of Service" },{ entity_type: "equipment",status: "Preparing for Demobilization" }],
    [{ status: "active" },{ status: "planned" }],new Date("2026-10-20T16:00:00"));
  assert.deepEqual({ open: counts.open,pending: counts.pending,vehicles: counts.vehicles,facilities: counts.facilities,checkins: counts.checkins },{ open: 2,pending: 1,vehicles: 1,facilities: 1,checkins: 1 });
  assert.equal(counts.demob.length,1);
});
test("request filters compose and priority sorting follows urgency",() => {
  const rows = [{ id: "1",title: "Water",status: "DRAFT",priority: "HIGH",requesting_section: "Ops" },{ id: "2",title: "Water",status: "DRAFT",priority: "IMMEDIATE",requesting_section: "Ops" },{ id: "3",title: "Food",status: "CLOSED",priority: "ROUTINE" }];
  assert.deepEqual(model.filterRequests(rows,new URLSearchParams("q=WATER&status=DRAFT&sort=priority&direction=desc")).map(r => r.id),["2","1"]);
  assert.equal(rows[0].id,"1");
});
test("facility payload preserves metadata and canonical tags without replaying alias or server fields",() => {
  const result = model.facilityPayload({ id: "server",name: "ICP",latitude: 0,longitude: -73,metadata: { source: "existing" },function_tags: "command, staging",served_sections: ["Operations"],capabilities: ["old"],created_at: "server" });
  assert.deepEqual(result.function_tags,["command","staging"]); assert.deepEqual(result.metadata,{ source: "existing" });
  for (const key of ["id","capabilities","created_at"]) assert.equal(key in result,false);
  assert.throws(() => model.facilityPayload({ latitude: 91 }),/latitude/);
  assert.throws(() => model.facilityPayload({ longitude: -181 }),/longitude/);
});
test("Logistics APIs use dedicated action/item/fulfillment paths and canonical facilities PUT",async () => {
  const calls = []; const fake = Object.fromEntries(["get","post","patch","put","delete"].map(method => [method,async (...args) => { calls.push([method,...args]); return {}; }]));
  const api = loadTs("../src/api/endpoints.ts",{ "./client": { api: fake } });
  await api.resourceRequestApproval("INC/1","request","DENY","actor","Reason");
  await api.replaceResourceRequestItems("INC/1","request",[]);
  await api.updateResourceRequestFulfillment("INC/1","request","fulfillment",{ status: "DELIVERED" });
  await api.updateFacility("INC/1","facility",{ name: "ICP" });
  assert.deepEqual(calls.map(c => c.slice(0,2)),[["post","/api/incidents/INC%2F1/logistics/resource-requests/request/approvals"],["put","/api/incidents/INC%2F1/logistics/resource-requests/request/items"],["patch","/api/incidents/INC%2F1/logistics/resource-requests/request/fulfillments/fulfillment"],["put","/api/incidents/INC%2F1/facilities/facility"]]);
  assert.deepEqual(calls[0][2],{ action: "DENY",actor_id: "actor",note: "Reason" });
});
test("timestamps retain seconds and safely round-trip between local inputs and API UTC",() => {
  assert.equal(model.utcTimestamp(model.localTimestamp("2026-10-20T12:01:02.999Z")),"2026-10-20T12:01:02Z");
  assert.equal(model.localTimestamp("invalid"),""); assert.equal(model.utcTimestamp(""),"");
});
test("print summary escapes request/item text rather than interpreting markup",() => {
  const React = require("react"); const { renderToStaticMarkup } = require("react-dom/server");
  const Summary = loadTs("../src/modules/logistics/RequestPrintSummary.tsx",{ "./model": model,"../../utils/formatDateTime": { formatDateTime: () => "Oct 20, 2026" } }).default;
  const html = renderToStaticMarkup(React.createElement(Summary,{ request: { id: "1",title: "<script>alert(1)</script>",status: "DRAFT",priority: "HIGH",items: [{ id: "item",description: "<img src=x>",quantity: 2,unit: "each" }],approvals: [],fulfillments: [] } }));
  assert.equal(html.includes("<script>"),false); assert.equal(html.includes("<img"),false);
  assert.ok(html.includes("&lt;script&gt;")); assert.ok(html.includes("Resource request summary"));
});
