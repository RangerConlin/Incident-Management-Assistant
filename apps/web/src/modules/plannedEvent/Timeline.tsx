import { Link } from "react-router-dom";
import { formatDateTime } from "../../utils/formatDateTime";
import { attention, parseTime, type PlannedRecord } from "./model";

const statusClass = (s: string) => "pe-st-" + s.toLowerCase().replace(/\s+/g, "-");

/**
 * Proportional timeline: one bar per activity for the planned window and a
 * thin line beneath it for what actually happened. The marker is "now".
 */
export default function Timeline({ rows, now, emptyMessage }: { rows: PlannedRecord[]; now: number; emptyMessage: string }) {
  const spans = rows.map(r => {
    const start = parseTime(r.starts_at) ?? parseTime(r.actual_start_at);
    const end = parseTime(r.ends_at) ?? parseTime(r.actual_end_at) ?? start;
    return { r, start, end, aStart: parseTime(r.actual_start_at), aEnd: parseTime(r.actual_end_at) ?? (r.status === "In Progress" ? now : null) };
  });
  const dated = spans.filter(s => s.start !== null);
  if (rows.length === 0) return <p>{emptyMessage}</p>;
  if (dated.length === 0) return <p>These activities have no planned times yet, so they cannot be placed on a timeline. Use the List view.</p>;

  const points = dated.flatMap(s => [s.start!, s.end ?? s.start!, s.aStart ?? s.start!, s.aEnd ?? s.start!]);
  const lo = Math.min(...points, now), hi = Math.max(...points, now);
  const pad = Math.max((hi - lo) * 0.03, 5 * 60_000);
  const min = lo - pad, span = hi + pad - min;
  const pct = (ms: number) => ((ms - min) / span) * 100;
  const ticks = Array.from({ length: 6 }, (_, i) => min + (span * i) / 5);
  const undated = spans.filter(s => s.start === null);

  return (
    <div className="pe-timeline">
      <div className="pe-tl-head">
        <span>Activity</span>
        <div className="pe-tl-axis" aria-hidden="true">{ticks.map((t, i) => <span key={i} style={{ left: `${pct(t)}%` }}>{formatDateTime(new Date(t).toISOString())}</span>)}</div>
      </div>
      {dated.map(({ r, start, end, aStart, aEnd }) => {
        const flag = attention(r, now);
        const width = Math.max(pct(end ?? start!) - pct(start!), 0.4);
        return (
          <div className="pe-tl-row" key={r.id}>
            <div className="pe-tl-name"><Link to={`${r.id}`} title={`${r.title} — ${r.status}`}>{r.title || `Activity #${r.id}`}</Link>{flag && flag.kind !== "starting-soon" && <> <span className="pe-flag">{flag.label}</span></>}</div>
            <div className="pe-tl-track">
              <div className={`pe-tl-bar ${statusClass(r.status)}`} style={{ left: `${pct(start!)}%`, width: `${width}%` }} title={`Planned ${formatDateTime(r.starts_at)} – ${formatDateTime(r.ends_at)}`} />
              {aStart !== null && <div className="pe-tl-actual" style={{ left: `${pct(aStart)}%`, width: `${Math.max(pct(aEnd ?? aStart) - pct(aStart), 0.3)}%` }} title={`Actual ${formatDateTime(r.actual_start_at)} – ${r.actual_end_at ? formatDateTime(r.actual_end_at) : "still running"}`} />}
              <div className="pe-tl-now" style={{ left: `${pct(now)}%` }} />
            </div>
          </div>
        );
      })}
      {undated.length > 0 && <p className="pe-note">{undated.length} activit{undated.length === 1 ? "y has" : "ies have"} no planned time and {undated.length === 1 ? "is" : "are"} only in the List view.</p>}
    </div>
  );
}
