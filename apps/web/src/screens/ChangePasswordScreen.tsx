import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { changePassword } from "../api/endpoints";
import { useSession } from "../auth/SessionContext";

export default function ChangePasswordScreen() {
  const { user } = useSession();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation don't match.");
      return;
    }
    setBusy(true);
    try {
      await changePassword(user.username, currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen">
      <h1>Change Password</h1>
      <p>Signed in as {user?.display_name}.</p>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="current-password">Current password</label>
          <input
            id="current-password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="new-password">New password</label>
          <input
            id="new-password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="confirm-password">Confirm new password</label>
          <input
            id="confirm-password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        {error && <p className="error">{error}</p>}
        {success && <p style={{ color: "#4caf50" }}>Password changed.</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Changing…" : "Change Password"}
        </button>
      </form>
      <button className="secondary" style={{ marginTop: 8 }} onClick={() => navigate(-1)}>
        Back
      </button>
    </div>
  );
}
