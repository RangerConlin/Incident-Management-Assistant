import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getToken, setToken } from "../api/client";
import * as apiEndpoints from "../api/endpoints";
import type { PersonnelSummary, PublicUser } from "../api/types";

const SESSION_KEY = "sarapp.session";

interface StoredSession {
  user: PublicUser;
  personnel: PersonnelSummary | null;
  incidentId: string | null;
}

interface SessionState extends StoredSession {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  selectIncident: (incidentId: string | null) => void;
}

const SessionContext = createContext<SessionState | null>(null);

function loadStored(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

function saveStored(session: StoredSession | null) {
  try {
    if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    // localStorage unavailable (private browsing, etc.) — session just won't survive a reload.
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<PublicUser | null>(null);
  const [personnel, setPersonnel] = useState<PersonnelSummary | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) return;
    const stored = loadStored();
    if (stored) {
      setUser(stored.user);
      setPersonnel(stored.personnel);
      setIncidentId(stored.incidentId);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    saveStored({ user, personnel, incidentId });
  }, [user, personnel, incidentId]);

  const login = async (username: string, password: string) => {
    const res = await apiEndpoints.login(username, password);
    setToken(res.token);
    setUser(res.user);
    setPersonnel(res.personnel);
    setIncidentId(null);
  };

  const logout = () => {
    setToken(null);
    saveStored(null);
    setUser(null);
    setPersonnel(null);
    setIncidentId(null);
  };

  const value = useMemo<SessionState>(
    () => ({
      user: user as PublicUser,
      personnel,
      incidentId,
      isAuthenticated: Boolean(user),
      login,
      logout,
      selectIncident: setIncidentId,
    }),
    [user, personnel, incidentId]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
