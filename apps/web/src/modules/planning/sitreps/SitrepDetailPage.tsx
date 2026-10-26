import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { useSession } from "../../../auth/SessionContext";
import {
  useCreateSitrepDistribution,
  useRefreshSitrep,
  useSitrepDetail,
  useSitrepDistributions,
  useUpdateSitrep,
} from "./hooks";

const STATUSES = ["draft", "ready_for_review", "needs_revision", "approved", "distributed", "archived"];
type Tab = "overview" | "sections" | "distributions";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "sections", label: "Sections" },
  { key: "distributions", label: "Distributions" },
];

export default function SitrepDetailPage() {
  const { sitrepId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [distRecipient, setDistRecipient] = useState("");

  const id = sitrepId!;
  const { data: sitrep, isLoading, error } = useSitrepDetail(incidentId!, id);
  const updateSitrep = useUpdateSitrep(incidentId!);
  const refreshSitrep = useRefreshSitrep(incidentId!);
  const { data: distributions = [] } = useSitrepDistributions(incidentId!, id);
  const createDistribution = useCreateSitrepDistribution(incidentId!, id);

  if (!incidentId) return null;
  if (isLoading) return <p>Loading situation report…</p>;
  if (error || !sitrep) return <p className="error">Could not load this situation report.</p>;

  const save = (body: Record<string, unknown>) => updateSitrep.mutate({ sitrepId: id, body });

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/command/sitreps")}>
        ← Situation Reports
      </button>
      <h2>SITREP #{sitrep.sitrep_number}</h2>

      <div className="detail-tabs">
        {TABS.map((t) => (
          <button key={t.key} className={`detail-tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="detail-header">
          <div className="field">
            <label>Status</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <StatusPill domain="sitrep" statusKey={sitrep.status} />
              <select value={sitrep.status} onChange={(e) => save({ status: e.target.value })}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="sitrep-prepared-by">Prepared By</label>
            <input
              id="sitrep-prepared-by"
              defaultValue={sitrep.prepared_by}
              onBlur={(e) => save({ prepared_by: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="sitrep-priority">Current Priority</label>
            <input
              id="sitrep-priority"
              defaultValue={sitrep.current_priority}
              onBlur={(e) => save({ current_priority: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="sitrep-tempo">Current Tempo</label>
            <select value={sitrep.current_tempo} onChange={(e) => save({ current_tempo: e.target.value })}>
              <option value="stable">Stable</option>
              <option value="increasing">Increasing</option>
              <option value="decreasing">Decreasing</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="sitrep-summary">Summary</label>
            <textarea
              id="sitrep-summary"
              defaultValue={sitrep.summary}
              onBlur={(e) => save({ summary: e.target.value })}
            />
          </div>
        </div>
      )}

      {tab === "sections" && (
        <div>
          <button
            style={{ width: "auto", marginBottom: 16 }}
            disabled={refreshSitrep.isPending}
            onClick={() => refreshSitrep.mutate(id)}
          >
            {refreshSitrep.isPending ? "Refreshing…" : "Refresh Auto-Filled Sections"}
          </button>
          {sitrep.sections.map((s) => (
            <div key={s.section_type} style={{ marginBottom: 20, borderBottom: "1px solid #2a2d33", paddingBottom: 16 }}>
              <h4 style={{ marginBottom: 6 }}>{s.title}</h4>
              {s.auto_content && (
                <div style={{ fontSize: "0.85rem", opacity: 0.65, marginBottom: 6, whiteSpace: "pre-wrap" }}>
                  Auto-filled: {s.auto_content}
                  {s.last_refreshed_at && ` (as of ${new Date(s.last_refreshed_at).toLocaleString()})`}
                </div>
              )}
              <textarea
                defaultValue={s.edited_content}
                placeholder="Override or add narrative for this section…"
                onBlur={(e) => {
                  const sections = sitrep.sections.map((sec) =>
                    sec.section_type === s.section_type ? { ...sec, edited_content: e.target.value } : sec
                  );
                  save({ sections });
                }}
              />
            </div>
          ))}
        </div>
      )}

      {tab === "distributions" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              style={{ maxWidth: 240 }}
              placeholder="Recipient group"
              value={distRecipient}
              onChange={(e) => setDistRecipient(e.target.value)}
            />
            <button
              style={{ width: "auto" }}
              disabled={!distRecipient.trim() || createDistribution.isPending}
              onClick={() =>
                createDistribution.mutate(
                  { recipient_group: distRecipient.trim(), distributed_by: user?.display_name },
                  { onSuccess: () => setDistRecipient("") }
                )
              }
            >
              Record Distribution
            </button>
          </div>
          {distributions.length === 0 ? (
            <p style={{ opacity: 0.6 }}>Not distributed yet.</p>
          ) : (
            distributions.map((d) => (
              <div key={d.id} className="list-item" style={{ cursor: "default" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{d.recipient_group}</div>
                  <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                    {d.delivery_method} · {d.distributed_by} · {new Date(d.distributed_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
