import { resourceStatusVar, taskStatusVar, teamStatusVar } from "../../styles/statusColors";

type Domain = "team" | "task" | "resource";

interface StatusPillProps {
  domain: Domain;
  statusKey: string;
  label?: string;
}

const RESOLVERS: Record<Domain, (key: string) => { bg: string; fg: string }> = {
  team: teamStatusVar,
  task: taskStatusVar,
  resource: resourceStatusVar,
};

export default function StatusPill({ domain, statusKey, label }: StatusPillProps) {
  const { bg, fg } = RESOLVERS[domain](statusKey);
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
