import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { listTasksForAssignment } from "../../../api/endpoints";

interface TaskPickerDialogProps {
  incidentId: string;
  onPick: (taskId: number) => void;
  onCancel: () => void;
}

export default function TaskPickerDialog({ incidentId, onPick, onCancel }: TaskPickerDialogProps) {
  const [selected, setSelected] = useState<number | "">("");
  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ["incident", incidentId, "tasks", "for-assignment"],
    queryFn: () => listTasksForAssignment(incidentId),
  });

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Assign to a Task</h3>
        <p>This status tracks progress on a task — pick which one this team is working.</p>
        {isLoading ? (
          <p>Loading tasks…</p>
        ) : (
          <select value={selected} onChange={(e) => setSelected(Number(e.target.value))}>
            <option value="" disabled>
              Select a task…
            </option>
            {tasks.map((t) => (
              <option key={t.id} value={t.id}>
                {t.task_id} — {t.title}
              </option>
            ))}
          </select>
        )}
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button disabled={selected === ""} onClick={() => selected !== "" && onPick(selected)}>
            Assign
          </button>
        </div>
      </div>
    </div>
  );
}
