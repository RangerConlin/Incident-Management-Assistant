import { useState } from "react";
import type { TaskDetail } from "../../../api/types";
import { useLinkTaskWorkAssignment, useTaskWorkAssignments, useUnlinkTaskWorkAssignment } from "./hooks";

export default function PlanningTab({ incidentId, task }: { incidentId: string; task: TaskDetail }) {
  const [waIdInput, setWaIdInput] = useState("");
  const { data: links = [], isLoading } = useTaskWorkAssignments(incidentId, task.int_id);
  const linkWa = useLinkTaskWorkAssignment(incidentId, task.int_id);
  const unlinkWa = useUnlinkTaskWorkAssignment(incidentId, task.int_id);

  return (
    <div>
      <h3>Linked Work Assignments</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          style={{ maxWidth: 200 }}
          placeholder="Work Assignment ID (numeric)"
          value={waIdInput}
          onChange={(e) => setWaIdInput(e.target.value)}
        />
        <button
          style={{ width: "auto" }}
          disabled={!waIdInput.trim() || linkWa.isPending}
          onClick={() => {
            const waId = Number(waIdInput);
            if (!Number.isFinite(waId)) return;
            linkWa.mutate(waId, { onSuccess: () => setWaIdInput("") });
          }}
        >
          Link Work Assignment
        </button>
      </div>

      {isLoading ? (
        <p>Loading…</p>
      ) : links.length === 0 ? (
        <p style={{ opacity: 0.6 }}>No work assignments linked yet.</p>
      ) : (
        links.map((link) => (
          <div key={link.link_id} className="list-item" style={{ cursor: "default" }}>
            <div>
              <div style={{ fontWeight: 600 }}>
                <a href={`#/planning/work-assignments/${link.id}`}>
                  {link.assignment_number || `WA #${link.id}`} — {link.assignment_name}
                </a>
              </div>
              <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                {link.planning_status} · {link.link_type || "linked"}
              </div>
            </div>
            <button
              className="secondary"
              style={{ width: "auto" }}
              onClick={() => unlinkWa.mutate({ waId: link.id, linkId: link.link_id })}
            >
              Unlink
            </button>
          </div>
        ))
      )}
    </div>
  );
}
