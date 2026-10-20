import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

function loadClient(buildUrl, fetcher, token = "token") {
  const source = readFileSync(new URL("../src/api/client.ts",import.meta.url),"utf8");
  const code = ts.transpileModule(source,{ compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const module = { exports: {} };
  new Function("require","module","exports","fetch","localStorage",code)(() => ({ buildUrl }),module,module.exports,fetcher,{ getItem: () => token });
  return module.exports;
}
test("PDF download uses the configured connect-code target and JWT, and returns binary bytes",async () => {
  const calls = [];
  const client = loadClient(path => `https://server.example/r/CODE${path}`,async (...args) => {
    calls.push(args);
    return new Response(new Blob(["%PDF-1.7\n"],{ type: "application/pdf" }),{ headers: { "Content-Type": "application/pdf","Content-Disposition": 'attachment; filename="ics_213rr_request.pdf"' } });
  });
  const result = await client.api.download("/api/incidents/id/form-exports",{ form_id: "ics_213rr",source_id: "request" });
  assert.equal(calls[0][0],"https://server.example/r/CODE/api/incidents/id/form-exports");
  assert.equal(calls[0][1].headers.Authorization,"Bearer token");
  assert.equal(result.filename,"ics_213rr_request.pdf"); assert.equal(await result.blob.text(),"%PDF-1.7\n");
});
test("download errors retain the server error instead of generating a fake PDF",async () => {
  const client = loadClient(path => path,async () => new Response(JSON.stringify({ detail: "Source not found" }),{ status: 404,headers: { "Content-Type": "application/json" } }));
  await assert.rejects(() => client.api.download("/exports",{}),error => error.status === 404 && error.message === "Source not found");
});
test("successful non-PDF responses are rejected and server filenames cannot inject paths",async () => {
  const invalid = loadClient(path => path,async () => new Response("{}",{ headers: { "Content-Type": "application/json" } }));
  await assert.rejects(() => invalid.api.download("/exports",{}),/did not return a PDF/);
  const client = loadClient(path => path,async () => new Response("%PDF",{ headers: { "Content-Type": "application/pdf","Content-Disposition": 'attachment; filename="folder/evil.pdf"' } }));
  assert.equal((await client.api.download("/exports",{})).filename,"folder_evil.pdf");
});
