import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../auth/SessionContext";
import { ApiError } from "../api/client";

export default function LoginScreen() {
  const { login } = useSession();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen">
      <h1>SARApp</h1>
      <p>Sign in with your personnel ID.</p>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="username">Personnel ID</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign In"}
        </button>
      </form>
      <p style={{ marginTop: 16 }}>
        <Link to="/setup">First time here? Set up your account</Link>
      </p>
      <p>
        <Link to="/connection">Connection settings</Link>
      </p>
    </div>
  );
}
