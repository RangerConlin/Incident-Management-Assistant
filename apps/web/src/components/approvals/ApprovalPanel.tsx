import { useState } from "react";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../table/StatusPill";
import AssignStepControl from "./AssignStepControl";
import { useApprovalInstance, useAssignApprovalStep, useSignApprovalStep, useStartApproval } from "./hooks";

const OVERALL_LABELS: Record<string, string> = {
  not_started: "Not Started",
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

interface ApprovalPanelProps {
  incidentId: string;
  entityType: string;
  entityId: string | null;
  startLabel?: string;
}

export default function ApprovalPanel({ incidentId, entityType, entityId, startLabel = "Submit for Approval" }: ApprovalPanelProps) {
  const { personnel } = useSession();
  const personRecord = personnel?.person_record ?? null;
  const { data: instance, isLoading } = useApprovalInstance(incidentId, entityType, entityId);
  const start = useStartApproval(incidentId, entityType, entityId);
  const sign = useSignApprovalStep(incidentId, entityType, entityId);
  const assign = useAssignApprovalStep(incidentId, entityType, entityId);
  const [error, setError] = useState<string | null>(null);

  if (!entityId || isLoading) return null;

  const act = (stepId: string, action: "approved" | "rejected") => {
    if (!personRecord) {
      setError("You must be signed in as a person record to act on this step.");
      return;
    }
    setError(null);
    sign.mutate(
      { step_id: stepId, actor_id: personRecord, action },
      { onError: (err) => setError(err instanceof Error ? err.message : "Sign failed.") }
    );
  };

  const assignStep = (stepId: string, personRecordToAssign: number) => {
    setError(null);
    assign.mutate(
      { step_id: stepId, actor_id: personRecordToAssign },
      { onError: (err) => setError(err instanceof Error ? err.message : "Assign failed.") }
    );
  };

  return (
    <div className="field" style={{ marginTop: 16 }}>
      <h3 style={{ marginBottom: 8 }}>Approval</h3>
      {error && <p className="error">{error}</p>}
      {instance === null ? (
        <button
          className="secondary"
          style={{ width: "auto" }}
          disabled={start.isPending}
          onClick={() => start.mutate(undefined, { onError: (err) => setError(err instanceof Error ? err.message : "Submission failed.") })}
        >
          {startLabel}
        </button>
      ) : instance ? (
        <div>
          <div style={{ marginBottom: 8 }}>
            <StatusPill domain="approval" statusKey={instance.status} label={OVERALL_LABELS[instance.status] ?? instance.status} />
          </div>
          {instance.steps.map((step) => {
            const needsAssignment = step.status === "active" && step.kind !== "ack" && step.resolved_actor_id === null;
            const canSign =
              step.status === "active" &&
              Boolean(personRecord) &&
              (step.kind === "ack" || step.resolved_actor_id === personRecord);
            return (
              <div key={step.step_id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <StatusPill domain="approval-step" statusKey={step.status} label={step.status} />
                <span>
                  {step.label}
                  {step.resolved_role && step.resolved_role !== step.role ? ` (${step.resolved_role.toLowerCase() === "manually assigned" ? "manually assigned" : `escalated to ${step.resolved_role}`})` : ""}
                </span>
                {needsAssignment && (
                  <AssignStepControl disabled={assign.isPending} onAssign={(personRecordToAssign) => assignStep(step.step_id, personRecordToAssign)} />
                )}
                {canSign && (
                  <div style={{ display: "flex", gap: 4 }}>
                    <button style={{ width: "auto" }} disabled={sign.isPending} onClick={() => act(step.step_id, "approved")}>
                      Sign
                    </button>
                    {step.kind !== "ack" && (
                      <button
                        className="secondary"
                        style={{ width: "auto" }}
                        disabled={sign.isPending}
                        onClick={() => act(step.step_id, "rejected")}
                      >
                        Reject
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
