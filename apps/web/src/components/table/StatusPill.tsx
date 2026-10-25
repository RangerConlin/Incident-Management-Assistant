import {
  pioStatusVar,
  logisticsRequestStatusVar,
  logisticsPriorityVar,
  facilityStatusVar,
  liaisonAgencyStatusVar,
  liaisonRequestStatusVar,
  liaisonPriorityVar,
  liaisonReportStateVar,
  meetingStatusVar,
  objectivePriorityVar,
  objectiveStatusVar,
  operationalPeriodStatusVar,
  resourceStatusVar,
  sitrepStatusVar,
  taskStatusVar,
  teamStatusVar,
  approvalStatusVar,
  approvalStepStatusVar,
  intelPriorityVar,
} from "../../styles/statusColors";

type Domain =
  | "team"
  | "task"
  | "resource"
  | "objective"
  | "objective-priority"
  | "op-period"
  | "meeting"
  | "sitrep"
  | "pio"
  | "liaison-agency"
  | "liaison-request"
  | "liaison-priority"
  | "liaison-report"
  | "logistics-request"
  | "logistics-priority"
  | "facility"
  | "approval"
  | "approval-step"
  | "intel-priority";

interface StatusPillProps {
  domain?: Domain;
  statusKey: string;
  label?: string;
}

const RESOLVERS: Record<Domain, (key: string) => { bg: string; fg: string }> = {
  pio: pioStatusVar,
  "logistics-request": logisticsRequestStatusVar,
  "logistics-priority": logisticsPriorityVar,
  facility: facilityStatusVar,
  "liaison-agency": liaisonAgencyStatusVar,
  "liaison-request": liaisonRequestStatusVar,
  "liaison-priority": liaisonPriorityVar,
  "liaison-report": liaisonReportStateVar,
  team: teamStatusVar,
  task: taskStatusVar,
  resource: resourceStatusVar,
  objective: objectiveStatusVar,
  "objective-priority": objectivePriorityVar,
  "op-period": operationalPeriodStatusVar,
  meeting: meetingStatusVar,
  sitrep: sitrepStatusVar,
  approval: approvalStatusVar,
  "approval-step": approvalStepStatusVar,
  "intel-priority": intelPriorityVar,
};

export default function StatusPill({ domain, statusKey, label }: StatusPillProps) {
  const colors = domain ? RESOLVERS[domain](statusKey) : null;
  const bg = colors?.bg ?? "var(--surface-raised)";
  const fg = colors?.fg ?? "var(--text-primary)";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 999,
        fontWeight: 600,
        fontSize: "0.8rem",
        textAlign: "center",
        background: bg,
        color: fg,
        whiteSpace: "nowrap",
      }}
    >
      {label ?? statusKey}
    </span>
  );
}
