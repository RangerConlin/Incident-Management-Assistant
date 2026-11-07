import { Link, useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { ASSESSMENT_STATUSES } from "../../../api/endpoints";
import { useSession } from "../../../auth/SessionContext";
import { formatDateTime } from "../../../utils/formatDateTime";
import { useIntelLog } from "../hooks";
import { useAssessmentDetail, useUpdateAssessment } from "./hooks";

// Matches desktop's assessment_detail_window.py's AssessmentDetailWindow,
// but stacked as one scrollable page instead of 4 tabs — per your
// correction, an assessment's content is short enough that tabs added a
// click for no real benefit. Same sections (Overview/Findings &
// Recommendations/Linked Records/History), stacked panels in that order,
// same pattern as Lead Detail.
export default function AssessmentDetailPage() {
  const { assessmentId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();

  const { data: assessment, isLoading, error } = useAssessmentDetail(incidentId!, assessmentId!);
  const updateAssessment = useUpdateAssessment(incidentId!);
  const log = useIntelLog(incidentId!, { entity_id: assessmentId! });

  if (!incidentId) return null;
  if (isLoading) return <p>Loading assessment…</p>;
  if (error || !assessment) return <p className="error">Could not load this assessment.</p>;

  const save = (body: Record<string, unknown>) =>
    updateAssessment.mutate({ assessmentId: assessment.id, body: { ...body, actor: user?.display_name } });
  const displayNumber = assessment.assessment_number ? `A-${String(assessment.assessment_number).padStart(3, "0")}` : "—";

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/intel/assessments")}>
        ← Assessments
      </button>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ marginBottom: 4 }}>
            {displayNumber} — {assessment.title}
          </h2>
          <StatusPill domain="intel-assessment-status" statusKey={assessment.status} />
        </div>
      </div>

      <div className="command-panel" style={{ margin: "14px 0" }}>
        <h3>Overview</h3>
        <div className="field">
          <label>Status</label>
          <select value={assessment.status} onChange={(e) => save({ status: e.target.value })}>
            {ASSESSMENT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Analyst</label>
          <input key={`analyst-${assessment.analyst}`} defaultValue={assessment.analyst ?? ""} onBlur={(e) => save({ analyst: e.target.value.trim() })} />
        </div>
        <p className="muted" style={{ fontSize: "0.78rem" }}>
          Created {formatDateTime(assessment.created_at)} · Updated {formatDateTime(assessment.updated_at)}
        </p>
      </div>

      <div className="command-panel" style={{ marginBottom: 14 }}>
        <h3>Summary</h3>
        <textarea key={`summary-${assessment.summary}`} defaultValue={assessment.summary ?? ""} onBlur={(e) => save({ summary: e.target.value })} />
      </div>

      <div className="command-panel" style={{ marginBottom: 14 }}>
        <h3>Findings</h3>
        <textarea key={`findings-${assessment.findings}`} defaultValue={assessment.findings ?? ""} onBlur={(e) => save({ findings: e.target.value })} />
      </div>

      <div className="command-panel" style={{ marginBottom: 14 }}>
        <h3>Recommendations</h3>
        <textarea
          key={`recommendations-${assessment.recommendations}`}
          defaultValue={assessment.recommendations ?? ""}
          onBlur={(e) => save({ recommendations: e.target.value })}
        />
      </div>

      <div className="command-panel" style={{ marginBottom: 14 }}>
        <h3>Linked Records</h3>
        <h4>Linked Intel Items</h4>
        {assessment.linked_item_ids.length === 0 ? (
          <p className="entry-empty">No intel items linked.</p>
        ) : (
          assessment.linked_item_ids.map((id) => (
            <p key={id}>
              <Link className="panel-link" to={`/intel/items/${id}`}>
                View Item {id} →
              </Link>
            </p>
          ))
        )}
        <h4>Linked Subjects</h4>
        {assessment.linked_subject_ids.length === 0 ? (
          <p className="entry-empty">No subjects linked.</p>
        ) : (
          assessment.linked_subject_ids.map((id) => (
            <p key={id}>
              <Link className="panel-link" to={`/intel/subjects/${id}`}>
                View Subject {id} →
              </Link>
            </p>
          ))
        )}
      </div>

      <div className="command-panel">
        <h3>History</h3>
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
    </div>
  );
}
