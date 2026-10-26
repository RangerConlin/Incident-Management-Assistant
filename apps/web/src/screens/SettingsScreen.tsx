import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { changePassword } from "../api/endpoints";
import { getConnectCode, getDomain, setConnectCode, setDomain } from "../api/connection";
import { useSession } from "../auth/SessionContext";
import { applyTheme, getStoredTheme } from "../styles/statusColors";

function ConnectionCard() {
  const [domain, setDomainValue] = useState(getDomain() ?? "");
  const [code, setCodeValue] = useState(getConnectCode() ?? "");
  const [saved, setSaved] = useState(false);

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    setDomain(domain || null);
    setConnectCode(code || null);
    setSaved(true);
    // Every request's target may have just changed — reload rather than try
    // to patch live state (auth, open queries, the WS) for a different server.
    window.location.reload();
  };

  const useInternal = () => {
    setDomainValue("");
    setCodeValue("");
    setDomain(null);
    setConnectCode(null);
    setSaved(true);
    window.location.reload();
  };

  return (
    <div className="settings-card">
      <h3>Connection</h3>
      <p className="desc">
        Where this client talks to — same-origin by default, or a domain and connect code for a remote
        LAN/cloud server.
      </p>
      <form onSubmit={save}>
        <div className="field">
          <label htmlFor="settings-domain">Domain</label>
          <input
            id="settings-domain"
            placeholder="e.g. sarapp.example.org"
            value={domain}
            onChange={(e) => setDomainValue(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="settings-code">Connect Code</label>
          <input
            id="settings-code"
            placeholder="e.g. ABCD-1234"
            value={code}
            onChange={(e) => setCodeValue(e.target.value)}
          />
        </div>
        {saved && <p className="error">Reloading…</p>}
        <button type="submit">Save &amp; Reload</button>
        <button type="button" className="secondary" onClick={useInternal}>
          Use Internal Connection (Default)
        </button>
      </form>
    </div>
  );
}

function ChangePasswordCard() {
  const { user } = useSession();
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
    <div className="settings-card">
      <h3>Change password</h3>
      <p className="desc">Applies to your personnel ID, {user?.display_name}, on this server.</p>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="settings-current-password">Current password</label>
          <input
            id="settings-current-password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="settings-new-password">New password</label>
          <input
            id="settings-new-password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="settings-confirm-password">Confirm new password</label>
          <input
            id="settings-confirm-password"
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
          {busy ? "Changing…" : "Update password"}
        </button>
      </form>
    </div>
  );
}

function AppearanceCard() {
  const [theme, setTheme] = useState(getStoredTheme());

  const choose = (next: "dark" | "light") => {
    applyTheme(next);
    setTheme(next);
  };

  return (
    <div className="settings-card">
      <h3>Appearance</h3>
      <p className="desc">Theme preference for this device.</p>
      <div className="settings-segmented">
        <button type="button" className={theme === "dark" ? "active" : ""} onClick={() => choose("dark")}>
          Dark
        </button>
        <button type="button" className={theme === "light" ? "active" : ""} onClick={() => choose("light")}>
          Light
        </button>
      </div>
    </div>
  );
}

export default function SettingsScreen() {
  const navigate = useNavigate();
  return (
    <div className="detail-page">
      <button type="button" className="settings-back" onClick={() => navigate(-1)}>
        ‹ Back
      </button>
      <h1 style={{ marginTop: 8, marginBottom: 0 }}>Settings</h1>
      <div className="settings-grid">
        <ConnectionCard />
        <ChangePasswordCard />
        <AppearanceCard />
      </div>
    </div>
  );
}
