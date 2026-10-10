import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built output is served by the shared FastAPI app (data/db/sarapp_db/api/app.py)
// as static files mounted at /app, so every asset URL must be rooted there —
// both in the production build and in dev, where this file's proxy below
// forwards API calls to a separately running backend.
const BACKEND_PROXY_TARGET = process.env.VITE_BACKEND_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    proxy: {
      // ws: true so the incident WebSocket (/api/incidents/{id}/ws) proxies
      // too, not just plain HTTP — see realtime/IncidentSocketProvider.tsx.
      "/api": { target: BACKEND_PROXY_TARGET, ws: true },
      "/health": BACKEND_PROXY_TARGET,
      "/server-info": BACKEND_PROXY_TARGET,
    },
  },
});
