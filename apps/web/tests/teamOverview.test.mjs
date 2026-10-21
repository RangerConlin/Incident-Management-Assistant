import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/modules/operations/teamStatus/teamOverviewModel.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const model = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("team type choices use the desktop operational codes", () => {
  assert.deepEqual(model.TEAM_TYPE_OPTIONS.map((type) => type.value), [
    "GT", "UDF", "LSAR", "DF", "GT/UAS", "UDF/UAS", "UAS", "AIR", "K9", "UTIL",
  ]);
});

test("display status values map to the same canonical API keys as desktop", () => {
  assert.equal(model.statusKeyForValue("En Route"), "enroute");
  assert.equal(model.statusKeyForValue("On Scene"), "arrival");
  assert.equal(model.statusKeyForValue("Rest"), "crew rest");
});

test("assigned-unit choices mirror desktop classifications and hierarchy", () => {
  const position = (position_id, title, classification, parent_position_id = null, sort_order = 0) =>
    ({ position_id, title, classification, parent_position_id, sort_order });
  const options = model.assignableUnitOptions([
    position(1, "Incident Commander", "command"),
    position(2, "Operations", "section", 1),
    position(3, "Team Leader", "position", 2),
    position(4, "Ground Branch", "branch", 2),
  ]);
  assert.deepEqual(options.map((option) => option.value), [2, 4]);
  assert.match(options[1].label, /Ground Branch \(branch\)$/);
});
