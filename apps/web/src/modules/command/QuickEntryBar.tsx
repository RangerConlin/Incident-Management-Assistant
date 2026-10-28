import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import { useCreateTask, TASK_PRIORITIES } from "../operations/taskStatus/hooks";
import { useAddCommsLogEntry, COMMS_PRIORITY_OPTIONS } from "../communications/log/hooks";
import { useRequestWrites } from "../logistics/hooks";
import { PRIORITIES as RESOURCE_REQUEST_PRIORITIES } from "../logistics/model";
import { useCreateWorkAssignment } from "../planning/workAssignments/hooks";
import { useRecordActions } from "../workspaces/hooks";
import { WORKSPACES } from "../workspaces/config";
import { useCreateObjective } from "./objectives/hooks";
import NewObjectiveDialog from "./objectives/NewObjectiveDialog";

export const SAFETY_REPORTS_DATASET = WORKSPACES.find((w) => w.path === "/safety")!.datasets.find((d) => d.key === "reports")!;
const SAFETY_SEVERITIES = SAFETY_REPORTS_DATASET.fields.find((f) => f.key === "severity")!.options!;

type QuickEntryType = "task" | "comm" | "resource" | "safety" | "objective" | "work";

// Compact action row above the dashboard title — each button opens a
// lightweight create dialog wired to the same mutations the real board
// pages use, so a quick entry here shows up exactly where it already would.
export default function QuickEntryBar() {
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const id = incidentId!;
  const [open, setOpen] = useState<QuickEntryType | null>(null);

  const createTask = useCreateTask(id);
  const addComm = useAddCommsLogEntry(id);
  const requestWrites = useRequestWrites(id, "new");
  const safetyActions = useRecordActions(SAFETY_REPORTS_DATASET, id);
  const createObjective = useCreateObjective(id);
  const createWork = useCreateWorkAssignment(id);

  return (
    <>
      <div className="qe-row qe-compact">
        <button className="qe-btn" type="button" onClick={() => setOpen("task")}>+ New Task</button>
        <button className="qe-btn" type="button" onClick={() => setOpen("comm")}>+ Comm Entry (213)</button>
        <button className="qe-btn" type="button" onClick={() => setOpen("resource")}>+ Resource Request</button>
        <button className="qe-btn" type="button" onClick={() => setOpen("safety")}>+ Safety Report</button>
        <button className="qe-btn" type="button" onClick={() => setOpen("objective")}>+ Objective</button>
        <button className="qe-btn" type="button" onClick={() => setOpen("work")}>+ Work Assignment</button>
      </div>

      {open === "task" && (
        <NewTaskDialog
          busy={createTask.isPending}
          onCancel={() => setOpen(null)}
          onCreate={(body) =>
            createTask.mutate(body, {
              onSuccess: (task) => {
                setOpen(null);
                navigate(`/ops/tasks/${task.int_id}`);
              },
            })
          }
        />
      )}
      {open === "comm" && (
        <NewCommEntryDialog
          busy={addComm.isPending}
          operatorName={user?.username}
          onCancel={() => setOpen(null)}
          onCreate={(body) => addComm.mutate(body, { onSuccess: () => setOpen(null) })}
        />
      )}
      {open === "resource" && (
        <NewResourceRequestDialog
          busy={requestWrites.save.isPending}
          onCancel={() => setOpen(null)}
          onCreate={(body) =>
            requestWrites.save.mutate(
              { ...body, status: "DRAFT", created_by_id: user?.username },
              {
                onSuccess: (req) => {
                  setOpen(null);
                  navigate(`/logistics/resource-requests/${req.id}`);
                },
              }
            )
          }
        />
      )}
      {open === "safety" && (
        <NewSafetyReportDialog
          busy={safetyActions.save.isPending}
          onCancel={() => setOpen(null)}
          onCreate={(body) =>
            safetyActions.save.mutate(
              { id: null, body: { ...body, reported_by: user?.username } },
              { onSuccess: () => setOpen(null) }
            )
          }
        />
      )}
      {open === "objective" && (
        <NewObjectiveDialog
          busy={createObjective.isPending}
          onCancel={() => setOpen(null)}
          onCreate={(body) =>
            createObjective.mutate({ ...body, created_by: user?.username }, { onSuccess: () => setOpen(null) })
          }
        />
      )}
      {open === "work" && (
        <NewWorkAssignmentDialog
          busy={createWork.isPending}
          onCancel={() => setOpen(null)}
          onCreate={(body) =>
            createWork.mutate(
              { ...body, created_by: user?.username },
              {
                onSuccess: (wa) => {
                  setOpen(null);
                  navigate(`/planning/work-assignments/${wa.id}`);
                },
              }
            )
          }
        />
      )}
    </>
  );
}

function NewTaskDialog({
  onCreate,
  onCancel,
  busy,
}: {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState("Medium");
  const [location, setLocation] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Task</h3>
        <div className="field">
          <label htmlFor="qe-task-title">Title</label>
          <input id="qe-task-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Search Grid 12B" autoFocus />
        </div>
        <div className="field">
          <label htmlFor="qe-task-priority">Priority</label>
          <select id="qe-task-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {TASK_PRIORITIES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="qe-task-location">Location</label>
          <input id="qe-task-location" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Optional" />
        </div>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>Cancel</button>
          <button
            disabled={!title.trim() || busy}
            onClick={() => onCreate({ title: title.trim(), priority, location: location.trim() || null })}
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function NewCommEntryDialog({
  onCreate,
  onCancel,
  busy,
  operatorName,
}: {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
  operatorName?: string;
}) {
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState("Routine");
  const [fromUnit, setFromUnit] = useState("");
  const [toUnit, setToUnit] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Comm Entry (213)</h3>
        <div className="field">
          <label htmlFor="qe-comm-from">From</label>
          <input id="qe-comm-from" value={fromUnit} onChange={(e) => setFromUnit(e.target.value)} placeholder="e.g. GT Delta" autoFocus />
        </div>
        <div className="field">
          <label htmlFor="qe-comm-to">To</label>
          <input id="qe-comm-to" value={toUnit} onChange={(e) => setToUnit(e.target.value)} placeholder="e.g. Command" />
        </div>
        <div className="field">
          <label htmlFor="qe-comm-priority">Priority</label>
          <select id="qe-comm-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {COMMS_PRIORITY_OPTIONS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="qe-comm-message">Message</label>
          <textarea id="qe-comm-message" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Traffic content…" />
        </div>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>Cancel</button>
          <button
            disabled={!message.trim() || busy}
            onClick={() =>
              onCreate({
                message: message.trim(),
                priority,
                from_unit: fromUnit.trim(),
                to_unit: toUnit.trim(),
                operator_display_name: operatorName,
                follow_up_required: priority === "Emergency",
              })
            }
          >
            {busy ? "Logging…" : "Log Entry"}
          </button>
        </div>
      </div>
    </div>
  );
}

function NewResourceRequestDialog({
  onCreate,
  onCancel,
  busy,
}: {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState("ROUTINE");
  const [section, setSection] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Resource Request</h3>
        <div className="field">
          <label htmlFor="qe-rr-title">What's needed</label>
          <input id="qe-rr-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. 2x additional ground teams" autoFocus />
        </div>
        <div className="field">
          <label htmlFor="qe-rr-priority">Priority</label>
          <select id="qe-rr-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {RESOURCE_REQUEST_PRIORITIES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="qe-rr-section">Requesting section</label>
          <input id="qe-rr-section" value={section} onChange={(e) => setSection(e.target.value)} placeholder="e.g. Operations" />
        </div>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>Cancel</button>
          <button
            disabled={!title.trim() || busy}
            onClick={() => onCreate({ title: title.trim(), priority, requesting_section: section.trim() })}
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function NewSafetyReportDialog({
  onCreate,
  onCancel,
  busy,
}: {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  const [location, setLocation] = useState("");
  const [severity, setSeverity] = useState(SAFETY_SEVERITIES[0]);
  const [notesValue, setNotesValue] = useState("");
  const [flagged, setFlagged] = useState(true);

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Safety Report</h3>
        <div className="field">
          <label htmlFor="qe-safety-location">Location</label>
          <input
            id="qe-safety-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Segment 7, Oak St. & 4th"
            autoFocus
          />
        </div>
        <div className="field">
          <label htmlFor="qe-safety-severity">Severity</label>
          <select id="qe-safety-severity" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            {SAFETY_SEVERITIES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="qe-safety-notes">Notes</label>
          <textarea
            id="qe-safety-notes"
            value={notesValue}
            onChange={(e) => setNotesValue(e.target.value)}
            placeholder="What happened, who's affected, what's being done…"
          />
        </div>
        <label className="command-check">
          <input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} /> Flag for Command's Safety Alerts panel
        </label>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>Cancel</button>
          <button
            disabled={!notesValue.trim() || busy}
            onClick={() =>
              onCreate({
                time: new Date().toISOString(),
                location: location.trim(),
                severity,
                notes: notesValue.trim(),
                flagged,
              })
            }
          >
            {busy ? "Reporting…" : "Report"}
          </button>
        </div>
      </div>
    </div>
  );
}

function NewWorkAssignmentDialog({
  onCreate,
  onCancel,
  busy,
}: {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Work Assignment</h3>
        <div className="field">
          <label htmlFor="qe-wa-name">Assignment name</label>
          <input
            id="qe-wa-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Division A — Ridge Line Clearance"
            autoFocus
          />
        </div>
        <div className="field">
          <label htmlFor="qe-wa-location">Location</label>
          <input id="qe-wa-location" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Optional" />
        </div>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>Cancel</button>
          <button
            disabled={!name.trim() || busy}
            onClick={() => onCreate({ assignment_name: name.trim(), location: location.trim() })}
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
