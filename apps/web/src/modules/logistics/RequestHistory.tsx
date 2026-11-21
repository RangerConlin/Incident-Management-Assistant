import { useState } from "react";
import type { LogisticsRecord } from "../../api/types";
import { formatDateTime } from "../../utils/formatDateTime";
import { approvalsBySection, label, SECTIONS, SECTION_LABELS, SECTION_ROLE_LABELS, type ApprovalSection } from "./model";

// Which actions a pending row offers per section, and which note is
// required for which. Requesting can still Cancel while Logistics can
// still Review/Approve/Deny — both can show a pending row at once.
const SECTION_PENDING_ACTIONS: Record<ApprovalSection, string[]> = {
  requesting: ["CANCEL", "REOPEN"],
  logistics: ["REVIEW", "APPROVE", "DENY"],
  finance: ["FINANCE_APPROVE", "FINANCE_DENY"],
};

const actionLabel = (action: string) => label(action.replace(/^FINANCE_/, ""));

export default function RequestHistory({
  approvals,
  audit,
  availableActions,
  terminal,
  busy,
  onApprovalAction,
}: {
  approvals: LogisticsRecord[];
  audit: LogisticsRecord[];
  availableActions: string[];
  terminal: boolean;
  busy: boolean;
  onApprovalAction: (action: string, section: ApprovalSection, note: string) => void;
}) {
  const grouped = approvalsBySection(approvals);
  const [notes, setNotes] = useState<Record<ApprovalSection, string>>({ requesting: "", logistics: "", finance: "" });

  return (
    <>
      {/* One table, rows grouped by the responsible section the way a
          paper ICS-213RR actually lays its approval blocks out — not a
          flat chronological log. Each section's still-pending row (if any
          action remains available for it) carries its own note input and
          action buttons inline. */}
      <section className="logistics-panel">
        <h3>Required Approvals</h3>
        <table className="logistics-approvals-table">
          <thead>
            <tr>
              <th>Section</th>
              <th>Status</th>
              <th>Actor</th>
              <th>When</th>
              <th>Note</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {SECTIONS.map((section) => {
              const entries = grouped[section];
              const latest = entries[entries.length - 1];
              const pendingActions = SECTION_PENDING_ACTIONS[section].filter((a) => availableActions.includes(a));
              const showPendingRow = !terminal && pendingActions.length > 0;
              if (!latest && !showPendingRow) {
                return (
                  <tr key={section}>
                    <td>
                      <b>{SECTION_LABELS[section]}</b>
                      <div className="logistics-approval-role">{SECTION_ROLE_LABELS[section]}</div>
                    </td>
                    <td className="muted">{section === "finance" ? "Not Required" : "—"}</td>
                    <td className="muted">—</td>
                    <td className="muted">—</td>
                    <td className="muted">{section === "finance" ? "No cost impact flagged on this request." : "—"}</td>
                    <td className="muted">—</td>
                  </tr>
                );
              }
              return (
                <tr key={section}>
                  <td>
                    <b>{SECTION_LABELS[section]}</b>
                    <div className="logistics-approval-role">{SECTION_ROLE_LABELS[section]}</div>
                  </td>
                  <td>{latest ? actionLabel(String(latest.action ?? "")) : <span className="muted">Pending</span>}</td>
                  <td>{latest ? String(latest.actor_id ?? "—") : <span className="muted">—</span>}</td>
                  <td>{latest ? formatDateTime(String(latest.ts_utc ?? "")) : <span className="muted">—</span>}</td>
                  <td>
                    {showPendingRow ? (
                      <input
                        aria-label={`${SECTION_LABELS[section]} note`}
                        value={notes[section]}
                        disabled={busy}
                        onChange={(e) => setNotes((old) => ({ ...old, [section]: e.target.value }))}
                        placeholder="Note (required to deny)"
                        style={{ width: "100%" }}
                      />
                    ) : (
                      <span className={latest?.note ? "" : "muted"}>{String(latest?.note ?? "—")}</span>
                    )}
                  </td>
                  <td>
                    {showPendingRow && (
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {pendingActions.map((action) => (
                          <button
                            key={action}
                            disabled={busy || (action.includes("DENY") && !notes[section].trim())}
                            onClick={() => {
                              onApprovalAction(action, section, notes[section].trim());
                              setNotes((old) => ({ ...old, [section]: "" }));
                            }}
                          >
                            {actionLabel(action)}
                          </button>
                        ))}
                      </div>
                    )}
                    {!showPendingRow && !latest && <span className="muted">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="logistics-panel">
        <h3>Audit History</h3>
        <table className="logistics-approvals-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Event / action</th>
              <th>Actor</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {audit.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  No audit events recorded.
                </td>
              </tr>
            )}
            {audit.map((r, row) => (
              <tr key={row}>
                <td>{formatDateTime(String(r.ts_utc ?? ""))}</td>
                <td>{String(r.event ?? r.action ?? "")}</td>
                <td>{String(r.actor_id ?? "—")}</td>
                <td>{r.old || r.new ? `${r.old ?? ""} → ${r.new ?? ""}` : Array.isArray(r.fields) ? r.fields.join(", ") : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
