import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
export type ConnectionStatus = "connected" | "connecting" | "disconnected";

const ConnectionStatusContext = createContext<ConnectionStatus>("disconnected");

interface IncidentMessage {
  collection: string;
  op: string;
  id: string;
  doc: unknown;
}

/**
 * Opens the incident's WebSocket and treats every message as a pure
 * invalidation signal: `queryClient.invalidateQueries(["incident", incidentId,
 * collection])` lets the owning query refetch and rejoin server-side, rather
 * than reconstructing the team/task join from the raw pushed document here.
 * Each module's query hooks set their own polling-floor `refetchInterval` —
 * this provider only handles the push side.
 */
export function IncidentSocketProvider({
  incidentId,
  children,
}: {
  incidentId: string | null;
  children: ReactNode;
}) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!incidentId) {
      setStatus("disconnected");
      return;
    }

    let cancelled = false;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/incidents/${incidentId}/ws`;

    setStatus("connecting");
    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => {
      if (!cancelled) setStatus("connected");
    };
    socket.onclose = () => {
      if (!cancelled) setStatus("disconnected");
    };
    socket.onerror = () => {
      if (!cancelled) setStatus("disconnected");
    };
    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as IncidentMessage;
        if (msg.collection) {
          queryClient.invalidateQueries({ queryKey: ["incident", incidentId, msg.collection] });
        }
      } catch {
        // non-JSON or unexpected payload — ignore, polling floor covers the gap
      }
    };

    return () => {
      cancelled = true;
      socket.close();
      socketRef.current = null;
    };
  }, [incidentId, queryClient]);

  return <ConnectionStatusContext.Provider value={status}>{children}</ConnectionStatusContext.Provider>;
}

export function useConnectionStatus(): ConnectionStatus {
  return useContext(ConnectionStatusContext);
}
