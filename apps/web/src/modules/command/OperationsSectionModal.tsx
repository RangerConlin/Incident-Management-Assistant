import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "../../auth/SessionContext";
import { listResourceTypes, listTeams, searchPersonnel, updateTeam } from "../../api/endpoints";
import type { OrgPosition } from "../../api/types";
import { useOrg, useOrgWrites } from "./hooks";

const CLASSIFICATIONS = ["branch", "division", "group", "unit", "staging_area"];
const ASSIGNMENT_TYPES = ["primary", "deputy", "assistant", "staff_assistant", "trainee"];
const ICS_TYPES = ["single_resource", "task_force", "strike_team"];

// Operations Section sub-view — a modal opened from Incident Organization's
// Operations Section Chief node, scoped to just that subtree. Matches
// desktop's dedicated ops_section_window.py in scope: same org
// structure/personnel CRUD as the main page, plus the resource-assignment
// pieces only this window has (teams assigned to a branch/division, ICS
// resource type, and a resource-kind pulldown sourced from the master
// resource-type catalog).
export default function OperationsSectionModal({ onClose }: { onClose: () => void }) {
  const { incidentId } = useSession();
  const id = incidentId!;
  const queryClient = useQueryClient();

  const query = useOrg(id);
  const writes = useOrgWrites(id);
  const teams = useQuery({
    queryKey: ["incident", id, "operations_teams_detail"],
    queryFn: () => listTeams(id),
    refetchInterval: 20_000,
  });
  const resourceTypes = useQuery({
    queryKey: ["master", "resource_types"],
    queryFn: () => listResourceTypes(),
    refetchInterval: 60_000,
  });
  const assignTeam = useMutation({
    mutationFn: (v: { teamId: number; unitId: number | null; icsType?: string; resourceKind?: string }) =>
      updateTeam(id, v.teamId, {
        operational_unit_id: v.unitId,
        ics_resource_kind: v.icsType ?? null,
        resource_kind: v.resourceKind ?? null,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["incident", id, "operations_teams_detail"] }),
  });

  const positions = query.data?.positions ?? [];
  const assignments = query.data?.assignments ?? [];
  const allTeams = teams.data ?? [];

  const byId = useMemo(() => new Map(positions.map((p) => [p.position_id, p])), [positions]);
  const childrenOf = useMemo(() => {
    const map = new Map<number | null, OrgPosition[]>();
    for (const p of positions) {
      const list = map.get(p.parent_position_id) ?? [];
      list.push(p);
      map.set(p.parent_position_id, list);
    }
    for (const list of map.values()) list.sort((a, b) => a.sort_order - b.sort_order || a.title.localeCompare(b.title));
    return map;
  }, [positions]);

  const root = positions.find((p) => p.title === "Operations Section Chief");
  const rows = useMemo(() => {
    if (!root) return [];
    const out: { position: OrgPosition; depth: number }[] = [{ position: root, depth: 0 }];
    const visit = (parentId: number, depth: number) => {
      for (const p of childrenOf.get(parentId) ?? []) {
        out.push({ position: p, depth });
        visit(p.position_id, depth + 1);
      }
    };
    visit(root.position_id, 1);
    return out;
  }, [root, childrenOf]);

  const [selected, setSelected] = useState<number | null>(null);
  useEffect(() => {
    if (selected === null && root) setSelected(root.position_id);
  }, [root, selected]);

  const [showAddForm, setShowAddForm] = useState(false);
  const [title, setTitle] = useState("");
  const [classification, setClassification] = useState("branch");
  const [personSearch, setPersonSearch] = useState("");
  const [person, setPerson] = useState("");
  const [atype, setAtype] = useState("primary");
  const [teamSel, setTeamSel] = useState("");
  const [icsType, setIcsType] = useState(ICS_TYPES[0]);
  const [resourceKind, setResourceKind] = useState("");

  const people = useQuery({
    queryKey: ["master", "personnel", personSearch],
    queryFn: () => searchPersonnel(personSearch),
    enabled: personSearch.length > 1,
  });

  const selectedPosition = positions.find((p) => p.position_id === selected);
  const selectedAssignments = assignments.filter((a) => a.position_id === selected);
  const assignedResources = allTeams.filter((t) => String(t.operational_unit_id ?? "") === String(selected ?? ""));
  const candidateResources = allTeams.filter((t) => String(t.operational_unit_id ?? "") !== String(selected ?? ""));

  if (!root) {
    return (
      <div className="ops-modal-backdrop" onClick={onClose}>
        <div className="ops-modal" onClick={(e) => e.stopPropagation()}>
          <div className="ops-modal-head">
            <div><h3>Operations Section</h3></div>
            <button className="ops-modal-close" type="button" onClick={onClose} aria-label="Close">×</button>
          </div>
          <div className="ops-modal-body">
            <p className="org-assign-empty">No Operations Section Chief position exists yet. Apply a template or add it from the main Incident Organization page first.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="ops-modal-backdrop" onClick={onClose}>
      <div className="ops-modal" onClick={(e) => e.stopPropagation()}>
        <div className="ops-modal-head">
          <div>
            <h3>Operations Section</h3>
            <div className="sub">Branches, divisions/groups, and resource assignment — scoped to this section only.</div>
          </div>
          <button className="ops-modal-close" type="button" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="ops-modal-toolbar">
          <button className="secondary" style={{ width: "auto" }} type="button" onClick={() => { setClassification("branch"); setShowAddForm((v) => !v); }}>
            {showAddForm ? "Cancel" : "+ Add Position"}
          </button>
        </div>

        {showAddForm && (
          <div style={{ padding: "0 20px 14px" }}>
            <form
              className="command-form"
              onSubmit={async (e) => {
                e.preventDefault();
                await writes.position.mutateAsync({ title, classification, parent_position_id: selected ?? root.position_id });
                setTitle("");
                setShowAddForm(false);
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
              <div><button disabled={writes.position.isPending}>Create under {selectedPosition?.title ?? root.title}</button></div>
            </form>
          </div>
        )}

        <div className="ops-modal-body">
          <div className="org-tree-panel">
            <h3>Operations Section</h3>
            {rows.map(({ position, depth }) => {
              const primaryAssignment = assignments.find((a) => a.position_id === position.position_id && a.assignment_type === "primary");
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
                </div>
              );
            })}
          </div>

          {selectedPosition && (
            <div className="org-detail-panel">
              <div className="org-detail-head">
                <h4>{selectedPosition.title}</h4>
                <span className="org-tag">{selectedPosition.classification.replaceAll("_", " ")}</span>
              </div>
              <div className="org-detail-meta">
                Reports to: {byId.get(selectedPosition.parent_position_id ?? -1)?.title ?? "—"}
                {selectedPosition.position_id !== root.position_id && (
                  <>
                    {" · "}
                    <button
                      className="link-button"
                      onClick={() => {
                        if (confirm(`Delete ${selectedPosition.title}?`)) {
                          writes.remove.mutate(selectedPosition.position_id, { onSuccess: () => setSelected(root.position_id) });
                        }
                      }}
                    >
                      Delete
                    </button>
                  </>
                )}
              </div>

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
                  <label htmlFor="ops-person-search">Personnel</label>
                  <input id="ops-person-search" type="search" value={personSearch} onChange={(e) => setPersonSearch(e.target.value)} placeholder="Search checked-in personnel…" />
                </div>
                {people.data && (
                  <div className="field">
                    <label htmlFor="ops-person-select">Match</label>
                    <select id="ops-person-select" required value={person} onChange={(e) => setPerson(e.target.value)}>
                      <option value="">Select person</option>
                      {people.data.map((p) => (
                        <option key={p.person_record} value={p.person_record}>{p.name} · {p.person_id}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="field">
                  <label htmlFor="ops-assign-type">Type</label>
                  <select id="ops-assign-type" value={atype} onChange={(e) => setAtype(e.target.value)}>
                    {ASSIGNMENT_TYPES.map((v) => (
                      <option key={v} value={v}>{v.replaceAll("_", " ")}</option>
                    ))}
                  </select>
                </div>
                <button style={{ width: "auto" }} type="submit" disabled={!person || writes.assign.isPending}>Assign</button>
              </form>

              <div className="org-section-label">Assigned resources</div>
              {teams.isPending ? (
                <p className="org-assign-empty">Loading…</p>
              ) : assignedResources.length === 0 ? (
                <p className="org-assign-empty">No resources assigned.</p>
              ) : (
                <table className="org-assign-table">
                  <thead><tr><th>Name</th><th>ICS type</th><th>Resource kind</th><th>Status</th><th></th></tr></thead>
                  <tbody>
                    {assignedResources.map((t) => (
                      <tr key={t.int_id}>
                        <td>{t.name}</td>
                        <td>{t.ics_resource_kind ? t.ics_resource_kind.replaceAll("_", " ") : "—"}</td>
                        <td>{t.resource_kind || "—"}</td>
                        <td>{t.status}</td>
                        <td>
                          <button
                            className="secondary"
                            style={{ width: "auto" }}
                            type="button"
                            disabled={assignTeam.isPending}
                            onClick={() => assignTeam.mutate({ teamId: t.int_id, unitId: null })}
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <div className="org-section-label">Assign resource</div>
              <div className="ops-resource-form">
                <div className="field">
                  <label htmlFor="ops-res-team">Team</label>
                  <select id="ops-res-team" value={teamSel} onChange={(e) => setTeamSel(e.target.value)}>
                    <option value="">Select team</option>
                    {candidateResources.map((t) => (
                      <option key={t.int_id} value={t.int_id}>{t.name}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="ops-res-type">ICS type</label>
                  <select id="ops-res-type" value={icsType} onChange={(e) => setIcsType(e.target.value)}>
                    {ICS_TYPES.map((v) => (
                      <option key={v} value={v}>{v.replaceAll("_", " ")}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="ops-res-kind">Resource kind</label>
                  <select id="ops-res-kind" value={resourceKind} onChange={(e) => setResourceKind(e.target.value)}>
                    <option value="">Not specified</option>
                    {resourceTypes.data?.map((rt) => (
                      <option key={rt.id ?? rt.name} value={rt.name}>{rt.name}</option>
                    ))}
                  </select>
                </div>
                <button
                  className="secondary"
                  style={{ width: "auto" }}
                  type="button"
                  disabled={!teamSel || assignTeam.isPending}
                  onClick={() => {
                    assignTeam.mutate(
                      { teamId: Number(teamSel), unitId: selectedPosition.position_id, icsType, resourceKind: resourceKind || undefined },
                      { onSuccess: () => setTeamSel("") }
                    );
                  }}
                >
                  Assign
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
