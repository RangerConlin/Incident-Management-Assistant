import { Navigate, Route, Routes } from "react-router-dom";
import { useSession } from "./auth/SessionContext";
import { IncidentSocketProvider } from "./realtime/IncidentSocketProvider";
import AppShell from "./shell/AppShell";
import LoginScreen from "./screens/LoginScreen";
import AccountSetupScreen from "./screens/AccountSetupScreen";
import ConnectionSettingsScreen from "./screens/ConnectionSettingsScreen";
import TeamStatusBoardPage from "./modules/operations/teamStatus/TeamStatusBoardPage";
import TeamDetailPage from "./modules/operations/teamStatus/TeamDetailPage";
import TaskStatusBoardPage from "./modules/operations/taskStatus/TaskStatusBoardPage";
import TaskDetailPage from "./modules/operations/taskStatus/TaskDetailPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated } = useSession();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function RequireIncident({ children }: { children: JSX.Element }) {
  const { incidentId } = useSession();
  return incidentId ? children : <Navigate to="/" replace />;
}

function ShellWithSocket() {
  const { incidentId } = useSession();
  return (
    <IncidentSocketProvider incidentId={incidentId}>
      <AppShell />
    </IncidentSocketProvider>
  );
}

function IndexContent() {
  const { incidentId } = useSession();
  if (!incidentId) {
    return (
      <div className="screen">
        <p>Select an incident from the top bar to get started.</p>
      </div>
    );
  }
  return <Navigate to="/ops/teams" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/setup" element={<AccountSetupScreen />} />
      <Route path="/connection" element={<ConnectionSettingsScreen />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <ShellWithSocket />
          </RequireAuth>
        }
      >
        <Route index element={<IndexContent />} />
        <Route
          path="ops/teams"
          element={
            <RequireIncident>
              <TeamStatusBoardPage />
            </RequireIncident>
          }
        />
        <Route
          path="ops/teams/:teamId"
          element={
            <RequireIncident>
              <TeamDetailPage />
            </RequireIncident>
          }
        />
        <Route
          path="ops/tasks"
          element={
            <RequireIncident>
              <TaskStatusBoardPage />
            </RequireIncident>
          }
        />
        <Route
          path="ops/tasks/:taskId"
          element={
            <RequireIncident>
              <TaskDetailPage />
            </RequireIncident>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
