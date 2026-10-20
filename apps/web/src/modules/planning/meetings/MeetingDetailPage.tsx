import FormExportControls from "../../forms/FormExportControls";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import StatusPill from "../../../components/table/StatusPill";
import { useSession } from "../../../auth/SessionContext";
import {
  useAddMeetingAttendee,
  useAddMeetingChecklistItem,
  useAddMeetingNote,
  useMeetingDetail,
  useRemoveMeetingAttendee,
  useUpdateMeeting,
  useUpdateMeetingAttendee,
  useUpdateMeetingChecklistItem,
} from "./hooks";

const STATUSES = ["draft", "scheduled", "ready", "completed", "canceled"];
type Tab = "overview" | "attendees" | "checklist" | "notes";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "attendees", label: "Attendees" },
  { key: "checklist", label: "Checklist" },
  { key: "notes", label: "Notes" },
];

export default function MeetingDetailPage() {
  const { meetingId } = useParams();
  const { incidentId, user } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [attendeeName, setAttendeeName] = useState("");
  const [checklistText, setChecklistText] = useState("");
  const [noteText, setNoteText] = useState("");
  const [noteCategory, setNoteCategory] = useState("");

  const id = Number(meetingId);
  const { data: meeting, isLoading, error } = useMeetingDetail(incidentId!, id);
  const updateMeeting = useUpdateMeeting(incidentId!);
  const addAttendee = useAddMeetingAttendee(incidentId!, id);
  const updateAttendee = useUpdateMeetingAttendee(incidentId!, id);
  const removeAttendee = useRemoveMeetingAttendee(incidentId!, id);
  const addChecklistItem = useAddMeetingChecklistItem(incidentId!, id);
  const updateChecklistItem = useUpdateMeetingChecklistItem(incidentId!, id);
  const addNote = useAddMeetingNote(incidentId!, id);

  if (!incidentId) return null;
  if (isLoading) return <p>Loading meeting…</p>;
  if (error || !meeting) return <p className="error">Could not load this meeting.</p>;

  const save = (body: Record<string, unknown>) => updateMeeting.mutate({ meetingId: id, body });

  return (
    <div className="detail-page">
      <FormExportControls formIds={["ics_230"]} sourceId={meetingId} />
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => navigate("/planning/meetings")}>
        ← Meetings
      </button>
      <h2>{meeting.title}</h2>

      <div className="detail-tabs">
        {TABS.map((t) => (
          <button key={t.key} className={`detail-tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label} {t.key === "attendees" && `(${meeting.attendees.length})`}
            {t.key === "checklist" && `(${meeting.checklist_items.filter((c) => c.is_complete).length}/${meeting.checklist_items.length})`}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="detail-header">
          <div className="field">
            <label>Status</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <StatusPill domain="meeting" statusKey={meeting.status} />
              <select value={meeting.status} onChange={(e) => save({ status: e.target.value })}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="meeting-title-field">Title</label>
            <input id="meeting-title-field" defaultValue={meeting.title} onBlur={(e) => save({ title: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="meeting-date-field">Date</label>
            <input
              id="meeting-date-field"
              type="date"
              defaultValue={meeting.meeting_date}
              onBlur={(e) => save({ meeting_date: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="meeting-start-field">Start</label>
            <input
              id="meeting-start-field"
              type="time"
              defaultValue={meeting.start_time}
              onBlur={(e) => save({ start_time: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="meeting-end-field">End</label>
            <input
              id="meeting-end-field"
              type="time"
              defaultValue={meeting.end_time}
              onBlur={(e) => save({ end_time: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="meeting-location-field">Location</label>
            <input
              id="meeting-location-field"
              defaultValue={meeting.location}
              onBlur={(e) => save({ location: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="meeting-owner-field">Owner</label>
            <input id="meeting-owner-field" defaultValue={meeting.owner} onBlur={(e) => save({ owner: e.target.value })} />
          </div>
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="meeting-notes-field">Freeform Notes</label>
            <textarea
              id="meeting-notes-field"
              defaultValue={meeting.freeform_notes}
              onBlur={(e) => save({ freeform_notes: e.target.value })}
            />
          </div>
        </div>
      )}

      {tab === "attendees" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              style={{ maxWidth: 220 }}
              placeholder="Name"
              value={attendeeName}
              onChange={(e) => setAttendeeName(e.target.value)}
            />
            <button
              style={{ width: "auto" }}
              disabled={!attendeeName.trim() || addAttendee.isPending}
              onClick={() =>
                addAttendee.mutate(
                  { display_name: attendeeName.trim() },
                  { onSuccess: () => setAttendeeName("") }
                )
              }
            >
              Add Attendee
            </button>
          </div>
          {meeting.attendees.length === 0 ? (
            <p style={{ opacity: 0.6 }}>No attendees yet.</p>
          ) : (
            meeting.attendees.map((a, i) => {
              // Some older meetings were seeded with sub-items that never
              // got an `id` assigned (legacy data, not a template-created
              // row) -- those can't be addressed by the attendee/{id}
              // endpoints, so edits are disabled for them rather than
              // silently sending a broken `null` id to the API.
              const attendeeId = a.id;
              return (
                <div key={attendeeId ?? `unindexed-${i}`} className="list-item" style={{ cursor: "default" }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>{a.display_name}</div>
                    <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                      {a.role || a.attendee_type} · {a.requirement_status}
                      {attendeeId == null && " · read-only (legacy record, no id)"}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <select
                      value={a.attendance_status}
                      disabled={attendeeId == null}
                      onChange={(e) =>
                        attendeeId != null &&
                        updateAttendee.mutate({ attendeeId, body: { attendance_status: e.target.value } })
                      }
                    >
                      <option value="invited">Invited</option>
                      <option value="confirmed">Confirmed</option>
                      <option value="attended">Attended</option>
                      <option value="no-show">No-show</option>
                    </select>
                    <button
                      className="secondary"
                      style={{ width: "auto" }}
                      disabled={attendeeId == null}
                      onClick={() => attendeeId != null && removeAttendee.mutate(attendeeId)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {tab === "checklist" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              style={{ maxWidth: 320 }}
              placeholder="Checklist item"
              value={checklistText}
              onChange={(e) => setChecklistText(e.target.value)}
            />
            <button
              style={{ width: "auto" }}
              disabled={!checklistText.trim() || addChecklistItem.isPending}
              onClick={() =>
                addChecklistItem.mutate({ text: checklistText.trim() }, { onSuccess: () => setChecklistText("") })
              }
            >
              Add Item
            </button>
          </div>
          {meeting.checklist_items.length === 0 ? (
            <p style={{ opacity: 0.6 }}>No checklist items yet.</p>
          ) : (
            meeting.checklist_items.map((c, i) => {
              // See the attendees tab above for why some legacy items have
              // no addressable id.
              const itemId = c.id;
              return (
                <div key={itemId ?? `unindexed-${i}`} className="list-item" style={{ cursor: "default" }}>
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      cursor: itemId != null ? "pointer" : "default",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={c.is_complete}
                      disabled={itemId == null}
                      onChange={(e) =>
                        itemId != null &&
                        updateChecklistItem.mutate({ itemId, body: { is_complete: e.target.checked } })
                      }
                    />
                    <span style={{ textDecoration: c.is_complete ? "line-through" : "none", opacity: c.is_complete ? 0.6 : 1 }}>
                      {c.text}
                    </span>
                    {itemId == null && (
                      <span style={{ fontSize: "0.78rem", opacity: 0.5 }}>(legacy record, read-only)</span>
                    )}
                  </label>
                  {c.assigned_to && <span style={{ fontSize: "0.85rem", opacity: 0.7 }}>{c.assigned_to}</span>}
                </div>
              );
            })
          )}
        </div>
      )}

      {tab === "notes" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              style={{ maxWidth: 140 }}
              placeholder="Category"
              value={noteCategory}
              onChange={(e) => setNoteCategory(e.target.value)}
            />
            <input
              style={{ flex: 1 }}
              placeholder="Note"
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
            />
            <button
              style={{ width: "auto" }}
              disabled={!noteText.trim() || addNote.isPending}
              onClick={() =>
                addNote.mutate(
                  { category: noteCategory.trim(), text: noteText.trim(), author: user?.display_name },
                  { onSuccess: () => setNoteText("") }
                )
              }
            >
              Add Note
            </button>
          </div>
          {meeting.structured_notes.length === 0 ? (
            <p style={{ opacity: 0.6 }}>No structured notes yet.</p>
          ) : (
            meeting.structured_notes.map((n) => (
              <div key={n.id} className="list-item" style={{ cursor: "default" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {n.category ? `[${n.category}] ` : ""}
                    {n.text}
                  </div>
                  <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                    {n.author} · {new Date(n.timestamp).toLocaleString()} · {n.routing_status}
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
