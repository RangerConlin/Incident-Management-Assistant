import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "../../auth/SessionContext";
import { searchPersonnel } from "../../api/endpoints";
import type { OrgPosition } from "../../api/types";
import { useOperationalPeriods } from "../planning/operationalPeriods/hooks";
import { useDownloadForm } from "../forms/hooks";
import { useOrg, useOrgWrites } from "./hooks";
import OperationsSectionModal from "./OperationsSectionModal";
import "./command.css";

const FIXED = new Set([
  "Incident Commander", "Safety Officer", "Public Information Officer", "Liaison Officer",
  "Operations Section Chief", "Planning Section Chief", "Logistics Section Chief", "Finance/Administration Section Chief",
]);
const CLASSIFICATIONS = ["branch", "division", "group", "unit", "staging_area"];
const ASSIGNMENT_TYPES = ["primary", "deputy", "assistant", "staff_assistant", "trainee"];
const SPAN_OF_CONTROL_LIMIT = 7;
const SECTION_FILTERS: { key: string; label: string }[] = [
  { key: "all", label: "All sections" },
  { key: "command", label: "Command Staff" },
  { key: "operations", label: "Operations" },
  { key: "planning", label: "Planning" },
  { key: "logistics", label: "Logistics" },
  { key: "finance", label: "Finance/Admin" },
];

// Approximate bucketing by walking up the parent chain looking for a
// section-chief-shaped title — there's no real "section" field on a
// position, just title/classification, same as desktop.
function sectionBucket(position: OrgPosition, byId: Map<number, OrgPosition>): string {
  let current: OrgPosition | undefined = position;
  const seen = new Set<number>();
  while (current && !seen.has(current.position_id)) {
    seen.add(current.position_id);
    const t = current.title.toLowerCase();
    if (t.includes("operations")) return "operations";
    if (t.includes("planning")) return "planning";
    if (t.includes("logistics")) return "logistics";
    if (t.includes("finance")) return "finance";
    if (["incident commander", "safety officer", "public information officer", "liaison officer"].includes(t)) return "command";
    current = current.parent_position_id != null ? byId.get(current.parent_position_id) : undefined;
  }
  return "other";
}

function WarnIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
      <path d="M12 9v4" /><path d="M12 17h.01" /><path d="m10.3 3.9-8 14A1 1 0 0 0 3.2 19.5h17.6a1 1 0 0 0 .87-1.6l-8-14a1 1 0 0 0-1.74 0Z" />
    </svg>
  );
}

export default function IncidentOrganizationPage() {
  const { incidentId, user } = useSession();
  const id = incidentId!;
  const query = useOrg(id);
  const writes = useOrgWrites(id);
  const periods = useOperationalPeriods(id);
  const download = useDownloadForm(id);

  const [selected, setSelected] = useState<number | null>(null);
  const [sectionFilter, setSectionFilter] = useState("all");
  const [showAddForm, setShowAddForm] = useState(false);
  const [title, setTitle] = useState("");
  const [classification, setClassification] = useState("division");
  const [parent, setParent] = useState("");
  const [template, setTemplate] = useState("");
  const [personSearch, setPersonSearch] = useState("");
  const [person, setPerson] = useState("");
  const [atype, setAtype] = useState("primary");
  const [exportPeriod, setExportPeriod] = useState("");
  const [message, setMessage] = useState("");
  const [showOpsModal, setShowOpsModal] = useState(false);

  const people = useQuery({
    queryKey: ["master", "personnel", personSearch],
    queryFn: () => searchPersonnel(personSearch),
    enabled: personSearch.length > 1,
  });

  const positions = query.data?.positions ?? [];
  const assignments = query.data?.assignments ?? [];

  const byId = useMemo(() => new Map(positions.map((p) => [p.position_id, p])), [positions]);
  const childrenOf = useMemo(() => {
    const map = new Map<number | null, OrgPosition[]>();
    for (const p of positions) {
      const key = p.parent_position_id;
      const list = map.get(key) ?? [];
      list.push(p);
      map.set(key, list);
    }
    for (const list of map.values()) list.sort((a, b) => a.sort_order - b.sort_order || a.title.localeCompare(b.title));
    return map;
  }, [positions]);
  const directReportCount = useMemo(() => {
    const counts = new Map<number, number>();
    for (const p of positions) {
      if (p.parent_position_id != null) counts.set(p.parent_position_id, (counts.get(p.parent_position_id) ?? 0) + 1);
    }
    return counts;
  }, [positions]);
  const rows = useMemo(() => {
    const out: { position: OrgPosition; depth: number }[] = [];
    const visit = (parentId: number | null, depth: number) => {
      for (const p of childrenOf.get(parentId) ?? []) {
        if (sectionFilter === "all" || sectionBucket(p, byId) === sectionFilter) out.push({ position: p, depth });
        visit(p.position_id, depth + 1);
      }
    };
    visit(null, 0);
    return out;
  }, [childrenOf, sectionFilter, byId]);

  const selectedPosition = positions.find((p) => p.position_id === selected);
  const selectedAssignments = assignments.filter((a) => a.position_id === selected);
  const selectedSpan = selectedPosition ? directReportCount.get(selectedPosition.position_id) ?? 0 : 0;

  if (query.isPending) return <p>Loading incident organization…</p>;
  if (query.isError) return <p className="error">Could not load incident organization.</p>;

  return (
    <div className="command-page">
      <div className="command-heading">
        <div>
          <h2>Incident Organization</h2>
          <p>Build the ICS-203 structure and staff active positions.</p>
        </div>
      </div>

      <div className="quick-chip-row">
        {SECTION_FILTERS.map((f) => (
          <button key={f.key} type="button" className={"quick-chip" + (sectionFilter === f.key ? " active" : "")} onClick={() => setSectionFilter(f.key)}>
            {f.label}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", margin: "12px 0" }}>
        <select aria-label="Organization template" value={template} onChange={(e) => setTemplate(e.target.value)}>
          <option value="">Choose a template</option>
          {query.data?.templates.map((t) => (
            <option key={t.template_id} value={t.template_id}>{t.name}</option>
          ))}
        </select>
        <button
          className="secondary"
          style={{ width: "auto" }}
          type="button"
          disabled={!template || writes.apply.isPending}
          onClick={async () => {
            const t = query.data?.templates.find((x) => String(x.template_id) === template);
            if (t) {
              await writes.apply.mutateAsync(t.payload);
              setMessage("Organization template applied.");
            }
          }}
        >
          Apply template
        </button>
        <select aria-label="Export operational period" value={exportPeriod} onChange={(e) => setExportPeriod(e.target.value)}>
          <option value="">Current org (no period)</option>
          {periods.data?.map((p) => (
            <option key={p.id} value={p.id}>OP {p.number} — {p.name}</option>
          ))}
        </select>
        <button
          className="secondary"
          style={{ width: "auto" }}
          type="button"
          disabled={download.isPending}
          onClick={() => {
            download.mutate(
              {
                form_id: "ics_203",
                ...(exportPeriod ? { operational_period_id: Number(exportPeriod) } : {}),
                prepared_by: user?.display_name || user?.username || "",
              },
              {
                onSuccess: (result) => {
                  const url = URL.createObjectURL(result.blob);
                  const anchor = document.createElement("a");
                  anchor.href = url;
                  anchor.download = result.filename;
                  document.body.appendChild(anchor);
                  anchor.click();
                  anchor.remove();
                  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
                },
              }
            );
          }}
        >
          {download.isPending ? "Exporting…" : "Export ICS-203"}
        </button>
        <button className="secondary" style={{ width: "auto" }} type="button" disabled title="Not built yet — no ics_207 export is registered server-side.">
          Prepare ICS-207
        </button>
        <button className="secondary" style={{ width: "auto" }} type="button" onClick={() => setShowAddForm((v) => !v)}>
          {showAddForm ? "Cancel" : "+ Add Position"}
        </button>
      </div>
      {message && <p role="status">{message}</p>}
      {download.error && <p className="error" role="alert">{download.error.message}</p>}

      {showAddForm && (
        <section className="command-panel">
          <h3>Create custom organization node</h3>
          <form
            className="command-form"
            onSubmit={async (e) => {
              e.preventDefault();
              await writes.position.mutateAsync({ title, classification, parent_position_id: parent ? Number(parent) : null });
              setTitle("");
              setShowAddForm(false);
              setMessage("Organization node created.");
            }}
          >
            <label>Title<input required value={title} onChange={(e) => setTitle(e.target.value)} /></label>
            <label>
              Classification
              <select value={classification} onChange={(e) => setClassification(e.target.value)}>
                {CLASSIFICATIONS.map((v) => (
                  <option key={v} value={v}>{v.replaceAll("_", " ")}</option>
                ))}
              </select>
            </label>
            <label>
              Reports to
              <select value={parent} onChange={(e) => setParent(e.target.value)}>
                <option value="">Top level</option>
                {positions.map((p) => (
                  <option key={p.position_id} value={p.position_id}>{p.title}</option>
                ))}
              </select>
            </label>
            <div><button disabled={writes.position.isPending}>Create node</button></div>
          </form>
        </section>
      )}

      <div className="org-layout">
        <div className="org-tree-panel">
          <h3>Organization chart</h3>
          {rows.length === 0 ? (
            <p className="org-assign-empty">No organization exists yet. Apply a template or add a custom position.</p>
          ) : (
            rows.map(({ position, depth }) => {
              const primaryAssignment = assignments.find((a) => a.position_id === position.position_id && a.assignment_type === "primary");
              const span = directReportCount.get(position.position_id) ?? 0;
              return (
                <div
                  key={position.position_id}
                  className={"org-node" + (selected === position.position_id ? " selected" : "")}
                  style={{ paddingLeft: 10 + depth * 20 }}
                  onClick={() => setSelected(position.position_id)}
                >
                  <span className="org-node-title">{position.title}</span>
                  <span className={"org-node-assign" + (primaryAssignment ? "" : " vacant")}>
                    {primaryAssignment ? primaryAssignment.person_name : "Vacant"}
                  </span>
                  {span > SPAN_OF_CONTROL_LIMIT && (
                    <span className="org-warn-dot" title={`Span of control: ${span} direct reports (limit ${SPAN_OF_CONTROL_LIMIT})`} />
                  )}
                </div>
              );
            })
          )}
        </div>

        {selectedPosition ? (
          <div className="org-detail-panel">
            <div className="org-detail-head">
              <h4>{selectedPosition.title}</h4>
              <span className="org-tag">{selectedPosition.classification.replaceAll("_", " ")}</span>
            </div>
            <div className="org-detail-meta">
              {FIXED.has(selectedPosition.title) ? "Fixed ICS role" : "Custom position"} · Reports to:{" "}
              {byId.get(selectedPosition.parent_position_id ?? -1)?.title ?? "—"}
              {!FIXED.has(selectedPosition.title) && (
                <>
                  {" · "}
                  <button
                    className="link-button"
                    onClick={() => {
                      if (confirm(`Delete ${selectedPosition.title}?`)) {
                        writes.remove.mutate(selectedPosition.position_id, { onSuccess: () => setSelected(null) });
                      }
                    }}
                  >
                    Delete
                  </button>
                </>
              )}
            </div>

            {selectedPosition.title === "Operations Section Chief" && (
              <button className="secondary" style={{ width: "auto", marginBottom: 12 }} type="button" onClick={() => setShowOpsModal(true)}>
                Open Operations Section →
              </button>
            )}

            {selectedSpan > SPAN_OF_CONTROL_LIMIT && (
              <div className="org-warning-strip">
                <WarnIcon />
                <span>
                  Span of control: {selectedSpan} direct reports (limit {SPAN_OF_CONTROL_LIMIT}). Consider delegating via a deputy or splitting a function off to its own position.
                </span>
              </div>
            )}

            {!FIXED.has(selectedPosition.title) && (
              <div className="field" style={{ maxWidth: 260 }}>
                <label htmlFor="org-move">Reports to</label>
                <select
                  id="org-move"
                  value={selectedPosition.parent_position_id ?? ""}
                  onChange={(e) =>
                    writes.move.mutate({
                      positionId: selectedPosition.position_id,
                      parentPositionId: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                >
                  <option value="">Top level</option>
                  {positions.filter((p) => p.position_id !== selectedPosition.position_id).map((p) => (
                    <option key={p.position_id} value={p.position_id}>{p.title}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="org-section-label">Assignments</div>
            {selectedAssignments.length === 0 ? (
              <p className="org-assign-empty">No one currently assigned.</p>
            ) : (
              <table className="org-assign-table">
                <thead><tr><th>Name</th><th>Type</th><th></th></tr></thead>
                <tbody>
                  {selectedAssignments.map((a) => (
                    <tr key={a.assignment_id}>
                      <td>{a.person_name}</td>
                      <td><span className="org-tag">{a.assignment_type.replaceAll("_", " ")}</span></td>
                      <td><button className="secondary" style={{ width: "auto" }} type="button" onClick={() => writes.end.mutate(a.assignment_id)}>End</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <div className="org-section-label">Assign personnel</div>
            <form
              className="org-assign-form"
              onSubmit={async (e) => {
                e.preventDefault();
                await writes.assign.mutateAsync({ position_id: selectedPosition.position_id, person_record: Number(person), assignment_type: atype });
                setPerson("");
                setPersonSearch("");
              }}
            >
              <div className="field">
                <label htmlFor="org-person-search">Personnel</label>
                <input id="org-person-search" type="search" value={personSearch} onChange={(e) => setPersonSearch(e.target.value)} placeholder="Search checked-in personnel…" />
              </div>
              {people.data && (
                <div className="field">
                  <label htmlFor="org-person-select">Match</label>
                  <select id="org-person-select" required value={person} onChange={(e) => setPerson(e.target.value)}>
                    <option value="">Select person</option>
                    {people.data.map((p) => (
                      <option key={p.person_record} value={p.person_record}>{p.name} · {p.person_id}</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="field">
                <label htmlFor="org-assign-type">Type</label>
                <select id="org-assign-type" value={atype} onChange={(e) => setAtype(e.target.value)}>
                  {ASSIGNMENT_TYPES.map((v) => (
                    <option key={v} value={v}>{v.replaceAll("_", " ")}</option>
                  ))}
                </select>
              </div>
              <button style={{ width: "auto" }} type="submit" disabled={!person || writes.assign.isPending}>Assign</button>
            </form>
          </div>
        ) : (
          <div className="org-detail-panel"><p className="org-assign-empty">Select a position to view its details.</p></div>
        )}
      </div>

      {showOpsModal && <OperationsSectionModal onClose={() => setShowOpsModal(false)} />}
    </div>
  );
}
