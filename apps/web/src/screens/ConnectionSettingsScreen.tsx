import { useState } from "react";
import { Link } from "react-router-dom";
import { getConnectCode, getDomain, setConnectCode, setDomain } from "../api/connection";

export default function ConnectionSettingsScreen() {
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
    <div className="screen">
      <h1>Connection Settings</h1>
      <p>
        By default this app talks to whatever server is already serving it ("internal" — a LAN server, an
        offline server, or a cloud server reached directly). Set a domain and connect code here only if you're
        opening this app from somewhere else and need to reach a specific incident's server through the public
        router.
      </p>
      <form onSubmit={save}>
        <div className="field">
          <label htmlFor="domain">Domain</label>
          <input
            id="domain"
            placeholder="e.g. sarapp.example.org"
            value={domain}
            onChange={(e) => setDomainValue(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="code">Connect Code</label>
          <input
            id="code"
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
      <p style={{ marginTop: 16 }}>
        <Link to="/login">Back to sign in</Link>
      </p>
    </div>
  );
}
