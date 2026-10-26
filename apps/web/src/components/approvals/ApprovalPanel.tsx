import { useState } from "react";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../table/StatusPill";
import AssignStepControl from "./AssignStepControl";
import SubmitApprovalDialog from "./SubmitApprovalDialog";
import { fetchSignPreview, fetchStartPreview, useApprovalInstance, useAssignApprovalStep, useSignApprovalStep, useStartApproval } from "./hooks";
import type { ApprovalPreviewRow } from "../../api/types";

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

type PendingConfirm = { kind: "start" } | { kind: "sign"; stepId: string };

export default function ApprovalPanel({ incidentId, entityType, entityId, startLabel = "Submit for Approval" }: ApprovalPanelProps) {
  const { personnel } = useSession();
  const personRecord = personnel?.person_record ?? null;
  const { data: instance, isLoading } = useApprovalInstance(incidentId, entityType, entityId);
  const start = useStartApproval(incidentId, entityType, entityId);
  const sign = useSignApprovalStep(incidentId, entityType, entityId);
  const assign = useAssignApprovalStep(incidentId, entityType, entityId);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const [previewRows, setPreviewRows] = useState<ApprovalPreviewRow[]>([]);

  if (!entityId || isLoading) return null;

  const beginStart = async () => {
    setError(null);
    try {
      const rows = await fetchStartPreview(incidentId, entityType, entityId);
      if (rows.length === 0) {
        start.mutate({}, { onError: (err) => setError(err instanceof Error ? err.message : "Submission failed.") });
        return;
      }
      setPreviewRows(rows);
      setPending({ kind: "start" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load submission preview.");
    }
  };

  const beginSign = async (stepId: string) => {
    if (!personRecord) {
      setError("You must be signed in as a person record to act on this step.");
      return;
    }
    setError(null);
    try {
      const rows = await fetchSignPreview(incidentId, entityType, entityId, stepId);
      if (rows.length === 0) {
        sign.mutate(
          { step_id: stepId, actor_id: personRecord, action: "approved" },
          { onError: (err) => setError(err instanceof Error ? err.message : "Sign failed.") }
        );
        return;
      }
      setPreviewRows(rows);
      setPending({ kind: "sign", stepId });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load sign preview.");
    }
  };

  const reject = (stepId: string) => {
    if (!personRecord) return;
    setError(null);
    sign.mutate(
      { step_id: stepId, actor_id: personRecord, action: "rejected" },
      { onError: (err) => setError(err instanceof Error ? err.message : "Reject failed.") }
    );
  };

  const confirmPending = (assignActors: Record<string, number>) => {
    if (!pending) return;
    if (pending.kind === "start") {
      start.mutate(assignActors, { onError: (err) => setError(err instanceof Error ? err.message : "Submission failed.") });
    } else if (personRecord) {
      sign.mutate(
        { step_id: pending.stepId, actor_id: personRecord, action: "approved", assign_actors: assignActors },
        { onError: (err) => setError(err instanceof Error ? err.message : "Sign failed.") }
      );
    }
    setPending(null);
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
      {pending && (
        <SubmitApprovalDialog
          title={pending.kind === "start" ? "Submit for Approval" : "Sign — next step"}
          rows={previewRows}
          onConfirm={confirmPending}
          onCancel={() => setPending(null)}
        />
      )}
      {instance === null ? (
        <button className="secondary" style={{ width: "auto" }} disabled={start.isPending} onClick={beginStart}>
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
                  {step.resolved_role && step.resolved_role !== step.role
                    ? ` (${step.resolved_role === "Selected by submitter" ? "selected by submitter" : `escalated to ${step.resolved_role}`})`
                    : ""}
                </span>
                {needsAssignment && (
                  <AssignStepControl disabled={assign.isPending} onAssign={(personRecordToAssign) => assignStep(step.step_id, personRecordToAssign)} />
                )}
                {canSign && (
                  <div style={{ display: "flex", gap: 4 }}>
                    <button style={{ width: "auto" }} disabled={sign.isPending} onClick={() => beginSign(step.step_id)}>
                      Sign
                    </button>
                    {step.kind !== "ack" && (
                      <button className="secondary" style={{ width: "auto" }} disabled={sign.isPending} onClick={() => reject(step.step_id)}>
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
