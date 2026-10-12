import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { lookupPerson, registerPerson, setPassword as apiSetPassword } from "../api/endpoints";

type Step = "lookup" | "register" | "password";

export default function AccountSetupScreen() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("lookup");
  const [personId, setPersonId] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPasswordValue] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const runLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await lookupPerson(personId.trim());
      if (res.status === "found") {
        setStep("password");
      } else if (res.status === "not_found") {
        setStep("register");
      } else {
        setError("Several personnel records share this ID. Ask an administrator to fix the roster.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lookup failed.");
    } finally {
      setBusy(false);
    }
  };

  const runRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await registerPerson(personId.trim(), firstName.trim(), lastName.trim());
      setStep("password");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create profile.");
    } finally {
      setBusy(false);
    }
  };

  const runSetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await apiSetPassword(personId.trim(), password);
      navigate("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not set password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen">
      <h1>Account Setup</h1>

      {step === "lookup" && (
        <form onSubmit={runLookup}>
          <p>Enter your personnel ID to get started.</p>
          <div className="field">
            <label htmlFor="person_id">Personnel ID</label>
            <input id="person_id" value={personId} onChange={(e) => setPersonId(e.target.value)} required />
          </div>
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={busy}>
            {busy ? "Checking…" : "Continue"}
          </button>
        </form>
      )}

      {step === "register" && (
        <form onSubmit={runRegister}>
          <p>We didn't find a personnel record for "{personId}". Create one:</p>
          <div className="field">
            <label htmlFor="first_name">First name</label>
            <input id="first_name" value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="last_name">Last name</label>
            <input id="last_name" value={lastName} onChange={(e) => setLastName(e.target.value)} required />
          </div>
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Continue"}
          </button>
        </form>
      )}

      {step === "password" && (
        <form onSubmit={runSetPassword}>
          <p>Choose a password for "{personId}".</p>
          <div className="field">
            <label htmlFor="new_password">Password</label>
            <input
              id="new_password"
              type="password"
              value={password}
              onChange={(e) => setPasswordValue(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="confirm_password">Confirm password</label>
            <input
              id="confirm_password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={busy}>
            {busy ? "Saving…" : "Finish Setup"}
          </button>
        </form>
      )}

      <p style={{ marginTop: 16 }}>
        <Link to="/login">Back to sign in</Link>
      </p>
    </div>
  );
}
