import { useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { useSession } from "../../../auth/SessionContext";
import { usePatchCheckin, useSetCheckinStatus } from "../checkin/hooks";
import { RESOURCE_STATUS_OPTIONS, useCheckInResource, useCheckOutResource, useResourceStatusDetail } from "./hooks";

export default function ResourceDetailPage() {
  const { resourceType, recordId } = useParams();
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const isPersonnel = resourceType === "personnel";

  const { data: resource, isLoading, error } = useResourceStatusDetail(incidentId!, resourceType!, recordId!);
  const checkIn = useCheckInResource(incidentId!);
  const checkOut = useCheckOutResource(incidentId!);
  const setPersonnelStatus = useSetCheckinStatus(incidentId!);
  const patchPersonnel = usePatchCheckin(incidentId!);

  if (!incidentId) return null;
  if (isLoading) return <p>Loading resource…</p>;
  if (error || !resource) return <p className="error">Could not load this resource.</p>;

  // Personnel check-in/edit lives behind /checkin/{person_record}, not the
  // generic /resources/{type}/{id} endpoint (that one explicitly rejects
  // resource_type="personnel" — see incident_resources.py).
  const save = (overrides: Record<string, unknown>) => {
    if (isPersonnel) {
      const personRecord = Number(recordId);
      if ("status" in overrides) {
        setPersonnelStatus.mutate({ personRecord, status: String(overrides.status) });
      } else {
        patchPersonnel.mutate({ personRecord, body: overrides });
      }
      return;
    }
    checkIn.mutate({ resourceType: resourceType!, recordId: recordId!, overrides });
  };

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/logistics/resources")}>
        ← Resource Status Board
      </button>
      <h2>
        {resource.resource_name} — {resource.resource_type}
      </h2>

      <div className="detail-header">
        <div className="field">
          <label>Status</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <StatusPill domain="resource" statusKey={resource.status} />
            <select value="" onChange={(e) => e.target.value && save({ status: e.target.value })}>
              <option value="">Change status…</option>
              {RESOURCE_STATUS_OPTIONS.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="field">
          <label>Assigned To</label>
          <input value={resource.assigned_to ?? "—"} readOnly />
        </div>
        <div className="field">
          <label>Location</label>
          <input defaultValue={resource.location ?? ""} onBlur={(e) => save({ location: e.target.value })} />
        </div>
        <div className="field">
          <label>ETA</label>
          <input
            type="datetime-local"
            defaultValue={resource.eta_utc ? resource.eta_utc.slice(0, 16) : ""}
            onBlur={(e) => save({ eta_utc: e.target.value ? new Date(e.target.value).toISOString() : null })}
          />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Notes</label>
          <textarea defaultValue={resource.notes ?? ""} onBlur={(e) => save({ notes: e.target.value })} />
        </div>
      </div>

      <h3>Status History</h3>
      <div className="message-list" style={{ maxHeight: 220 }}>
        {[...(resource.status_log ?? [])].reverse().map((entry, i) => (
          <div key={i} className="message">
            <div className="meta">
              {entry.changed_by} · {new Date(entry.timestamp).toLocaleString()}
            </div>
            {entry.status}
          </div>
        ))}
        {(!resource.status_log || resource.status_log.length === 0) && (
          <p style={{ opacity: 0.6 }}>No status history yet.</p>
        )}
      </div>

      <button
        className="secondary"
        style={{ width: "auto", marginTop: 16 }}
        disabled={checkOut.isPending}
        onClick={() =>
          checkOut.mutate(
            { resourceType: resourceType!, recordId: recordId! },
            { onSuccess: () => navigate("/logistics/resources") }
          )
        }
      >
        Check Out
      </button>
    </div>
  );
}
