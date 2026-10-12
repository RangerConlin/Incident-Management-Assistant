import { useState } from "react";

interface NewOperationalPeriodDialogProps {
  onCreate: (body: { name: string; start_time: string; end_time: string }) => void;
  onCancel: () => void;
  busy?: boolean;
  error?: string | null;
}

export default function NewOperationalPeriodDialog({ onCreate, onCancel, busy, error }: NewOperationalPeriodDialogProps) {
  const [name, setName] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Operational Period</h3>
        <div className="field">
          <label htmlFor="op-name">Name (optional)</label>
          <input id="op-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Day 2 — Day Ops" />
        </div>
        <div className="field">
          <label htmlFor="op-start">Start Time</label>
          <input id="op-start" type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="op-end">End Time</label>
          <input id="op-end" type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
        </div>
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            disabled={!startTime || !endTime || busy}
            onClick={() => onCreate({ name, start_time: startTime, end_time: endTime })}
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
