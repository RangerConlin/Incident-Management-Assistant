import { useMemo, useState } from "react";
import { useSession } from "../../auth/SessionContext";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import StatusPill from "../../components/table/StatusPill";
import type { Hazard, WorkAssignment, WorkAssignmentHazard } from "../../api/types";
import { useWorkAssignments } from "../planning/workAssignments/hooks";
import { useCreateHazard, useDeleteHazard, useHazards, useUpdateHazard } from "./hooks";

type Tab = "consolidated" | "by-assignment" | "register";

// Matches desktop's safety/panels/ics215a_panel.py ("Incident Action Safety
// Analysis (ICS-215A)") merged with safety/orm/ui/risk_manager_window.py,
// per your direction: the full viewer/editor of hazards and SPE for the
// incident in one place. Consolidated/By Assignment read the legacy
// embedded-per-WA hazard shape (risk_level/likelihood/severity);
// Register reads+edits the canonical SPE-scored Hazard model — genuinely
// two different data sources on one page.
export default function HazardDashboardPage() {
  const { incidentId } = useSession();
  const [tab, setTab] = useState<Tab>("consolidated");
  const { data: workAssignments = [] } = useWorkAssignments(incidentId!);
  const { data: hazards = [], isLoading: hazardsLoading } = useHazards(incidentId!);

  if (!incidentId) return null;

  return (
    <div>
      <h2>Hazard Dashboard</h2>
      <div className="detail-tabs" style={{ marginBottom: 16 }}>
        <button className={`detail-tab ${tab === "consolidated" ? "active" : ""}`} onClick={() => setTab("consolidated")}>
          Consolidated
        </button>
        <button className={`detail-tab ${tab === "by-assignment" ? "active" : ""}`} onClick={() => setTab("by-assignment")}>
          By Assignment
        </button>
        <button className={`detail-tab ${tab === "register" ? "active" : ""}`} onClick={() => setTab("register")}>
          Register
        </button>
      </div>

      {tab === "consolidated" && <ConsolidatedView workAssignments={workAssignments} />}
      {tab === "by-assignment" && <ByAssignmentView workAssignments={workAssignments} />}
      {tab === "register" && <RegisterView incidentId={incidentId} hazards={hazards} isLoading={hazardsLoading} />}
    </div>
  );
}

type ConsolidatedRow = WorkAssignmentHazard & { assignments: string[] };

function ConsolidatedView({ workAssignments }: { workAssignments: WorkAssignment[] }) {
  const rows = useMemo<ConsolidatedRow[]>(() => {
    const byKey = new Map<string, ConsolidatedRow>();
    for (const wa of workAssignments) {
      const label = `${wa.assignment_number || wa.assignment_name}`.trim();
      for (const h of wa.hazards ?? []) {
        const key = String(h.hazard_type_id ?? h.hazard_type_text.toLowerCase());
        const existing = byKey.get(key);
        if (existing) {
          if (!existing.assignments.includes(label)) existing.assignments.push(label);
        } else {
          byKey.set(key, { ...h, assignments: [label] });
        }
      }
    }
    return Array.from(byKey.values());
  }, [workAssignments]);

  const columns: ColumnDef<ConsolidatedRow>[] = [
    { key: "hazard_type_text", header: "Hazard", sortable: true, sortValue: (r) => r.hazard_type_text, defaultWidth: 200 },
    { key: "category", header: "Category", defaultWidth: 130 },
    { key: "risk_level", header: "Risk", defaultWidth: 90 },
    { key: "likelihood", header: "Likelihood", defaultWidth: 100 },
    { key: "severity", header: "Severity", defaultWidth: 100 },
    { key: "control_measure", header: "Control Measure", defaultWidth: 220 },
    { key: "ppe_text", header: "PPE", defaultWidth: 140 },
    { key: "is_resolved", header: "Resolved", defaultWidth: 90, render: (r) => (r.is_resolved ? "Yes" : "No") },
    { key: "assignments", header: "Work Assignments", defaultWidth: 180, render: (r) => r.assignments.join(", ") },
  ];

  return (
    <DataTable
      tableId="hazard-dashboard-consolidated"
      columns={columns}
      rows={rows}
      rowKey={(r) => `${r.hazard_type_id ?? r.hazard_type_text}`}
      emptyMessage="No hazards recorded on any work assignment yet."
    />
  );
}

function ByAssignmentView({ workAssignments }: { workAssignments: WorkAssignment[] }) {
  const withHazards = workAssignments.filter((wa) => (wa.hazards ?? []).length > 0);
  const columns: ColumnDef<WorkAssignmentHazard>[] = [
    { key: "hazard_type_text", header: "Hazard", defaultWidth: 200 },
    { key: "category", header: "Category", defaultWidth: 130 },
    { key: "risk_level", header: "Risk", defaultWidth: 90 },
    { key: "likelihood", header: "Likelihood", defaultWidth: 100 },
    { key: "severity", header: "Severity", defaultWidth: 100 },
    { key: "control_measure", header: "Control Measure", defaultWidth: 220 },
    { key: "ppe_text", header: "PPE", defaultWidth: 140 },
    { key: "is_resolved", header: "Resolved", defaultWidth: 90, render: (r) => (r.is_resolved ? "Yes" : "No") },
  ];

  if (withHazards.length === 0) return <p className="muted">No work assignments have hazards recorded yet.</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {withHazards.map((wa) => (
        <div key={wa.id}>
          <h3>
            {wa.assignment_number} — {wa.assignment_name} <span className="muted">({wa.hazards.length} hazard{wa.hazards.length === 1 ? "" : "s"})</span>
          </h3>
          <DataTable tableId={`hazard-dashboard-wa-${wa.id}`} columns={columns} rows={wa.hazards} rowKey={(r) => r.id} emptyMessage="No hazards recorded." />
        </div>
      ))}
    </div>
  );
}

type HazardForm = {
  title: string;
  description: string;
  category: string;
  location_text: string;
  notes: string;
  controls: string;
  ppe: string;
  safety_language: string;
  severity: number;
  probability: number;
  exposure: number;
  residual_severity: number | "";
  residual_probability: number | "";
  residual_exposure: number | "";
};

const EMPTY_HAZARD_FORM: HazardForm = {
  title: "",
  description: "",
  category: "",
  location_text: "",
  notes: "",
  controls: "",
  ppe: "",
  safety_language: "",
  severity: 1,
  probability: 1,
  exposure: 1,
  residual_severity: "",
  residual_probability: "",
  residual_exposure: "",
};

function hazardToForm(h: Hazard): HazardForm {
  return {
    title: h.title,
    description: h.description,
    category: h.category,
    location_text: h.location_text,
    notes: h.notes,
    controls: h.controls.join(", "),
    ppe: h.ppe.join(", "),
    safety_language: h.safety_language,
    severity: h.default_spe?.severity ?? 1,
    probability: h.default_spe?.probability ?? 1,
    exposure: h.default_spe?.exposure ?? 1,
    residual_severity: h.spe_residual?.severity ?? "",
    residual_probability: h.spe_residual?.probability ?? "",
    residual_exposure: h.spe_residual?.exposure ?? "",
  };
}

function formToPayload(form: HazardForm): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    title: form.title,
    description: form.description,
    category: form.category,
    location_text: form.location_text,
    notes: form.notes,
    controls: form.controls.split(",").map((s) => s.trim()).filter(Boolean),
    ppe: form.ppe.split(",").map((s) => s.trim()).filter(Boolean),
    safety_language: form.safety_language,
    default_spe: { severity: form.severity, probability: form.probability, exposure: form.exposure },
  };
  if (form.residual_severity !== "" && form.residual_probability !== "" && form.residual_exposure !== "") {
    payload.spe_residual = { severity: form.residual_severity, probability: form.residual_probability, exposure: form.residual_exposure };
  }
  return payload;
}

function RegisterView({ incidentId, hazards, isLoading }: { incidentId: string; hazards: Hazard[]; isLoading: boolean }) {
  const createHazard = useCreateHazard(incidentId);
  const updateHazard = useUpdateHazard(incidentId);
  const deleteHazard = useDeleteHazard(incidentId);
  const [editing, setEditing] = useState<Hazard | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [form, setForm] = useState<HazardForm>(EMPTY_HAZARD_FORM);

  const highInitial = hazards.filter((h) => h.default_spe && (h.default_spe.band === "High" || h.default_spe.band === "Very High")).length;
  const highResidual = hazards.filter((h) => h.spe_residual && (h.spe_residual.band === "High" || h.spe_residual.band === "Very High")).length;
  const unlinked = hazards.filter((h) => h.work_assignment_ids.length === 0 && h.task_ids.length === 0 && h.team_ids.length === 0).length;

  const startAdd = () => {
    setForm(EMPTY_HAZARD_FORM);
    setIsNew(true);
    setEditing({} as Hazard);
  };
  const startEdit = (h: Hazard) => {
    setForm(hazardToForm(h));
    setIsNew(false);
    setEditing(h);
  };
  const cancel = () => setEditing(null);
  const save = () => {
    const payload = formToPayload(form);
    if (isNew) createHazard.mutate(payload, { onSuccess: cancel });
    else updateHazard.mutate({ hazardId: editing!.id, body: payload }, { onSuccess: cancel });
  };

  const columns: ColumnDef<Hazard>[] = [
    { key: "title", header: "Hazard", sortable: true, sortValue: (r) => r.title, defaultWidth: 200 },
    { key: "category", header: "Category", defaultWidth: 130 },
    {
      key: "default_spe",
      header: "Initial SPE",
      defaultWidth: 150,
      render: (r) => (r.default_spe ? <StatusPill domain="spe-band" statusKey={r.default_spe.band} label={`${r.default_spe.score} — ${r.default_spe.band}`} /> : "—"),
    },
    {
      key: "spe_residual",
      header: "Residual SPE",
      defaultWidth: 150,
      render: (r) => (r.spe_residual ? <StatusPill domain="spe-band" statusKey={r.spe_residual.band} label={`${r.spe_residual.score} — ${r.spe_residual.band}`} /> : "Not assessed"),
    },
    { key: "op_period_ids", header: "Op Periods", defaultWidth: 100, render: (r) => r.op_period_ids.join(", ") || "—" },
    {
      key: "linked",
      header: "Linked Items",
      defaultWidth: 100,
      render: (r) => r.work_assignment_ids.length + r.task_ids.length + r.team_ids.length,
    },
    { key: "hazard_zone_ids", header: "Hazard Zones", defaultWidth: 100, render: (r) => r.hazard_zone_ids.length },
    { key: "updated_at", header: "Updated", defaultWidth: 150 },
    {
      key: "_actions",
      header: "",
      defaultWidth: 110,
      render: (r) => (
        <span style={{ display: "flex", gap: 6 }}>
          <button type="button" className="secondary" style={{ width: "auto", padding: "2px 8px" }} onClick={() => startEdit(r)}>
            Edit
          </button>
          <button type="button" className="secondary" style={{ width: "auto", padding: "2px 8px" }} onClick={() => deleteHazard.mutate(r.id)}>
            Remove
          </button>
        </span>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 16 }}>
        <div className="planning-panel"><h3 style={{ margin: 0 }}>{hazards.length}</h3><p className="muted">Total Hazards</p></div>
        <div className="planning-panel"><h3 style={{ margin: 0 }}>{highInitial}</h3><p className="muted">High Initial SPE</p></div>
        <div className="planning-panel"><h3 style={{ margin: 0 }}>{highResidual}</h3><p className="muted">High Residual SPE</p></div>
        <div className="planning-panel"><h3 style={{ margin: 0 }}>{unlinked}</h3><p className="muted">Unlinked Hazards</p></div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <button type="button" style={{ width: "auto" }} onClick={startAdd}>
          + Add Hazard
        </button>
      </div>

      {editing !== null && (
        <div className="detail-header" style={{ marginBottom: 16 }}>
          <div className="field"><label>Title</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div className="field"><label>Category</label><input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></div>
          <div className="field"><label>Location</label><input value={form.location_text} onChange={(e) => setForm({ ...form, location_text: e.target.value })} /></div>
          <div className="field" style={{ gridColumn: "1 / -1" }}><label>Description</label><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div className="field"><label>Initial Severity (1–5)</label><input type="number" min={1} max={5} value={form.severity} onChange={(e) => setForm({ ...form, severity: Number(e.target.value) })} /></div>
          <div className="field"><label>Initial Probability (1–5)</label><input type="number" min={1} max={5} value={form.probability} onChange={(e) => setForm({ ...form, probability: Number(e.target.value) })} /></div>
          <div className="field"><label>Initial Exposure (1–4)</label><input type="number" min={1} max={4} value={form.exposure} onChange={(e) => setForm({ ...form, exposure: Number(e.target.value) })} /></div>
          <div className="field"><label>Residual Severity (1–5, optional)</label><input type="number" min={1} max={5} value={form.residual_severity} onChange={(e) => setForm({ ...form, residual_severity: e.target.value === "" ? "" : Number(e.target.value) })} /></div>
          <div className="field"><label>Residual Probability (1–5, optional)</label><input type="number" min={1} max={5} value={form.residual_probability} onChange={(e) => setForm({ ...form, residual_probability: e.target.value === "" ? "" : Number(e.target.value) })} /></div>
          <div className="field"><label>Residual Exposure (1–4, optional)</label><input type="number" min={1} max={4} value={form.residual_exposure} onChange={(e) => setForm({ ...form, residual_exposure: e.target.value === "" ? "" : Number(e.target.value) })} /></div>
          <div className="field"><label>Controls (comma-separated)</label><input value={form.controls} onChange={(e) => setForm({ ...form, controls: e.target.value })} /></div>
          <div className="field"><label>PPE (comma-separated)</label><input value={form.ppe} onChange={(e) => setForm({ ...form, ppe: e.target.value })} /></div>
          <div className="field" style={{ gridColumn: "1 / -1" }}><label>Standard Safety Language</label><textarea value={form.safety_language} onChange={(e) => setForm({ ...form, safety_language: e.target.value })} /></div>
          <div className="field" style={{ gridColumn: "1 / -1" }}><label>Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" style={{ width: "auto" }} onClick={save} disabled={!form.title || !form.category}>
              Save
            </button>
            <button type="button" className="secondary" style={{ width: "auto" }} onClick={cancel}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? <p>Loading…</p> : <DataTable tableId="hazard-dashboard-register" columns={columns} rows={hazards} rowKey={(r) => r.id} emptyMessage="No hazards in the register yet." />}
    </div>
  );
}
