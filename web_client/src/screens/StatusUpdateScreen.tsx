import { useEffect, useState } from "react";
import { useSession } from "../auth/SessionContext";
import { ApiError } from "../api/client";
import { TEAM_STATUS_STEPS, getTeam, setTeamStatus } from "../api/endpoints";

export default function StatusUpdateScreen() {
  const { incidentId, checkin } = useSession();
  const teamId = checkin?.team_id ?? null;
  const [stepIndex, setStepIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!incidentId || !teamId) {
      setLoading(false);
      return;
    }
    getTeam(incidentId, teamId)
      .then((team) => {
        const idx = TEAM_STATUS_STEPS.findIndex((s) => s.label === team.status);
        if (idx >= 0) setStepIndex(idx);
      })
      .catch(() => {
        // Current status is informational only — default to the first step on failure.
      })
      .finally(() => setLoading(false));
  }, [incidentId, teamId]);

  const applyStatus = async (statusKey: string, nextIndex: number | null) => {
    if (!incidentId || !teamId) return;
    setError(null);
    setBusy(true);
    try {
      await setTeamStatus(incidentId, teamId, statusKey);
      if (nextIndex !== null) setStepIndex(nextIndex);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update status.");
    } finally {
      setBusy(false);
    }
  };

  if (!teamId) {
    return <p>You're not assigned to a team yet, so there's no status to update.</p>;
  }
  if (loading) return <p>Loading…</p>;

  const current = TEAM_STATUS_STEPS[stepIndex];
  const next = TEAM_STATUS_STEPS[stepIndex + 1];

  return (
    <div>
      <p>
        Current status: <strong>{current.label}</strong>
      </p>
      <button disabled={busy || !next} onClick={() => next && applyStatus(next.key, stepIndex + 1)}>
        {next ? `Advance to ${next.label}` : "Final Status Reached"}
      </button>
      <h3 style={{ marginTop: 24 }}>Special Status</h3>
      <button className="secondary" disabled={busy} onClick={() => applyStatus("discovery", null)}>
        Discovery
      </button>
      <button className="danger" disabled={busy} onClick={() => applyStatus("out of service", null)}>
        Out of Service
      </button>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
