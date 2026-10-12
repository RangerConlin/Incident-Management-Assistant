import { useState } from "react";
import type { MeetingTemplate } from "../../../api/types";
import { useMeetingTemplates } from "./hooks";

interface NewMeetingDialogProps {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}

export default function NewMeetingDialog({ onCreate, onCancel, busy }: NewMeetingDialogProps) {
  const { data: templates = [] } = useMeetingTemplates();
  const [templateSlug, setTemplateSlug] = useState("");
  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [location, setLocation] = useState("");
  const [owner, setOwner] = useState("");

  const applyTemplate = (slug: string) => {
    setTemplateSlug(slug);
    const tpl = templates.find((t: MeetingTemplate) => t.slug === slug);
    if (tpl && !title) setTitle(tpl.name);
  };

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Meeting</h3>
        <div className="field">
          <label htmlFor="meeting-template">Template (optional)</label>
          <select id="meeting-template" value={templateSlug} onChange={(e) => applyTemplate(e.target.value)}>
            <option value="">None</option>
            {templates.map((t: MeetingTemplate) => (
              <option key={t.slug} value={t.slug}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="meeting-title">Title</label>
          <input id="meeting-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="meeting-date">Date</label>
          <input id="meeting-date" type="date" value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="meeting-start">Start Time</label>
          <input id="meeting-start" type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="meeting-location">Location</label>
          <input id="meeting-location" value={location} onChange={(e) => setLocation(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="meeting-owner">Owner</label>
          <input id="meeting-owner" value={owner} onChange={(e) => setOwner(e.target.value)} />
        </div>
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            disabled={!title.trim() || busy}
            onClick={() =>
              onCreate({
                template_id: templateSlug || undefined,
                title: title.trim(),
                meeting_date: meetingDate,
                start_time: startTime,
                location,
                owner,
                status: "draft",
              })
            }
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
