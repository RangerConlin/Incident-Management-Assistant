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

import CommandDashboardPage from "./modules/command/CommandDashboardPage";
import IncidentOverviewPage from "./modules/command/IncidentOverviewPage";
import IncidentOrganizationPage from "./modules/command/IncidentOrganizationPage";
import IapPackagesPage from "./modules/command/IapPackagesPage";
import IapPackageDetailPage from "./modules/command/IapPackageDetailPage";

import ResourceStatusBoardPage from "./modules/logistics/resourceStatus/ResourceStatusBoardPage";
import ResourceDetailPage from "./modules/logistics/resourceStatus/ResourceDetailPage";
import CheckInPage from "./modules/logistics/checkin/CheckInPage";

import PublicInformationLayout from "./modules/publicInformation/PublicInformationLayout";
import PioOverviewPage from "./modules/publicInformation/PioOverviewPage";
import ReleasesBoardPage from "./modules/publicInformation/ReleasesBoardPage";
import ReleaseDetailPage from "./modules/publicInformation/ReleaseDetailPage";
import RecordsBoardPage from "./modules/publicInformation/RecordsBoardPage";
import RecordDetailPage from "./modules/publicInformation/RecordDetailPage";

import LiaisonLayout from "./modules/liaison/LiaisonLayout";
import LiaisonOverviewPage from "./modules/liaison/LiaisonOverviewPage";
import LiaisonBoardPage from "./modules/liaison/LiaisonBoardPage";
import LiaisonDetailPage from "./modules/liaison/LiaisonDetailPage";
import AgencyContactPage from "./modules/liaison/AgencyContactPage";

import LogisticsDashboardPage from "./modules/logistics/LogisticsDashboardPage";
import ResourceRequestsBoardPage from "./modules/logistics/ResourceRequestsBoardPage";
import ResourceRequestDetailPage from "./modules/logistics/ResourceRequestDetailPage";
import FacilitiesBoardPage from "./modules/logistics/FacilitiesBoardPage";
import FacilityDetailPage from "./modules/logistics/FacilityDetailPage";

import CommsPlanPage from "./modules/communications/plan/CommsPlanPage";
import CommsLogPage from "./modules/communications/log/CommsLogPage";

import FormExportsPage from "./modules/forms/FormExportsPage";
import ApprovalsPage from "./modules/workspaces/ApprovalsPage";
import CertificationsPage from "./modules/workspaces/CertificationsPage";
import WeatherPage from "./modules/workspaces/WeatherPage";
import DemobilizationPage from "./modules/workspaces/DemobilizationPage";
import CustomizationPage from "./modules/workspaces/CustomizationPage";
import WorkspacePage from "./modules/workspaces/WorkspacePage";
import { WORKSPACES } from "./modules/workspaces/config";

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
        <Route path="forms" element={<RequireIncident><FormExportsPage /></RequireIncident>} />
        <Route path="planning/approvals" element={<RequireIncident><ApprovalsPage /></RequireIncident>} />
        <Route path="planning/demobilization" element={<RequireIncident><DemobilizationPage /></RequireIncident>} />
        <Route path="personnel/certifications" element={<RequireIncident><CertificationsPage /></RequireIncident>} />
        <Route path="weather" element={<RequireIncident><WeatherPage /></RequireIncident>} />
        <Route path="admin/ui-customization" element={<CustomizationPage />} />
        <Route path="logistics" element={<RequireIncident><LogisticsDashboardPage /></RequireIncident>} />
        <Route path="logistics/resource-requests" element={<RequireIncident><ResourceRequestsBoardPage /></RequireIncident>} />
        <Route path="logistics/resource-requests/:requestId" element={<RequireIncident><ResourceRequestDetailPage /></RequireIncident>} />
        <Route path="logistics/facilities" element={<RequireIncident><FacilitiesBoardPage /></RequireIncident>} />
        <Route path="logistics/facilities/:facilityId" element={<RequireIncident><FacilityDetailPage /></RequireIncident>} />
        <Route path="liaison" element={<RequireIncident><LiaisonLayout /></RequireIncident>}>
          <Route index element={<LiaisonOverviewPage />} />
          <Route path="agencies/:agencyId/contacts/new" element={<AgencyContactPage />} />
          <Route path=":section" element={<LiaisonBoardPage />} />
          <Route path=":section/:recordId" element={<LiaisonDetailPage />} />
        </Route>
        <Route path="pio" element={<RequireIncident><PublicInformationLayout /></RequireIncident>}>
          <Route index element={<PioOverviewPage />} />
          <Route path="releases" element={<ReleasesBoardPage />} />
          <Route path="releases/:releaseId" element={<ReleaseDetailPage />} />
          <Route path=":section" element={<RecordsBoardPage />} />
          <Route path=":section/:recordId" element={<RecordDetailPage />} />
        </Route>
        <Route path="command" element={<RequireIncident><CommandDashboardPage /></RequireIncident>} />
        <Route path="command/overview" element={<RequireIncident><IncidentOverviewPage /></RequireIncident>} />
        <Route path="command/organization" element={<RequireIncident><IncidentOrganizationPage /></RequireIncident>} />
        <Route path="command/iap" element={<RequireIncident><IapPackagesPage /></RequireIncident>} />
        <Route path="command/iap/:opNumber" element={<RequireIncident><IapPackageDetailPage /></RequireIncident>} />
        <Route path="command/sitreps" element={<RequireIncident><SitrepsBoardPage /></RequireIncident>} />
        <Route path="command/sitreps/:sitrepId" element={<RequireIncident><SitrepDetailPage /></RequireIncident>} />
        <Route path="comms/plan" element={<RequireIncident><CommsPlanPage /></RequireIncident>} />
        <Route path="comms/log" element={<RequireIncident><CommsLogPage /></RequireIncident>} />
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
          path="logistics/resources"
          element={
            <RequireIncident>
              <ResourceStatusBoardPage />
            </RequireIncident>
          }
        />
        <Route
          path="logistics/resources/:resourceType/:recordId"
          element={
            <RequireIncident>
              <ResourceDetailPage />
            </RequireIncident>
          }
        />
        <Route
          path="logistics/checkin"
          element={
            <RequireIncident>
              <CheckInPage />
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
        {WORKSPACES.map((w) => (
          <Route
            key={w.path}
            path={w.path.slice(1)}
            element={
              <RequireIncident>
                <WorkspacePage workspace={w} />
              </RequireIncident>
            }
          />
        ))}
        {WORKSPACES.map((w) => (
          <Route
            key={`${w.path}-dataset`}
            path={`${w.path.slice(1)}/:datasetKey/:recordId?`}
            element={
              <RequireIncident>
                <WorkspacePage workspace={w} />
              </RequireIncident>
            }
          />
        ))}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
