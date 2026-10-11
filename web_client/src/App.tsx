import { Navigate, Route, Routes } from "react-router-dom";
import { useSession } from "./auth/SessionContext";
import { IncidentSocketProvider } from "./realtime/IncidentSocketProvider";
import AppShell from "./shell/AppShell";
import LoginScreen from "./screens/LoginScreen";
import AccountSetupScreen from "./screens/AccountSetupScreen";
import ConnectionSettingsScreen from "./screens/ConnectionSettingsScreen";
import SelectIncidentScreen from "./screens/SelectIncidentScreen";
import ChangePasswordScreen from "./screens/ChangePasswordScreen";
import TeamStatusBoardPage from "./modules/operations/teamStatus/TeamStatusBoardPage";
import TeamDetailPage from "./modules/operations/teamStatus/TeamDetailPage";
import TaskStatusBoardPage from "./modules/operations/taskStatus/TaskStatusBoardPage";
import TaskDetailPage from "./modules/operations/taskStatus/TaskDetailPage";
import PlanningDashboardPage from "./modules/planning/PlanningDashboardPage";
import ObjectivesBoardPage from "./modules/planning/objectives/ObjectivesBoardPage";
import ObjectiveDetailPage from "./modules/planning/objectives/ObjectiveDetailPage";
import OperationalPeriodsBoardPage from "./modules/planning/operationalPeriods/OperationalPeriodsBoardPage";
import OperationalPeriodDetailPage from "./modules/planning/operationalPeriods/OperationalPeriodDetailPage";
import MeetingsBoardPage from "./modules/planning/meetings/MeetingsBoardPage";
import MeetingDetailPage from "./modules/planning/meetings/MeetingDetailPage";
import SitrepsBoardPage from "./modules/planning/sitreps/SitrepsBoardPage";
import SitrepDetailPage from "./modules/planning/sitreps/SitrepDetailPage";
import WorkAssignmentsBoardPage from "./modules/planning/workAssignments/WorkAssignmentsBoardPage";
import WorkAssignmentDetailPage from "./modules/planning/workAssignments/WorkAssignmentDetailPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated } = useSession();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function RequireIncident({ children }: { children: JSX.Element }) {
  const { incidentId } = useSession();
  return incidentId ? children : <Navigate to="/select-incident" replace />;
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
  return <Navigate to={incidentId ? "/ops/teams" : "/select-incident"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/setup" element={<AccountSetupScreen />} />
      <Route path="/connection" element={<ConnectionSettingsScreen />} />
      <Route
        path="/select-incident"
        element={
          <RequireAuth>
            <SelectIncidentScreen />
          </RequireAuth>
        }
      />
      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePasswordScreen />
          </RequireAuth>
        }
      />
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
        <Route
          path="planning"
          element={
            <RequireIncident>
              <PlanningDashboardPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/objectives"
          element={
            <RequireIncident>
              <ObjectivesBoardPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/objectives/:objectiveId"
          element={
            <RequireIncident>
              <ObjectiveDetailPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/operational-periods"
          element={
            <RequireIncident>
              <OperationalPeriodsBoardPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/operational-periods/:periodId"
          element={
            <RequireIncident>
              <OperationalPeriodDetailPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/meetings"
          element={
            <RequireIncident>
              <MeetingsBoardPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/meetings/:meetingId"
          element={
            <RequireIncident>
              <MeetingDetailPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/sitreps"
          element={
            <RequireIncident>
              <SitrepsBoardPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/sitreps/:sitrepId"
          element={
            <RequireIncident>
              <SitrepDetailPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/work-assignments"
          element={
            <RequireIncident>
              <WorkAssignmentsBoardPage />
            </RequireIncident>
          }
        />
        <Route
          path="planning/work-assignments/:waId"
          element={
            <RequireIncident>
              <WorkAssignmentDetailPage />
            </RequireIncident>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
