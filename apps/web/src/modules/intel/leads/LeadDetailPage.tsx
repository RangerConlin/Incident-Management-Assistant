import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { useSession } from "../../../auth/SessionContext";
import { formatDateTime } from "../../../utils/formatDateTime";
import AssignLeadDialog from "./AssignLeadDialog";
import { useAssignLead, useConvertLead, useLeadDetail } from "./hooks";

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="field">
      <label>{label}</label>
      <output>{value}</output>
    </div>
  );
}

// Matches desktop's lead_detail_window.py's LeadDetailWindow: one
// scrollable page, NO tabs (unlike Subject/Intel Item/Assessment detail) —
// that's the real window's own shape, not a simplification.
export default function LeadDetailPage() {
  const { leadId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [assigning, setAssigning] = useState(false);

  const { data: lead, isLoading, error } = useLeadDetail(incidentId!, leadId!);
  const assignLead = useAssignLead(incidentId!);
  const convertLead = useConvertLead(incidentId!);

  if (!incidentId) return null;
  if (isLoading) return <p>Loading lead…</p>;
  if (error || !lead) return <p className="error">Could not load this lead.</p>;

  const displayNumber = lead.lead_number ? `L-${String(lead.lead_number).padStart(3, "0")}` : "—";

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/intel/leads")}>
        ← Leads
      </button>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ marginBottom: 4 }}>
            {displayNumber} — {lead.title}
          </h2>
          <StatusPill domain="intel-priority" statusKey={lead.priority} />{" "}
          <StatusPill domain="intel-lead-status" statusKey={lead.status} />
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="secondary" style={{ width: "auto" }} onClick={() => setAssigning(true)}>
            Assign
          </button>
          <button
            style={{ width: "auto" }}
            disabled={lead.status === "Converted" || convertLead.isPending}
            onClick={() => convertLead.mutate({ lead, actor: user?.display_name }, { onSuccess: (item) => navigate(`/intel/items/${item.id}`) })}
          >
            → Convert to Item
          </button>
        </div>
      </div>

      <div className="command-panel" style={{ margin: "14px 0" }}>
        <h3>Summary</h3>
        <p>{lead.summary || "No summary recorded."}</p>
      </div>

      <div className="command-panel" style={{ marginBottom: 14 }}>
        <h3>Source Information</h3>
        <Row label="Source Category" value={lead.source_category} />
        <Row label="Agency" value={lead.source_agency} />
        <Row label="Representative" value={lead.source_contact_name} />
        <Row label="Role / Title" value={lead.source_role} />
        <Row label="Phone" value={lead.source_phone} />
        <Row label="Email" value={lead.source_email} />
        <Row label="Address" value={lead.source_address} />
        <Row label="Contact Method" value={lead.source_contact_method} />
        <Row label="Source Notes" value={lead.source_notes} />
        {lead.source_subject_id && (
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            Linked source subject:{" "}
            <Link className="panel-link" to={`/intel/subjects/${lead.source_subject_id}`}>
              View Subject →
            </Link>
          </p>
        )}
      </div>

      {(lead.source_reliability || lead.information_confidence) && (
        <div className="command-panel" style={{ marginBottom: 14 }}>
          <h3>Report Quality</h3>
          <Row label="Source Reliability" value={lead.source_reliability} />
          <Row label="Information Confidence" value={lead.information_confidence} />
        </div>
      )}

      <div className="command-panel" style={{ marginBottom: 14 }}>
        <h3>Location</h3>
        <p>{lead.location_text || "No location recorded."}</p>
      </div>

      <div className="command-panel" style={{ marginBottom: 14 }}>
        <h3>Assignment</h3>
        <Row label="Assigned To" value={lead.assigned_to || "Unassigned"} />
        <Row label="Status" value={lead.status} />
      </div>

      {lead.status === "Converted" && (
        <div className="command-panel" style={{ marginBottom: 14 }}>
          <h3>Conversion</h3>
          <p>
            Converted to {lead.converted_to_type || "an intel record"}.{" "}
            {lead.converted_to_id && lead.converted_to_type === "item" && (
              <Link className="panel-link" to={`/intel/items/${lead.converted_to_id}`}>
                View Item →
              </Link>
            )}
          </p>
        </div>
      )}

      <div className="command-panel">
        <h3>Notes</h3>
        <p>{lead.notes || "No notes recorded."}</p>
        <p className="muted" style={{ fontSize: "0.78rem", marginTop: 8 }}>
          Created {formatDateTime(lead.created_at)} · Updated {formatDateTime(lead.updated_at)}
        </p>
      </div>

      {assigning && (
        <AssignLeadDialog
          leadLabel={displayNumber}
          initialValue={lead.assigned_to ?? ""}
          onCancel={() => setAssigning(false)}
          onAssign={(name) => assignLead.mutate({ leadId: lead.id, name }, { onSuccess: () => setAssigning(false) })}
        />
      )}
    </div>
  );
}
