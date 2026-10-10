import { Navigate, Route, Routes } from "react-router-dom";
import { useSession } from "./auth/SessionContext";
import LoginScreen from "./screens/LoginScreen";
import AccountSetupScreen from "./screens/AccountSetupScreen";
import IncidentSelectScreen from "./screens/IncidentSelectScreen";
import CheckInScreen from "./screens/CheckInScreen";
import HomeScreen from "./screens/HomeScreen";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated } = useSession();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function RequireIncident({ children }: { children: JSX.Element }) {
  const { incidentId } = useSession();
  return incidentId ? children : <Navigate to="/incidents" replace />;
}

function RequireCheckin({ children }: { children: JSX.Element }) {
  const { checkin } = useSession();
  return checkin?.checked_in ? children : <Navigate to="/checkin" replace />;
}

function RootRedirect() {
  const { isAuthenticated, incidentId, checkin } = useSession();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!incidentId) return <Navigate to="/incidents" replace />;
  if (!checkin?.checked_in) return <Navigate to="/checkin" replace />;
  return <Navigate to="/home" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/setup" element={<AccountSetupScreen />} />
      <Route
        path="/incidents"
        element={
          <RequireAuth>
            <IncidentSelectScreen />
          </RequireAuth>
        }
      />
      <Route
        path="/checkin"
        element={
          <RequireAuth>
            <RequireIncident>
              <CheckInScreen />
            </RequireIncident>
          </RequireAuth>
        }
      />
      <Route
        path="/home"
        element={
          <RequireAuth>
            <RequireIncident>
              <RequireCheckin>
                <HomeScreen />
              </RequireCheckin>
            </RequireIncident>
          </RequireAuth>
        }
      />
      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}
