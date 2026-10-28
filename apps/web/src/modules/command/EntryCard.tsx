import { useState, type ReactNode } from "react";
import { severityVar, type SeverityKey } from "../../styles/statusColors";

export interface EntryCardProps {
  severity?: SeverityKey;
  flag?: string;
  title: ReactNode;
  when?: string;
  summary: ReactNode;
  children?: ReactNode;
}

// Each list entry is its own card, tinted to its severity so color reads at
// a glance across the whole row, not just from a small badge. Clicking
// expands it in place (an accordion, not a side drawer) — independent per
// card. A click on a link inside the expanded detail doesn't collapse it.
export default function EntryCard({ severity, flag, title, when, summary, children }: EntryCardProps) {
  const [expanded, setExpanded] = useState(false);
  const sev = severity ? severityVar(severity) : null;

  return (
    <div
      className={"entry-card" + (expanded ? " expanded" : "")}
      style={
        sev
          ? {
              background: `color-mix(in srgb, ${sev.bg} 12%, #1d2024)`,
              borderColor: `color-mix(in srgb, ${sev.bg} 40%, #2a2d33)`,
            }
          : undefined
      }
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("a")) return;
        setExpanded((v) => !v);
      }}
    >
      {flag && (
        <span className={"flag" + (sev ? "" : " neutral")} style={sev ? { background: sev.bg, color: sev.fg } : undefined}>
          {flag}
        </span>
      )}
      <span className="who">{title}</span>
      {when && <span className="when">{when}</span>}
      <svg className="entry-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
        <path d="m9 18 6-6-6-6" />
      </svg>
      <p>{summary}</p>
      {expanded && children && <div className="entry-detail">{children}</div>}
    </div>
  );
}
