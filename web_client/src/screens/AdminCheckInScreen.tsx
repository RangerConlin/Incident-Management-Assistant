import { useEffect, useState } from "react";
import { useSession } from "../auth/SessionContext";
import { ApiError } from "../api/client";
import { getRoster, patchCheckinStatus } from "../api/endpoints";
import type { RosterRow } from "../api/types";

export default function AdminCheckInScreen() {
  const { incidentId } = useSession();
  const [roster, setRoster] = useState<RosterRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const reload = () => {
    if (!incidentId) return;
    setLoading(true);
    getRoster(incidentId)
      .then(setRoster)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load roster."))
      .finally(() => setLoading(false));
  };

  useEffect(reload, [incidentId]);

  const toggle = async (row: RosterRow) => {
    if (!incidentId) return;
    setBusyId(row.person_record);
    setError(null);
    try {
      const nextStatus = row.checked_in ? "Demobilized" : "Available";
      await patchCheckinStatus(incidentId, row.person_record, nextStatus);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update check-in.");
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return <p>Loading roster…</p>;

  return (
    <div>
      {error && <p className="error">{error}</p>}
      {roster.length === 0 && <p>No one is on the roster yet.</p>}
      {roster.map((row) => (
        <div key={row.person_record} className="list-item" style={{ cursor: "default" }}>
          <div>
            <strong>{row.name}</strong>
            <div style={{ fontSize: "0.8rem", opacity: 0.8 }}>
              {row.role || "—"} · {row.team} · {row.status}
            </div>
          </div>
          <button
            className={row.checked_in ? "danger" : undefined}
            style={{ width: "auto" }}
            disabled={busyId === row.person_record}
            onClick={() => toggle(row)}
          >
            {row.checked_in ? "Check Out" : "Check In"}
          </button>
        </div>
      ))}
    </div>
  );
}
