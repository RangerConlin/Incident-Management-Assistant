import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../auth/SessionContext";
import { ApiError } from "../api/client";
import { fetchCheckin, getCheckinTeams, saveCheckin } from "../api/endpoints";
import type { TeamOption } from "../api/types";

const APP_ROLES = ["Command Staff", "Field User"] as const;

export default function CheckInScreen() {
  const { incidentId, personnel, checkin, setCheckin } = useSession();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState<TeamOption[]>([]);
  const [role, setRole] = useState<string>(APP_ROLES[1]);
  const [teamId, setTeamId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const personRecord = personnel?.person_record ?? null;

  useEffect(() => {
    if (!incidentId) {
      navigate("/incidents");
      return;
    }
    if (!personRecord) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const existing = await fetchCheckin(incidentId, personRecord);
        if (existing && existing.checked_in) {
          setCheckin(existing);
          navigate("/home");
          return;
        }
        const teamOptions = await getCheckinTeams(incidentId);
        setTeams(teamOptions);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not load check-in options.");
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId, personRecord]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incidentId || !personRecord) return;
    setError(null);
    setBusy(true);
    try {
      const saved = await saveCheckin(incidentId, personRecord, {
        status: "Available",
        role_on_team: role,
        team_id: role === "Field User" ? teamId || null : null,
        location: "ICP",
      });
      setCheckin(saved);
      navigate("/home");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Check-in failed.");
    } finally {
      setBusy(false);
    }
  };

  if (!personRecord) {
    return (
      <div className="screen">
        <p className="error">
          Your account isn't linked to a personnel record, so you can't check in. Contact an administrator.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="screen">
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="screen">
      <h2>Check In</h2>
      {checkin && <p>Checked in as {checkin.role_on_team}.</p>}
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="role">Role</label>
          <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
            {APP_ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        {role === "Field User" && (
          <div className="field">
            <label htmlFor="team">Team</label>
            <select id="team" value={teamId} onChange={(e) => setTeamId(e.target.value)} required>
              <option value="" disabled>
                Select a team…
              </option>
              {teams.map((t) => (
                <option key={t.team_id} value={t.team_id}>
                  {t.team_name}
                </option>
              ))}
            </select>
          </div>
        )}
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Checking in…" : "Check In"}
        </button>
      </form>
    </div>
  );
}
