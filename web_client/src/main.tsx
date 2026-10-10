import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import { SessionProvider } from "./auth/SessionContext";
import { applyTheme, getStoredTheme } from "./styles/statusColors";
import "./styles/statusColors.css";
import "./styles.css";

applyTheme(getStoredTheme());

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Operational data (teams/tasks) is short-stale by default; slow-moving
      // catalog data (incident list) overrides this per-query with a longer
      // staleTime where it's fetched.
      staleTime: 10_000,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <SessionProvider>
          <App />
        </SessionProvider>
      </HashRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
