import { useState } from "react";
import { useSession } from "../../../auth/SessionContext";
import StatusPill from "../../../components/table/StatusPill";
import AssignStepControl from "../../../components/approvals/AssignStepControl";
import {
  useApprovalInstance,
  useAssignApprovalStep,
  useNotifyApprovalStep,
  useSignApprovalStep,
  useStartApproval,
} from "../../../components/approvals/hooks";

// Mirrors the desktop Work Assignment detail window's Approvals tab and the
// step_id values registered server-side under entity_type "work_assignment"
// (server/sarapp_db/sarapp_db/api/routers/approvals.py). Safety Officer is
// the only real approve/reject gate; Operations, Planning, and Logistics
// each just acknowledge ("Reviewed").
const WA_APPROVAL_STEPS: { stepId: string; label: string; code: string; isGate: boolean }[] = [
  { stepId: "sofr_approval", label: "Safety Officer", code: "SOFR", isGate: true },
  { stepId: "osc_review", label: "Operations Section Chief", code: "OSC", isGate: false },
  { stepId: "psc_review", label: "Planning Section Chief", code: "PSC", isGate: false },
  { stepId: "lsc_review", label: "Logistics Section Chief", code: "LSC", isGate: false },
];

interface WorkAssignmentApprovalsProps {
  incidentId: string;
  workAssignmentId: number;
}

export default function WorkAssignmentApprovals({ incidentId, workAssignmentId }: WorkAssignmentApprovalsProps) {
  const entityId = String(workAssignmentId);
  const { personnel } = useSession();
  const personRecord = personnel?.person_record ?? null;
  const { data: instance, isLoading } = useApprovalInstance(incidentId, "work_assignment", entityId);
  const start = useStartApproval(incidentId, "work_assignment", entityId);
  const sign = useSignApprovalStep(incidentId, "work_assignment", entityId);
  const assign = useAssignApprovalStep(incidentId, "work_assignment", entityId);
  const notify = useNotifyApprovalStep(incidentId, "work_assignment", entityId);
  const [error, setError] = useState<string | null>(null);
  const [rejectStepId, setRejectStepId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  if (isLoading) return null;

  const stepsById = new Map((instance?.steps ?? []).map((s) => [s.step_id, s]));
  const completedCount = [...stepsById.values()].filter((s) => s.status === "completed").length;
  const gate = stepsById.get("sofr_approval");
  let note = "";
  if (!instance) note = " · not yet requested";
  else if (instance.status === "rejected") note = " · Rejected";
  else if (gate && gate.status !== "completed") note = " · Safety approval pending";

  const statusText = (stepId: string, isGate: boolean) => {
    const step = stepsById.get(stepId);
    if (!step) return "Not Sent";
    if (step.status === "completed") {
      if (isGate) return instance?.status === "rejected" ? "Rejected" : "Approved";
      return "Reviewed";
    }
    if (step.status === "active") return "Pending";
    if (step.status === "skipped") return "Skipped";
    return "Waiting";
  };

  const act = (stepId: string, action: "approved" | "rejected" | "acknowledged", notes?: string) => {
    if (!personRecord) {
      setError("You must be signed in as a person record to act on this step.");
      return;
    }
    setError(null);
    sign.mutate(
      { step_id: stepId, actor_id: personRecord, action, notes },
      { onError: (err) => setError(err instanceof Error ? err.message : "Action failed.") }
    );
  };

  const confirmReject = () => {
    if (!rejectStepId) return;
    act(rejectStepId, "rejected", rejectReason.trim() || undefined);
    setRejectStepId(null);
    setRejectReason("");
  };

  return (
    <div>
      <p style={{ opacity: 0.75, marginBottom: 12 }}>
        {completedCount} of {WA_APPROVAL_STEPS.length} sign-offs complete
        {note}
      </p>
      {error && <p className="error">{error}</p>}
      {rejectStepId && (
        <div className="field" style={{ marginBottom: 12 }}>
          <label htmlFor="wa-reject-reason">Why is this being rejected?</label>
          <textarea id="wa-reject-reason" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button style={{ width: "auto" }} disabled={sign.isPending} onClick={confirmReject}>
              Confirm Reject
            </button>
            <button className="secondary" style={{ width: "auto" }} onClick={() => setRejectStepId(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {WA_APPROVAL_STEPS.map(({ stepId, label, code, isGate }) => {
        const step = stepsById.get(stepId);
        const text = statusText(stepId, isGate);
        const canAct = step?.status === "active" && Boolean(personRecord) && step.resolved_actor_id === personRecord;
        const needsAssignment = step?.status === "active" && step.resolved_actor_id === null;
        return (
          <div
            key={stepId}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 14px",
              marginBottom: 8,
              background: "var(--surface-raised, #1b1e24)",
              borderRadius: 6,
              flexWrap: "wrap",
            }}
          >
            <strong style={{ flex: 1, minWidth: 180 }}>
              {label} ({code})
            </strong>
            <StatusPill domain="approval-step" statusKey={step?.status ?? "waiting"} label={text} />
            {step?.completed_at && (
              <span style={{ opacity: 0.7, fontSize: "0.85rem" }}>{new Date(step.completed_at).toLocaleString()}</span>
            )}
            {needsAssignment && (
              <AssignStepControl
                disabled={assign.isPending}
                onAssign={(pr) =>
                  assign.mutate(
                    { step_id: stepId, actor_id: pr },
                    { onError: (err) => setError(err instanceof Error ? err.message : "Assign failed.") }
                  )
                }
              />
            )}
            {canAct && isGate && (
              <div style={{ display: "flex", gap: 4 }}>
                <button style={{ width: "auto" }} disabled={sign.isPending} onClick={() => act(stepId, "approved")}>
                  Approve
                </button>
                <button
                  className="secondary"
                  style={{ width: "auto" }}
                  disabled={sign.isPending}
                  onClick={() => setRejectStepId(stepId)}
                >
                  Reject
                </button>
              </div>
            )}
            {canAct && !isGate && (
              <button style={{ width: "auto" }} disabled={sign.isPending} onClick={() => act(stepId, "acknowledged")}>
                Mark Reviewed
              </button>
            )}
            {step?.status === "active" && step.resolved_actor_id != null && (
              <button
                className="secondary"
                style={{ width: "auto" }}
                disabled={notify.isPending}
                onClick={() => notify.mutate(stepId)}
              >
                {isGate ? "Send for Approval" : "Send for Review"}
              </button>
            )}
          </div>
        );
      })}
      {!instance && (
        <button
          style={{ width: "auto" }}
          disabled={start.isPending}
          onClick={() =>
            start.mutate({}, { onError: (err) => setError(err instanceof Error ? err.message : "Request failed.") })
          }
        >
          Request Sign-offs
        </button>
      )}
    </div>
  );
}
