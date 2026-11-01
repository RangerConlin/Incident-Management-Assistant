import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import { useOperationalPeriods } from "../planning/operationalPeriods/hooks";
import { formatDateTime } from "../../utils/formatDateTime";
import { iapStatusVar } from "../../styles/statusColors";
import { useIapPackage, useIapPackages, useIapWrites } from "./hooks";
import ApprovalPanel from "../../components/approvals/ApprovalPanel";
import "./command.css";

const FORM_CATALOG: [string, string][] = [
  ["ICS-201", "Incident Briefing"],
  ["ICS-202", "Incident Objectives"],
  ["ICS-203", "Organization Assignment List"],
  ["ICS-204", "Assignment List"],
  ["ICS-205", "Communications Plan"],
  ["ICS-206", "Medical Plan"],
  ["ICS-207", "Organization Chart"],
  ["ICS-208", "Safety Message / Plan"],
  ["ICS-214", "Activity Log"],
];

const STATUS_OPTIONS = ["draft", "in_review", "approved", "published", "superseded"];

function InfoIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" /><path d="M12 8h.01" />
    </svg>
  );
}

export default function IapPackagesPage() {
  const { opNumber } = useParams();
  const { incidentId } = useSession();
  const id = incidentId!;
  const nav = useNavigate();

  const periods = useOperationalPeriods(id);
  const packagesQuery = useIapPackages(id);
  const packages = packagesQuery.data ?? [];

  const rows = useMemo(() => {
    const byOp = new Map(packages.map((p) => [p.op_number, p]));
    const opNumbers = new Set<number>([...byOp.keys(), ...(periods.data?.map((p) => p.number) ?? [])]);
    return [...opNumbers].sort((a, b) => a - b).map((op) => ({
      op,
      period: periods.data?.find((p) => p.number === op),
      pkg: byOp.get(op),
    }));
  }, [packages, periods.data]);

  const next = Math.max(0, ...rows.map((r) => r.op)) + 1;
  const selectedOp = opNumber ? Number(opNumber) : undefined;
  const selectedRow = rows.find((r) => r.op === selectedOp);

  const pkgQuery = useIapPackage(id, selectedOp);
  const writes = useIapWrites(id, selectedOp);

  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [formId, setFormId] = useState(FORM_CATALOG[0][0]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (pkgQuery.data) {
      setDraft({ ...pkgQuery.data });
    } else if (selectedRow?.period) {
      setDraft({ status: "draft", op_start: selectedRow.period.start_time, op_end: selectedRow.period.end_time, notes: "", version_tag: "" });
    } else {
      setDraft({ status: "draft", op_start: "", op_end: "", notes: "", version_tag: "" });
    }
  }, [pkgQuery.data, selectedRow]);

  const exists = Boolean(pkgQuery.data);
  const forms = [...(pkgQuery.data?.forms ?? [])].sort((a, b) => a.display_order - b.display_order);
  const set = (k: string, v: unknown) => setDraft((d) => ({ ...d, [k]: v }));

  if (periods.isPending && packagesQuery.isPending) return <p>Loading IAP packages…</p>;

  return (
    <div className="command-page">
      <div className="command-heading">
        <div>
          <h2>Incident Action Plans</h2>
          <p>Assemble and track the form package for each operational period.</p>
        </div>
        <button className="secondary" style={{ width: "auto" }} type="button" onClick={() => nav(`/command/iap/${next}`)}>
          + New IAP package
        </button>
      </div>
      {message && <p role="status">{message}</p>}

      <div className="org-layout">
        <div className="org-tree-panel">
          <h3>Operational periods</h3>
          {rows.length === 0 ? (
            <p className="org-assign-empty">No operational periods exist yet — create one in Planning first.</p>
          ) : (
            rows.map(({ op, period, pkg }) => {
              const status = pkg?.status ?? "not_started";
              const color = status === "not_started" ? undefined : iapStatusVar(status);
              return (
                <div
                  key={op}
                  className={"org-node" + (selectedOp === op ? " selected" : "")}
                  onClick={() => nav(`/command/iap/${op}`)}
                >
                  <span className="org-node-title">
                    Period {op}{period ? ` · ${period.name}` : ""}
                  </span>
                  <span
                    className="org-node-assign"
                    style={color ? { background: color.bg, color: color.fg, borderRadius: 999, padding: "1px 8px" } : undefined}
                  >
                    {status.replaceAll("_", " ")}
                  </span>
                </div>
              );
            })
          )}
        </div>

        {!selectedRow ? (
          <div className="org-detail-panel"><p className="org-assign-empty">Select an operational period to view or create its IAP package.</p></div>
        ) : (
          <div className="org-detail-panel">
            <div className="org-detail-head">
              <h4>IAP · Operational Period {selectedOp}</h4>
              <span className="org-tag">{exists ? `${forms.length} forms` : "not created yet"}</span>
            </div>

            <form
              className="command-form"
              onSubmit={async (e) => {
                e.preventDefault();
                await writes.save.mutateAsync({ ...draft, incident_id: id });
                setMessage("IAP package saved.");
              }}
            >
              <label>
                Status
                <select value={String(draft.status ?? "draft")} onChange={(e) => set("status", e.target.value)}>
                  {STATUS_OPTIONS.map((v) => <option key={v} value={v}>{v.replaceAll("_", " ")}</option>)}
                </select>
              </label>
              <label>Starts<input required type="datetime-local" value={String(draft.op_start ?? "").slice(0, 16)} onChange={(e) => set("op_start", e.target.value)} /></label>
              <label>Ends<input required type="datetime-local" value={String(draft.op_end ?? "").slice(0, 16)} onChange={(e) => set("op_end", e.target.value)} /></label>
              <label>Version tag<input value={String(draft.version_tag ?? "")} onChange={(e) => set("version_tag", e.target.value)} /></label>
              <label className="command-wide">Package notes<textarea rows={3} value={String(draft.notes ?? "")} onChange={(e) => set("notes", e.target.value)} /></label>
              <div className="command-wide" style={{ display: "flex", gap: 8 }}>
                <button disabled={writes.save.isPending}>{writes.save.isPending ? "Saving…" : exists ? "Save package" : "Create package"}</button>
                <button
                  className="secondary" style={{ width: "auto" }} type="button" disabled
                  title="Not built yet — no server-side IAP PDF export is registered. Will write to published_pdf_path once implemented."
                >
                  Export PDF
                </button>
              </div>
            </form>

            {exists && (
              <>
                <div className="org-section-label">Package forms</div>
                <div className="org-info-strip">
                  <InfoIcon />
                  <span>
                    Autofill from incident data (incident name, IC, op dates) into these forms is not built yet — each form is filled in on its own page today.
                  </span>
                </div>
                {forms.length === 0 ? (
                  <p className="org-assign-empty">No forms added to this package yet.</p>
                ) : (
                  <table className="org-assign-table">
                    <thead><tr><th>Form</th><th>Status</th><th>Updated</th><th></th></tr></thead>
                    <tbody>
                      {forms.map((f, index) => (
                        <tr key={f.form_id}>
                          <td>{f.form_id} · {f.title}</td>
                          <td><span className="org-tag">{f.status}</span></td>
                          <td>{formatDateTime(f.last_updated)}</td>
                          <td style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                            <button
                              className="secondary" style={{ width: "auto" }} type="button" disabled={index === 0}
                              onClick={() => {
                                const order = forms.map((x) => x.form_id);
                                [order[index - 1], order[index]] = [order[index], order[index - 1]];
                                writes.order.mutate(order);
                              }}
                            >
                              Up
                            </button>
                            <button
                              className="secondary" style={{ width: "auto" }} type="button" disabled={index === forms.length - 1}
                              onClick={() => {
                                const order = forms.map((x) => x.form_id);
                                [order[index + 1], order[index]] = [order[index], order[index + 1]];
                                writes.order.mutate(order);
                              }}
                            >
                              Down
                            </button>
                            <button
                              className="link-button" type="button"
                              onClick={() => { if (confirm(`Remove ${f.form_id} from this package?`)) writes.removeForm.mutate(f.form_id); }}
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10 }}>
                  <select value={formId} onChange={(e) => setFormId(e.target.value)} style={{ width: "auto" }}>
                    {FORM_CATALOG.filter(([fid]) => !forms.some((f) => f.form_id === fid)).map(([fid, title]) => (
                      <option key={fid} value={fid}>{fid} · {title}</option>
                    ))}
                  </select>
                  <button
                    className="secondary" style={{ width: "auto" }} type="button"
                    onClick={() => {
                      const item = FORM_CATALOG.find((x) => x[0] === formId);
                      if (item) writes.form.mutate({ formId, body: { form_id: formId, title: item[1], op_number: selectedOp, status: "draft", revision: 0, display_order: forms.length } });
                    }}
                  >
                    Add form
                  </button>
                </div>

                <div className="org-section-label">Approval</div>
                <ApprovalPanel incidentId={id} entityType="iap" entityId={String(selectedOp)} startLabel="Submit IAP for Approval" />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
