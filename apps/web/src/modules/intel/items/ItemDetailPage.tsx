import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import ExportButton from "../../forms/ExportButton";
import { useSession } from "../../../auth/SessionContext";
import { formatDateTime } from "../../../utils/formatDateTime";
import { useIntelLog } from "../hooks";
import ObservationDialog from "./ObservationDialog";
import { useAddObservation, useArchiveItem, useItemDetail } from "./hooks";

type Tab = "overview" | "observations" | "links" | "attachments" | "history";

export default function ItemDetailPage() {
  const { itemId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [addingObservation, setAddingObservation] = useState(false);

  const { data: item, isLoading, error } = useItemDetail(incidentId!, itemId!);
  const archiveItem = useArchiveItem(incidentId!);
  const addObservation = useAddObservation(incidentId!);
  const log = useIntelLog(incidentId!, { entity_id: itemId! });

  if (!incidentId) return null;
  if (isLoading) return <p>Loading intel item…</p>;
  if (error || !item) return <p className="error">Could not load this intel item.</p>;

  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "observations", label: `Observations (${item.observations.length})` },
    { key: "links", label: "Links" },
    { key: "attachments", label: "Attachments" },
    { key: "history", label: "History" },
  ];

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/intel/items")}>
        ← Intel Items
      </button>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <span style={{ opacity: 0.7 }}>{item.item_type}</span>
          <h2 style={{ margin: "2px 0 6px" }}>{item.title}</h2>
          <StatusPill domain="intel-priority" statusKey={item.priority} />{" "}
          <StatusPill domain="intel-confidence" statusKey={item.confidence} />{" "}
          <StatusPill domain="intel-trend" statusKey={item.trend} />
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {item.item_type === "Clue" && <ExportButton formId="sar_135" label="Export Clue Report (SAR 135)" />}
          <button style={{ width: "auto" }} onClick={() => setAddingObservation(true)}>
            + Observation
          </button>
        </div>
      </div>

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
            <output>{item.status}</output>
          </div>
          <div className="field">
            <label>Location</label>
            <output>{item.location_text || "—"}</output>
          </div>
          <div className="field">
            <label>Created By</label>
            <output>{item.created_by || "—"}</output>
          </div>
          <div className="field">
            <label>Updated</label>
            <output>{formatDateTime(item.updated_at)}</output>
          </div>
          {item.source_lead_id && (
            <p className="muted" style={{ fontSize: "0.82rem" }}>
              Source lead:{" "}
              <Link className="panel-link" to={`/intel/leads/${item.source_lead_id}`}>
                View Lead →
              </Link>
            </p>
          )}
          <div className="field" style={{ marginTop: 10 }}>
            <label>Notes</label>
            <output style={{ whiteSpace: "pre-wrap" }}>{item.notes || "No notes recorded."}</output>
          </div>
          <button
            className="danger"
            style={{ width: "auto", marginTop: 12 }}
            onClick={() => {
              if (window.confirm(`Archive "${item.title}"?`)) archiveItem.mutate(item.id, { onSuccess: () => navigate("/intel/items") });
            }}
          >
            Archive Item
          </button>
        </div>
      )}

      {tab === "observations" && (
        <div>
          {item.observations.length === 0 ? (
            <p className="entry-empty">No observations recorded yet.</p>
          ) : (
            [...item.observations].reverse().map((o) => (
              <div key={o.obs_id} className="command-panel" style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                  <strong>
                    Observed {formatDateTime(o.observed_at)} — {o.observer || "Unknown"}
                  </strong>
                  <span>
                    <StatusPill domain="intel-confidence" statusKey={o.confidence} />
                  </span>
                </div>
                <p style={{ margin: "6px 0" }}>{o.summary}</p>
                {o.detailed_notes && <p style={{ opacity: 0.8, fontSize: "0.86rem" }}>{o.detailed_notes}</p>}
                <p style={{ opacity: 0.6, fontSize: "0.8rem" }}>
                  {o.source_team ? `Source: ${o.source_team} · ` : ""}
                  {o.status ? `Status: ${o.status} · ` : ""}
                  {o.location_text ? `Location: ${o.location_text}` : ""}
                </p>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "links" && (
        <div>
          <h3>Linked Subjects</h3>
          {item.linked_subject_ids.length === 0 ? (
            <p className="entry-empty">No linked subjects.</p>
          ) : (
            item.linked_subject_ids.map((id) => (
              <p key={id}>
                <Link className="panel-link" to={`/intel/subjects/${id}`}>
                  View Subject {id} →
                </Link>
              </p>
            ))
          )}
          <h3>Linked Tasks</h3>
          {item.linked_task_ids.length === 0 ? (
            <p className="entry-empty">No linked tasks.</p>
          ) : (
            item.linked_task_ids.map((id) => (
              <p key={id}>
                <Link className="panel-link" to={`/ops/tasks/${id}`}>
                  View Task {id} →
                </Link>
              </p>
            ))
          )}
        </div>
      )}

      {tab === "attachments" && (
        <p className="entry-empty">
          No attachment storage exists yet for intel items — desktop's attachment picker writes to a local filesystem path with no
          server endpoint behind it, so this tab has nothing to show until that's built.
        </p>
      )}

      {tab === "history" && (
        <div>
          {log.isLoading ? (
            <p>Loading…</p>
          ) : (log.data ?? []).length === 0 ? (
            <p className="entry-empty">No history yet.</p>
          ) : (
            log.data!.map((e) => (
              <p key={e.id} style={{ fontSize: "0.86rem" }}>
                <span style={{ fontFamily: "monospace", opacity: 0.6 }}>{formatDateTime(e.timestamp)}</span> — {e.event_type}: {e.summary}
              </p>
            ))
          )}
        </div>
      )}

      {addingObservation && (
        <ObservationDialog
          itemTitle={item.title}
          busy={addObservation.isPending}
          onCancel={() => setAddingObservation(false)}
          onCreate={(body) =>
            addObservation.mutate(
              { itemId: item.id, body: { ...body, actor: user?.display_name } },
              { onSuccess: () => setAddingObservation(false) },
            )
          }
        />
      )}
    </div>
  );
}
