import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const scriptDir = path.dirname(__filename);
const workspaceRoot = path.resolve(scriptDir, "..", "..", "..");
const mainRoot = path.join(workspaceRoot, "Incident-Management-Assistant");
const mobileRoot = path.join(workspaceRoot, "ICS-Mobile-App");
const outputPath = path.join(mainRoot, "docs", "architecture", "repo_file_inventory.xlsx");

const legacyImportRoots = [
  "modules",
  "utils",
  "sarapp_db",
  "cloud_server",
  "cloud_router",
  "lan_server",
  "server",
  "services",
  "app",
  "ui",
  "panels",
  "models",
  "bridge",
  "notifications",
  "styles",
  "core",
];

const textExtensions = new Set([
  ".bat",
  ".cmd",
  ".conf",
  ".css",
  ".csv",
  ".dart",
  ".dockerfile",
  ".env",
  ".gitignore",
  ".html",
  ".ini",
  ".js",
  ".json",
  ".jsx",
  ".kt",
  ".kts",
  ".md",
  ".mjs",
  ".ps1",
  ".py",
  ".qss",
  ".sql",
  ".swift",
  ".toml",
  ".ts",
  ".tsx",
  ".txt",
  ".xml",
  ".yaml",
  ".yml",
]);

const generatedOrLocalDirs = new Set([
  ".dart_tool",
  ".gradle",
  ".idea",
  ".pytest_cache",
  ".venv",
  "__pycache__",
  "build",
  "dist",
  "logs",
  "node_modules",
  "tmp",
]);

const generatedOrLocalFileNames = new Set([
  ".flutter-plugins-dependencies",
  "local.properties",
  "upload-keystore.jks",
  "key.properties",
]);

function normalizeRel(value) {
  return value.split(path.sep).join("/");
}

function topSegment(relPath) {
  return normalizeRel(relPath).split("/")[0] || "";
}

function extensionFor(fileName) {
  if (fileName === ".gitignore" || fileName === ".dockerignore" || fileName === ".env.example") {
    return fileName;
  }
  return path.extname(fileName).toLowerCase();
}

function isProbablyText(fileName) {
  const ext = extensionFor(fileName);
  return textExtensions.has(ext);
}

function hasPathSegment(relPath, segmentSet) {
  return normalizeRel(relPath).split("/").some((part) => segmentSet.has(part));
}

async function walkFiles(root, repository) {
  const rows = [];

  async function walk(dir) {
    let entries = [];
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.name === ".git") {
        continue;
      }
      const fullPath = path.join(dir, entry.name);
      const relForSkip = normalizeRel(path.relative(root, fullPath));
      if (relForSkip === "tools/dev/node_modules" || relForSkip.startsWith("tools/dev/node_modules/")) {
        continue;
      }
      if (entry.isDirectory()) {
        await walk(fullPath);
        continue;
      }
      if (!entry.isFile()) {
        continue;
      }
      const stat = await fs.stat(fullPath);
      const relPath = normalizeRel(path.relative(root, fullPath));
      const fileName = path.basename(fullPath);
      const ext = extensionFor(fileName);
      const analysis = await analyzeTextFile(fullPath, ext);
      const recommendation = recommend(repository, relPath, fileName, ext);
      rows.push({
        repository,
        relativePath: relPath,
        name: fileName,
        extension: ext,
        sizeKb: Math.round((stat.size / 1024) * 10) / 10,
        modified: stat.mtime.toISOString().slice(0, 19).replace("T", " "),
        currentLocation: normalizeRel(path.dirname(relPath)),
        ...recommendation,
        legacyImportRefs: analysis.legacyImportRefs,
        pathAssumptionRefs: analysis.pathAssumptionRefs,
        lineCount: analysis.lineCount,
      });
    }
  }

  await walk(root);
  return rows;
}

async function analyzeTextFile(fullPath, ext) {
  if (!isProbablyText(path.basename(fullPath))) {
    return { legacyImportRefs: 0, pathAssumptionRefs: 0, lineCount: "" };
  }
  let text = "";
  try {
    const stat = await fs.stat(fullPath);
    if (stat.size > 2_000_000) {
      return { legacyImportRefs: 0, pathAssumptionRefs: 0, lineCount: "" };
    }
    text = await fs.readFile(fullPath, "utf8");
  } catch {
    return { legacyImportRefs: 0, pathAssumptionRefs: 0, lineCount: "" };
  }
  const lineCount = text.length ? text.split(/\r\n|\r|\n/).length : 0;
  let legacyImportRefs = 0;
  if (ext === ".py") {
    const importPattern = new RegExp(
      `^(?:from|import)\\s+(?:${legacyImportRoots.join("|")})(?:\\.|\\s|$)`,
      "gm",
    );
    legacyImportRefs = (text.match(importPattern) || []).length;
  }
  const pathAssumptionRefs = (
    text.match(/Path\(__file__\)|resolve\(\)\.parents|sys\.path|PYTHONPATH|apps[\\/]+web|data[\\/]+db[\\/]+sarapp_db/g) ||
    []
  ).length;
  return { legacyImportRefs, pathAssumptionRefs, lineCount };
}

function recommend(repository, relPath, fileName, ext) {
  const rel = normalizeRel(relPath);
  const top = topSegment(rel);
  const generated = hasPathSegment(rel, generatedOrLocalDirs) || generatedOrLocalFileNames.has(fileName);
  const pycache = rel.includes("__pycache__/") || fileName.endsWith(".pyc");

  if (generated || pycache) {
    return recommendation(
      "Delete or exclude",
      "",
      "generated/local",
      "Cleanup",
      "High",
      "Generated, cache, local environment, build output, or local secret/signing material.",
    );
  }

  if (repository === "mobile") {
    if (top === ".agents" || top === ".claude") {
      return recommendation("Review/archive", `apps/mobile/${rel}`, "agent metadata", "Mobile merge", "Medium", "Agent-local metadata may be useful but should not be blindly merged.");
    }
    if (top === "docs") {
      return recommendation("Move", `apps/mobile/${rel}`, "mobile docs", "Mobile merge", "High", "Mobile-specific documentation should travel with the mobile app.");
    }
    if (top === "tools") {
      return recommendation("Move", `apps/mobile/${rel}`, "mobile tooling", "Mobile merge", "High", "Mobile-specific tooling should travel with the mobile app.");
    }
    if (["android", "assets", "ios", "lib", "test", "third_party", "web", "windows"].includes(top)) {
      return recommendation("Move", `apps/mobile/${rel}`, "mobile app", "Mobile merge", "High", "Flutter source/platform files belong under apps/mobile.");
    }
    if (["pubspec.yaml", "pubspec.lock", "analysis_options.yaml", "firebase.json", ".env.example", ".gitignore", ".metadata", "README.md"].includes(fileName)) {
      return recommendation("Move", `apps/mobile/${rel}`, "mobile app", "Mobile merge", "High", "Flutter project root file belongs under apps/mobile.");
    }
    if (fileName.includes("Design Document") || fileName.includes("Timeline") || fileName === "tracking_plan.md" || fileName === "Current Mobile API Contract.txt") {
      return recommendation("Move/review", `apps/mobile/docs/${fileName}`, "mobile planning", "Mobile merge", "Medium", "Useful planning/API context, but may need consolidation into shared API docs.");
    }
    return recommendation("Review", `apps/mobile/${rel}`, "mobile other", "Mobile merge", "Medium", "Mobile repo file without a specific rule.");
  }

  if (rel.startsWith("apps/web/")) {
    return recommendation("Keep", rel, "web app", "Web migration", "Low", "Web client has already moved into the target apps/web runtime.");
  }
  if (rel.startsWith("services/cloud_server/")) {
    return recommendation("Keep", rel, "cloud service", "Services migration", "Low", "Cloud server runtime has already moved into the target services/cloud_server runtime.");
  }
  if (rel.startsWith("services/lan_server/")) {
    return recommendation("Keep", rel, "lan service", "Services migration", "Low", "LAN server runtime has already moved into the target services/lan_server runtime.");
  }
  if (rel.startsWith("services/cloud_router/")) {
    return recommendation("Keep", rel, "cloud router", "Services migration", "Low", "Cloud router runtime has already moved into the target services/cloud_router runtime.");
  }
  if (top === "cloud_server") {
    return recommendation("Move", `services/cloud_server/${rel.replace(/^cloud_server\//, "")}`, "cloud service", "Services migration", "High", "Cloud server runtime belongs under services/cloud_server.");
  }
  if (top === "cloud_router") {
    return recommendation("Move", `services/cloud_router/${rel.replace(/^cloud_router\//, "")}`, "cloud router", "Services migration", "High", "Cloud router runtime belongs under services/cloud_router.");
  }
  if (top === "lan_server") {
    return recommendation("Move", `services/lan_server/${rel.replace(/^lan_server\//, "")}`, "lan service", "Services migration", "High", "LAN server runtime belongs under services/lan_server.");
  }
  if (rel.startsWith("server/sarapp_db/sarapp_db/api/")) {
    return recommendation("Move", `server/sarapp_api/${rel.replace(/^data\/db\/sarapp_db\/api\//, "")}`, "backend API", "Server migration", "High", "FastAPI backend implementation belongs under server/sarapp_api.");
  }
  if (rel.startsWith("server/sarapp_db/sarapp_db/")) {
    return recommendation("Move", `server/sarapp_db/${rel.replace(/^data\/db\/sarapp_db\//, "")}`, "backend DB", "Server migration", "High", "sarapp_db package is backend implementation code.");
  }
  if (rel.startsWith("data/db/")) {
    return recommendation("Move/review", `server/sarapp_db/seed_loaders/${rel.replace(/^data\/db\//, "")}`, "db scripts", "Server migration", "Medium", "Database scripts should move near server DB code or tools after review.");
  }
  if (top === "data") {
    return recommendation("Keep/review", rel, "data content", "Data cleanup", "Medium", "Content data can remain under data, but generated exports and sample incidents should be reviewed.");
  }
  if (top === "docs") {
    return recommendation("Keep", rel, "documentation", "Docs", "High", "Documentation already lives in the target docs area.");
  }
  if (top === "Design Documents") {
    return recommendation("Move/archive", `docs/archive/design-documents/${rel.replace(/^docs\\archive\\design-documents\\//, "")}`, "legacy docs", "Docs cleanup", "Medium", "Design documents should be archived under docs if still useful.");
  }
  if (top === "scripts") {
    return recommendation("Move/review", `tools/scripts/${rel.replace(/^tools\\scripts\\//, "")}`, "script", "Tools cleanup", "Medium", "Scripts should move under tools after usefulness review.");
  }
  if (top === "tools") {
    return recommendation("Keep/review", rel, "tooling", "Tools cleanup", "Medium", "Existing tools folder mostly matches target, but old migration utilities should be reviewed.");
  }
  if (top === "server") {
    return recommendation("Move/review", `services/lan_server/${rel.replace(/^server\//, "legacy_server/")}`, "legacy server console", "Services migration", "Low", "Current server folder appears to be legacy/local server console code, not target backend server.");
  }
  if (top === "services") {
    return recommendation("Move/review", `apps/desktop/sarapp_desktop/services/${rel.replace(/^services\//, "")}`, "desktop service", "Desktop migration", "Low", "Existing services folder appears desktop/domain-service oriented, not target runtime services.");
  }
  if (["modules", "ui", "panels", "bridge", "models", "notifications", "profiles", "assets", "settings", "styles", "utils", "core", "app", "forms", "ui_bootstrap"].includes(top)) {
    const mappedTop = top === "app" ? "legacy_app" : top;
    return recommendation("Move", `apps/desktop/sarapp_desktop/${mappedTop}/${rel.split("/").slice(1).join("/")}`, "desktop app", "Desktop migration", "Medium", "Desktop/client code should move under apps/desktop.");
  }
  if (["main.py", "sarapp_server.py", "requirements.txt", "pyproject.toml", "pytest.ini", "conftest.py", "settings.json", "Start SARApp Desktop.bat"].includes(fileName)) {
    return recommendation("Move/review", `apps/desktop/${rel}`, "desktop root", "Desktop migration", "Medium", "Desktop root/config file should move with desktop packaging or be split by runtime.");
  }
  if (fileName.startsWith("_scratch") || fileName.startsWith("_gen_") || fileName.includes("backlog") || fileName.includes("transition")) {
    return recommendation("Review/archive", `tools/dev/${rel}`, "scratch/planning", "Cleanup", "Medium", "Scratch, generator, backlog, or transition file should be reviewed before keeping.");
  }
  if (top === "tests") {
    return recommendation("Move/review", `apps/desktop/tests/${rel.replace(/^tests\//, "")}`, "tests", "Test migration", "Medium", "Top-level tests should move near the runtime/package they cover after review.");
  }
  if (top === "packaging") {
    return recommendation("Move/review", `infra/desktop/${rel.replace(/^packaging\//, "")}`, "packaging", "Infra migration", "Medium", "Packaging assets/scripts should move under infra or apps/desktop packaging.");
  }
  if (top === ".github") {
    return recommendation("Keep/review", rel, "repository config", "CI cleanup", "Medium", "Repository-level automation can remain at the root but should be updated for new paths.");
  }
  if (top.startsWith(".")) {
    return recommendation("Review/archive", rel, "local metadata", "Cleanup", "Low", "Hidden metadata/config should be kept only if intentionally shared.");
  }
  return recommendation("Review", rel, "uncategorized", "Review", "Low", "No specific migration rule matched.");
}

function recommendation(disposition, newLocation, category, phase, confidence, rationale) {
  return {
    disposition,
    newLocation,
    category,
    migrationPhase: phase,
    confidence,
    rationale,
  };
}

function countBy(rows, key) {
  const counts = new Map();
  for (const row of rows) {
    counts.set(row[key], (counts.get(row[key]) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

function columnLetter(indexZeroBased) {
  let n = indexZeroBased + 1;
  let s = "";
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - m) / 26);
  }
  return s;
}

function writeMatrix(sheet, startRow, startCol, matrix, chunkSize = 1000) {
  for (let i = 0; i < matrix.length; i += chunkSize) {
    const chunk = matrix.slice(i, i + chunkSize);
    sheet.getRangeByIndexes(startRow + i, startCol, chunk.length, chunk[0].length).values = chunk;
  }
}

function applyHeaderStyle(range) {
  range.format = {
    fill: "#1F4E78",
    font: { name: "Arial", bold: true, color: "#FFFFFF", size: 10 },
    verticalAlignment: "center",
    horizontalAlignment: "center",
  };
}

function applySheetBase(sheet) {
  sheet.showGridLines = false;
  sheet.getRange("A:Z").format.font = { name: "Arial", size: 10, color: "#1F2937" };
}

async function main() {
  const rows = [
    ...(await walkFiles(mainRoot, "main")),
    ...(await walkFiles(mobileRoot, "mobile")),
  ].sort((a, b) => `${a.repository}/${a.relativePath}`.localeCompare(`${b.repository}/${b.relativePath}`));

  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("Summary");
  const inventory = workbook.worksheets.add("Inventory");
  const readme = workbook.worksheets.add("ReadMe");
  summary.tabColor = "#1F4E78";
  inventory.tabColor = "#5B9BD5";
  readme.tabColor = "#A6A6A6";
  for (const sheet of [summary, inventory, readme]) {
    applySheetBase(sheet);
  }

  const headers = [
    "Repository",
    "Relative path",
    "Name",
    "Extension",
    "Size KB",
    "Modified",
    "Current location",
    "Suggested disposition",
    "Actual status",
    "Suggested new location",
    "Category",
    "Migration phase",
    "Confidence",
    "Rationale",
    "Legacy import refs",
    "Path assumption refs",
    "Line count",
    "Decision notes",
  ];
  const matrix = [
    headers,
    ...rows.map((row) => [
      row.repository,
      row.relativePath,
      row.name,
      row.extension,
      row.sizeKb,
      row.modified,
      row.currentLocation,
      row.disposition,
      "Not started",
      row.newLocation,
      row.category,
      row.migrationPhase,
      row.confidence,
      row.rationale,
      row.legacyImportRefs,
      row.pathAssumptionRefs,
      row.lineCount,
      "",
    ]),
  ];
  writeMatrix(inventory, 0, 0, matrix, 750);
  const lastCol = columnLetter(headers.length - 1);
  const lastRow = matrix.length;
  applyHeaderStyle(inventory.getRange(`A1:${lastCol}1`));
  inventory.freezePanes.freezeRows(1);
  inventory.getRange(`A1:${lastCol}${lastRow}`).format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  inventory.getRange("E:E").format.numberFormat = "#,##0.0";
  inventory.getRange("N:P").format.numberFormat = "#,##0";
  inventory.getRange("A:A").format.columnWidth = 12;
  inventory.getRange("B:B").format.columnWidth = 58;
  inventory.getRange("C:C").format.columnWidth = 30;
  inventory.getRange("G:G").format.columnWidth = 36;
  inventory.getRange("H:H").format.columnWidth = 20;
  inventory.getRange("I:I").format.columnWidth = 18;
  inventory.getRange("J:J").format.columnWidth = 62;
  inventory.getRange("K:M").format.columnWidth = 20;
  inventory.getRange("N:N").format.columnWidth = 64;
  inventory.getRange("N:N").format.wrapText = true;
  inventory.getRange("Q:Q").format.columnWidth = 48;
  inventory.getRange("Q:Q").format.wrapText = true;
  inventory.getRange(`I2:I${lastRow}`).dataValidation = {
    rule: {
      type: "list",
      values: [
        "Not started",
        "Kept",
        "Moved",
        "Deleted",
        "Archived",
        "Excluded",
        "Needs review",
        "Blocked",
      ],
    },
  };
  inventory.tables.add(`A1:${lastCol}${lastRow}`, true, "RepoInventory");

  const dispositionCounts = countBy(rows, "disposition");
  const phaseCounts = countBy(rows, "migrationPhase");
  const categoryCounts = countBy(rows, "category");
  const repoCounts = countBy(rows, "repository");
  const totals = {
    files: rows.length,
    sizeKb: Math.round(rows.reduce((sum, row) => sum + row.sizeKb, 0) * 10) / 10,
    legacyImportRefs: rows.reduce((sum, row) => sum + row.legacyImportRefs, 0),
    pathAssumptionRefs: rows.reduce((sum, row) => sum + row.pathAssumptionRefs, 0),
  };

  summary.getRange("A2").values = [["Repository File Inventory"]];
  summary.getRange("A2").format.font = { name: "Arial", size: 14, bold: true, color: "#1F2937" };
  summary.getRange("A3").values = [["Generated inventory for the main project plus the mobile app, excluding .git internals."]];
  summary.getRange("A3").format.font = { name: "Arial", italic: true, color: "#4B5563" };
  summary.getRange("A5:B9").values = [
    ["Metric", "Value"],
    ["Files inventoried", totals.files],
    ["Total size KB", totals.sizeKb],
    ["Legacy import references", totals.legacyImportRefs],
    ["Path assumption references", totals.pathAssumptionRefs],
  ];
  applyHeaderStyle(summary.getRange("A5:B5"));
  summary.getRange("A5:B9").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  summary.getRange("B6:B9").format.numberFormat = "#,##0.0";
  summary.getRange("A:B").format.columnWidth = 28;

  writeCountBlock(summary, "D5", "Disposition", dispositionCounts);
  writeCountBlock(summary, "G5", "Migration phase", phaseCounts);
  writeCountBlock(summary, "J5", "Repository", repoCounts);
  writeCountBlock(summary, "A12", "Category", categoryCounts);

  readme.getRange("A2").values = [["How to use this workbook"]];
  readme.getRange("A2").format.font = { name: "Arial", size: 14, bold: true };
  readme.getRange("A4:B14").values = [
    ["Column", "Meaning"],
    ["Suggested disposition", "Initial recommendation: keep, move, review, archive, delete, or exclude."],
    ["Actual status", "Editable tracking field for the real migration outcome."],
    ["Suggested new location", "Proposed target path when the migration rule is clear."],
    ["Confidence", "How reliable the automated recommendation is. Low means human review is important."],
    ["Legacy import refs", "Count of Python imports from legacy top-level roots in that file."],
    ["Path assumption refs", "Count of likely root/path assumptions such as sys.path, Path(__file__), or old directory names."],
    ["Migration phase", "Suggested stage for addressing the file."],
    ["Repository", "main = Incident-Management-Assistant, mobile = ICS-Mobile-App."],
    ["Decision notes", "Editable notes for human decisions, blockers, or cleanup rationale."],
    ["Scope note", "The inventory excludes .git internals but intentionally includes local/generated folders so they can be marked for cleanup."],
  ];
  applyHeaderStyle(readme.getRange("A4:B4"));
  readme.getRange("A4:B14").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  readme.getRange("A:A").format.columnWidth = 24;
  readme.getRange("B:B").format.columnWidth = 96;
  readme.getRange("B:B").format.wrapText = true;

  workbook.recalculate();
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const preview = await workbook.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(path.dirname(outputPath), "repo_file_inventory_preview.png"), new Uint8Array(await preview.arrayBuffer()));
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);

  const summaryInspect = await workbook.inspect({
    kind: "table",
    sheetId: "Summary",
    range: "A5:B9",
    include: "values",
    tableMaxRows: 10,
    tableMaxCols: 4,
  });
  console.log(summaryInspect.ndjson);
  console.log(`Saved ${outputPath}`);
}

function writeCountBlock(sheet, anchor, title, counts) {
  const start = parseAnchor(anchor);
  const data = [[title, "Files"], ...counts.map(([name, count]) => [name, count])];
  sheet.getRangeByIndexes(start.row, start.col, data.length, 2).values = data;
  applyHeaderStyle(sheet.getRangeByIndexes(start.row, start.col, 1, 2));
  sheet.getRangeByIndexes(start.row, start.col, data.length, 2).format.borders = {
    preset: "all",
    style: "thin",
    color: "#D9E2F3",
  };
  sheet.getRangeByIndexes(start.row, start.col + 1, data.length, 1).format.numberFormat = "#,##0";
  sheet.getRangeByIndexes(start.row, start.col, data.length, 1).format.columnWidth = 24;
  sheet.getRangeByIndexes(start.row, start.col + 1, data.length, 1).format.columnWidth = 12;
}

function parseAnchor(anchor) {
  const match = /^([A-Z]+)(\d+)$/.exec(anchor);
  if (!match) {
    throw new Error(`Invalid anchor: ${anchor}`);
  }
  let col = 0;
  for (const ch of match[1]) {
    col = col * 26 + (ch.charCodeAt(0) - 64);
  }
  return { row: Number(match[2]) - 1, col: col - 1 };
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
