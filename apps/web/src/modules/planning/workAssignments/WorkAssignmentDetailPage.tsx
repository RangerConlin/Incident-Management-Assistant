import FormExportControls from "../../forms/FormExportControls";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { WA_PLANNING_STATUSES, WA_RESOURCE_STATUSES, WA_SAFETY_STATUSES } from "../../../api/endpoints";
import { useSession } from "../../../auth/SessionContext";
import {
  useAddWorkAssignmentResource,
  useAssignWorkAssignmentResource,
  useLinkWorkAssignmentTask,
  useRemoveWorkAssignmentAssignment,
  useRemoveWorkAssignmentResource,
  useUnlinkWorkAssignmentTask,
  useUpdateWorkAssignment,
  useWorkAssignmentDetail,
} from "./hooks";

type Tab = "overview" | "resources" | "tasks";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "resources", label: "Resources" },
  { key: "tasks", label: "Linked Tasks" },
];

export default function WorkAssignmentDetailPage() {
  const { waId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [newResourceType, setNewResourceType] = useState("");
  const [newResourceQty, setNewResourceQty] = useState("1");
  const [taskIdInput, setTaskIdInput] = useState("");

  const id = Number(waId);
  const { data: wa, isLoading, error } = useWorkAssignmentDetail(incidentId!, id);
  const updateWA = useUpdateWorkAssignment(incidentId!);
  const addResource = useAddWorkAssignmentResource(incidentId!, id);
  const removeResource = useRemoveWorkAssignmentResource(incidentId!, id);
  const assignResource = useAssignWorkAssignmentResource(incidentId!, id);
  const removeAssignment = useRemoveWorkAssignmentAssignment(incidentId!, id);
  const linkTask = useLinkWorkAssignmentTask(incidentId!, id);
  const unlinkTask = useUnlinkWorkAssignmentTask(incidentId!, id);

  if (!incidentId) return null;
  if (isLoading) return <p>Loading work assignment…</p>;
  if (error || !wa) return <p className="error">Could not load this work assignment.</p>;

  const save = (body: Record<string, unknown>) =>
    updateWA.mutate({ waId: id, body: { ...body, updated_by: user?.username } });

  return (
    <div className="detail-page">
      <FormExportControls formIds={["ics_204", "ics_215", "ics_215a"]} sourceId={waId} />
      <button
        className="secondary"
        style={{ width: "auto", marginBottom: 12 }}
        onClick={() => navigate("/planning/work-assignments")}
      >
        ← Work Assignments
      </button>
      <h2>
        {wa.assignment_number} — {wa.assignment_name || "Untitled"}
      </h2>

      <div className="detail-tabs">
        {TABS.map((t) => (
          <button key={t.key} className={`detail-tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label} {t.key === "resources" && `(${wa.resources.length})`}
            {t.key === "tasks" && `(${wa.task_links.length})`}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="detail-header">
          <div className="field">
            <label htmlFor="wa-name">Assignment Name</label>
            <input
              id="wa-name"
              defaultValue={wa.assignment_name}
              onBlur={(e) => save({ assignment_name: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Priority</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <StatusPill domain="objective-priority" statusKey={wa.priority} />
              <select value={wa.priority} onChange={(e) => save({ priority: e.target.value })}>
                <option value="Low">Low</option>
                <option value="Normal">Normal</option>
                <option value="High">High</option>
                <option value="Urgent">Urgent</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="wa-planning-status">Planning Status</label>
            <select
              id="wa-planning-status"
              value={wa.planning_status}
              onChange={(e) => save({ planning_status: e.target.value })}
            >
              {WA_PLANNING_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="wa-safety-status">Safety Status</label>
            <select
              id="wa-safety-status"
              value={wa.safety_status}
              onChange={(e) => save({ safety_status: e.target.value })}
            >
              {WA_SAFETY_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="wa-resource-status">Resource Status</label>
            <select
              id="wa-resource-status"
              value={wa.resource_status}
              onChange={(e) => save({ resource_status: e.target.value })}
            >
              {WA_RESOURCE_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="wa-branch">Branch</label>
            <input id="wa-branch" defaultValue={wa.branch} onBlur={(e) => save({ branch: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="wa-division">Division/Group</label>
            <input
              id="wa-division"
              defaultValue={wa.division_group}
              onBlur={(e) => save({ division_group: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="wa-location">Location</label>
            <input id="wa-location" defaultValue={wa.location} onBlur={(e) => save({ location: e.target.value })} />
          </div>
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="wa-description">Description</label>
            <textarea
              id="wa-description"
              defaultValue={wa.description}
              onBlur={(e) => save({ description: e.target.value })}
            />
          </div>
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="wa-tactics">Tactics Summary</label>
            <textarea
              id="wa-tactics"
              defaultValue={wa.tactics_summary}
              onBlur={(e) => save({ tactics_summary: e.target.value })}
            />
          </div>
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="wa-special">Special Instructions</label>
            <textarea
              id="wa-special"
              defaultValue={wa.special_instructions}
              onBlur={(e) => save({ special_instructions: e.target.value })}
            />
          </div>
        </div>
      )}

      {tab === "resources" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              style={{ maxWidth: 220 }}
              placeholder="Resource type (e.g. Ground Team)"
              value={newResourceType}
              onChange={(e) => setNewResourceType(e.target.value)}
            />
            <input
              type="number"
              min={1}
              style={{ maxWidth: 90 }}
              value={newResourceQty}
              onChange={(e) => setNewResourceQty(e.target.value)}
            />
            <button
              style={{ width: "auto" }}
              disabled={!newResourceType.trim() || addResource.isPending}
              onClick={() =>
                addResource.mutate(
                  { resource_type_text: newResourceType.trim(), quantity_required: Number(newResourceQty) || 1 },
                  { onSuccess: () => setNewResourceType("") }
                )
              }
            >
              Add Requirement
            </button>
          </div>

          {wa.resources.length === 0 ? (
            <p style={{ opacity: 0.6 }}>No resource requirements yet.</p>
          ) : (
            wa.resources.map((r) => (
              <div key={r.id} style={{ marginBottom: 16, borderBottom: "1px solid #2a2d33", paddingBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <strong>{r.resource_type_text || "Resource"}</strong>{" "}
                    <span style={{ opacity: 0.7, fontSize: "0.85rem" }}>
                      {r.quantity_assigned}/{r.quantity_required} filled
                      {r.quantity_gap > 0 && ` · gap ${r.quantity_gap}`}
                    </span>
                  </div>
                  <button className="secondary" style={{ width: "auto" }} onClick={() => removeResource.mutate(r.id)}>
                    Remove Requirement
                  </button>
                </div>
                <div style={{ marginTop: 8, marginLeft: 12 }}>
                  {r.assignments.map((a) => (
                    <div key={a.id} className="list-item" style={{ cursor: "default" }}>
                      <div>
                        <div style={{ fontWeight: 600 }}>{a.display_name || a.resource_id}</div>
                        <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                          {a.resource_kind} · {a.status}
                        </div>
                      </div>
                      <button
                        className="secondary"
                        style={{ width: "auto" }}
                        onClick={() => removeAssignment.mutate({ reqId: r.id, assignmentId: a.id })}
                      >
                        Unassign
                      </button>
                    </div>
                  ))}
                  <AssignResourceForm onAssign={(body) => assignResource.mutate({ reqId: r.id, body })} />
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "tasks" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              style={{ maxWidth: 200 }}
              placeholder="Task ID (numeric)"
              value={taskIdInput}
              onChange={(e) => setTaskIdInput(e.target.value)}
            />
            <button
              style={{ width: "auto" }}
              disabled={!taskIdInput.trim() || linkTask.isPending}
              onClick={() => {
                const taskId = Number(taskIdInput);
                if (!Number.isFinite(taskId)) return;
                linkTask.mutate({ task_id: taskId }, { onSuccess: () => setTaskIdInput("") });
              }}
            >
              Link Task
            </button>
          </div>
          {wa.task_links.length === 0 ? (
            <p style={{ opacity: 0.6 }}>No tasks linked yet.</p>
          ) : (
            wa.task_links.map((link) => (
              <div key={link.id} className="list-item" style={{ cursor: "default" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    <a href={`#/ops/tasks/${link.task_id}`}>Task #{link.task_id}</a>
                  </div>
                  <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                    {link.link_type} · linked {new Date(link.created_at).toLocaleString()}
                  </div>
                </div>
                <button className="secondary" style={{ width: "auto" }} onClick={() => unlinkTask.mutate(link.id)}>
                  Unlink
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function AssignResourceForm({ onAssign }: { onAssign: (body: Record<string, unknown>) => void }) {
  const [name, setName] = useState("");
  return (
    <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
      <input
        style={{ maxWidth: 200 }}
        placeholder="Team/vehicle name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <button
        className="secondary"
        style={{ width: "auto" }}
        disabled={!name.trim()}
        onClick={() => {
          onAssign({ display_name: name.trim(), resource_kind: "manual" });
          setName("");
        }}
      >
        Assign
      </button>
    </div>
  );
}
