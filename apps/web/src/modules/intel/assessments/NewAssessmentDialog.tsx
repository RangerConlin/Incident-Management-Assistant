import { useState } from "react";
import { TextField } from "../IntelFormFields";

interface NewAssessmentDialogProps {
  onCreate: (body: Record<string, unknown>) => void;
  onCancel: () => void;
  busy?: boolean;
}

// Matches desktop's assessments_tab.py's _NewAssessmentDialog.
export default function NewAssessmentDialog({ onCreate, onCancel, busy }: NewAssessmentDialogProps) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [findings, setFindings] = useState("");
  const [recommendations, setRecommendations] = useState("");
  const [analyst, setAnalyst] = useState("");

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Assessment</h3>
        <TextField label="Title" value={title} onChange={setTitle} required placeholder="Assessment title (required)" />
        <TextField
          label="Summary"
          value={summary}
          onChange={setSummary}
          textarea
          placeholder="Brief analytical summary — what question or situation is this assessment addressing?"
        />
        <TextField label="Findings" value={findings} onChange={setFindings} textarea placeholder="What the available Intel records indicate" />
        <TextField
          label="Recommendations"
          value={recommendations}
          onChange={setRecommendations}
          textarea
          placeholder="Recommended actions or considerations for planning/command"
        />
        <TextField label="Analyst" value={analyst} onChange={setAnalyst} />
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            disabled={!title.trim() || busy}
            onClick={() =>
              onCreate({
                title: title.trim(),
                summary,
                findings,
                recommendations: recommendations || undefined,
                analyst,
              })
            }
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
