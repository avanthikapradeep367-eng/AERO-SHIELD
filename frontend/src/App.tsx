import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import OverviewPage from "./pages/overview";
import DevicesPage from "./pages/devices";
import SimulateAttackPage from "./pages/simulate";
import AuthenticationPage from "./pages/authentication";
import EvidencePage from "./pages/evidence";
import ForensicsPage from "./pages/forensics";
import ThreatIntelligencePage from "./pages/threat-intelligence";
import AnalyticsPage from "./pages/analytics";
import TimelinePage from "./pages/timeline";
import SystemHealthPage from "./pages/system-health";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="simulate" element={<SimulateAttackPage />} />
        <Route path="authentication" element={<AuthenticationPage />} />
        <Route path="evidence" element={<EvidencePage />} />
        <Route path="forensics" element={<ForensicsPage />} />
        <Route path="threat-intelligence" element={<ThreatIntelligencePage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="system-health" element={<SystemHealthPage />} />
      </Route>
    </Routes>
  );
}

export default App;
