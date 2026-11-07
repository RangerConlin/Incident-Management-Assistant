import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { SUBJECT_STATUSES } from "../../../api/endpoints";
import { useSession } from "../../../auth/SessionContext";
import { formatDateTime } from "../../../utils/formatDateTime";
import { useIntelLog } from "../hooks";
import { useArchiveSubject, useSubjectDetail, useUpdateSubject } from "./hooks";

type Tab = "overview" | "timeline" | "links" | "activity";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "timeline", label: "Timeline" },
  { key: "links", label: "Linked Records" },
  { key: "activity", label: "Activity Log" },
];

const PERSON_TYPES = new Set(["Missing Person", "Witness", "Reporting Party", "Contact", "Patient"]);

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="field">
      <label>{label}</label>
      <output>{value}</output>
    </div>
  );
}

export default function SubjectDetailPage() {
  const { subjectId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");

  const { data: subject, isLoading, error } = useSubjectDetail(incidentId!, subjectId!);
  const updateSubject = useUpdateSubject(incidentId!);
  const archiveSubject = useArchiveSubject(incidentId!);
  const log = useIntelLog(incidentId!, { entity_id: subjectId! });

  if (!incidentId) return null;
  if (isLoading) return <p>Loading subject…</p>;
  if (error || !subject) return <p className="error">Could not load this subject.</p>;

  const save = (body: Record<string, unknown>) => updateSubject.mutate({ subjectId: subject.id, body: { ...body, created_by: user?.display_name } });
  const isMissing = subject.subject_type === "Missing Person";
  const isPatient = subject.subject_type === "Patient";
  const isPerson = PERSON_TYPES.has(subject.subject_type);
  const isVehicle = subject.subject_type === "Vehicle";
  const isAircraft = subject.subject_type === "Aircraft";
  const hasIdentity = isMissing || isPatient;

  return (
    <div className="detail-page">
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/intel/subjects")}>
        ← Subjects
      </button>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ marginBottom: 4 }}>{subject.name}</h2>
          <span style={{ opacity: 0.7, marginRight: 8 }}>{subject.subject_type}</span>
          <StatusPill domain="intel-subject-status" statusKey={subject.status} />
        </div>
        <button
          className="danger"
          style={{ width: "auto" }}
          onClick={() => {
            if (window.confirm(`Archive ${subject.name}?`)) archiveSubject.mutate(subject.id, { onSuccess: () => navigate("/intel/subjects") });
          }}
        >
          Archive Profile
        </button>
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
            <select value={subject.status} onChange={(e) => save({ status: e.target.value })}>
              {SUBJECT_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          {hasIdentity && (
            <>
              <Row label="Age" value={subject.age} />
              <Row label="Sex" value={subject.sex} />
              <Row label="DOB" value={subject.dob} />
              <Row label="Race" value={subject.race} />
              <Row label="Height" value={subject.height} />
              <Row label="Weight" value={subject.weight} />
              <Row label="Hair Color" value={subject.hair_color} />
              <Row label="Eye Color" value={subject.eye_color} />
              <Row label="Distinguishing Features" value={subject.distinguishing_features} />
            </>
          )}

          {isPerson && (
            <>
              <Row label="Phone" value={subject.phone} />
              <Row label="Email" value={subject.email} />
              <Row label="Address" value={subject.address} />
              <Row label="Organization" value={subject.organization} />
              <Row label="Relationship to Incident" value={subject.relationship_to_incident} />
            </>
          )}

          {isMissing && (
            <>
              <Row label="Last Known Position" value={[subject.lkp_place, subject.lkp_time].filter(Boolean).join(" · ")} />
              <Row label="Point Last Seen" value={[subject.pls_place, subject.pls_time].filter(Boolean).join(" · ")} />
              <Row label="Clothing" value={subject.clothing_description} />
              <Row label="Equipment" value={subject.equipment_description} />
              <Row label="Vehicle Description" value={subject.vehicle_description} />
              <Row label="Outdoor Experience" value={subject.outdoor_experience} />
              <Row label="Behavioral Notes" value={subject.behavioral_notes} />
              <Row label="Communication Needs" value={subject.communication_needs} />
              <Row label="Sensory Considerations" value={subject.sensory_considerations} />
              <Row label="Routine Habits" value={subject.routine_habits} />
              <Row label="Wandering History" value={subject.wandering_history} />
              <Row label="Favorite Places" value={subject.favorite_places} />
              <Row label="Triggers/Stressors" value={subject.triggers_or_stressors} />
              <Row label="Recent Changes" value={subject.recent_changes} />
              <Row label="Medical Conditions" value={subject.medical_conditions} />
              <Row label="Medications" value={subject.medications} />
              <Row label="Mobility Limitations" value={subject.mobility_limitations} />
            </>
          )}

          {isPatient && (
            <>
              <Row label="Medical Conditions" value={subject.medical_conditions} />
              <Row label="Medications" value={subject.medications} />
              <Row label="Treatment Given" value={subject.treatment_given} />
              <Row label="Transport Required" value={subject.transport_required} />
              <Row label="Transport Method" value={subject.transport_method} />
              <Row label="Transport Destination" value={subject.transport_destination} />
              <Row label="Disposition" value={subject.disposition} />
            </>
          )}

          {isVehicle && (
            <>
              <Row label="Make" value={subject.make} />
              <Row label="Model" value={subject.model} />
              <Row label="Year" value={subject.year} />
              <Row label="Color" value={subject.color} />
              <Row label="License Plate" value={subject.plate} />
              <Row label="Plate State" value={subject.plate_state} />
              <Row label="VIN" value={subject.vin} />
              <Row label="Owner/Operator" value={subject.owner_or_operator} />
              <Row label="Description" value={subject.description} />
            </>
          )}

          {isAircraft && (
            <>
              <Row label="Tail Number" value={subject.tail_number} />
              <Row label="Aircraft Type" value={subject.aircraft_type} />
              <Row label="Make/Model" value={subject.make_model} />
              <Row label="Color/Markings" value={subject.color_markings} />
              <Row label="Pilot/Operator" value={subject.pilot_or_operator} />
              <Row label="Departure Point" value={subject.departure_point} />
              <Row label="Destination" value={subject.destination} />
              <Row label="Occupants" value={subject.occupants} />
              <Row label="Fuel Endurance" value={subject.fuel_endurance} />
              <Row label="ELT/Survival Gear" value={subject.elt_survival_gear} />
              <Row label="Route/Last Contact" value={subject.route_or_last_contact} />
              <Row label="Remarks" value={subject.remarks} />
            </>
          )}

          <div className="field">
            <label>Notes</label>
            <textarea key={`notes-${subject.notes}`} defaultValue={subject.notes ?? ""} onBlur={(e) => save({ notes: e.target.value })} />
          </div>
          <Row label="Created" value={formatDateTime(subject.created_at)} />
          <Row label="Updated" value={formatDateTime(subject.updated_at)} />
        </div>
      )}

      {tab === "timeline" && (
        <div>
          {log.isLoading ? (
            <p>Loading…</p>
          ) : (log.data ?? []).length === 0 ? (
            <p className="entry-empty">No timeline entries yet.</p>
          ) : (
            [...(log.data ?? [])].reverse().map((e) => (
              <p key={e.id} style={{ fontSize: "0.86rem" }}>
                <span style={{ fontFamily: "monospace", opacity: 0.6 }}>{formatDateTime(e.timestamp)}</span> — {e.summary}
              </p>
            ))
          )}
        </div>
      )}

      {tab === "links" && (
        <div>
          <h3>Linked Intel Items</h3>
          {subject.linked_item_ids.length === 0 ? (
            <p className="entry-empty">No linked intel items.</p>
          ) : (
            subject.linked_item_ids.map((id) => (
              <p key={id}>
                <Link className="panel-link" to={`/intel/items/${id}`}>
                  View Item {id} →
                </Link>
              </p>
            ))
          )}
          <h3>Linked Tasks</h3>
          {subject.linked_task_ids.length === 0 ? (
            <p className="entry-empty">No linked tasks.</p>
          ) : (
            subject.linked_task_ids.map((id) => (
              <p key={id}>
                <Link className="panel-link" to={`/ops/tasks/${id}`}>
                  View Task {id} →
                </Link>
              </p>
            ))
          )}
        </div>
      )}

      {tab === "activity" && (
        <div>
          {log.isLoading ? (
            <p>Loading…</p>
          ) : (log.data ?? []).length === 0 ? (
            <p className="entry-empty">No activity logged yet.</p>
          ) : (
            log.data!.map((e) => (
              <p key={e.id} style={{ fontSize: "0.86rem" }}>
                <span style={{ fontFamily: "monospace", opacity: 0.6 }}>{formatDateTime(e.timestamp)}</span> — {e.event_type}: {e.summary}
              </p>
            ))
          )}
        </div>
      )}
    </div>
  );
}
