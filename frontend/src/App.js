import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { MeProvider, useMe } from "@/context/MeContext";
import { TrackerProvider } from "@/context/TrackerContext";
import { AppShell } from "@/components/AppShell";
import LoginPage from "@/pages/LoginPage";
import SetPasswordPage from "@/pages/SetPasswordPage";
import Dashboard from "@/pages/Dashboard";
import MyDay from "@/pages/MyDay";
import Employees from "@/pages/Employees";
import Departments from "@/pages/Departments";
import ImportPage from "@/pages/ImportPage";
import ImportHistory from "@/pages/ImportHistory";
import Attendance from "@/pages/Attendance";
import ActivityPage from "@/pages/ActivityPage";
import Screenshots from "@/pages/Screenshots";
import Reports from "@/pages/Reports";
import AuditLogs from "@/pages/AuditLogs";
import SettingsPage from "@/pages/SettingsPage";
import AgentPage from "@/pages/AgentPage";

function Guard({ roles, children }) {
  const { me } = useMe();
  return roles.includes(me.role) ? children : <Navigate to="/my-day" replace />;
}

const AM = ["admin", "manager"];
const A = ["admin"];

function Gate() {
  const { me, error, reload } = useMe();
  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center" data-testid="app-load-error">
        <p className="text-sm text-muted-foreground">Could not reach the server: {String(error)}</p>
        <Button variant="outline" onClick={reload}>Try again</Button>
      </div>
    );
  }
  if (me === null) {
    return <div className="flex min-h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-indigo-400" /></div>;
  }
  if (me === false) return <Navigate to="/login" replace />;
  return (
    <TrackerProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={me.role === "employee" ? <Navigate to="/my-day" replace /> : <Dashboard />} />
          <Route path="/my-day" element={<MyDay />} />
          <Route path="/employees" element={<Guard roles={AM}><Employees /></Guard>} />
          <Route path="/departments" element={<Guard roles={A}><Departments /></Guard>} />
          <Route path="/import" element={<Guard roles={A}><ImportPage /></Guard>} />
          <Route path="/import/history" element={<Guard roles={A}><ImportHistory /></Guard>} />
          <Route path="/attendance" element={<Attendance />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/screenshots" element={<Guard roles={AM}><Screenshots /></Guard>} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/audit-logs" element={<Guard roles={A}><AuditLogs /></Guard>} />
          <Route path="/settings" element={<Guard roles={A}><SettingsPage /></Guard>} />
          <Route path="/agent" element={<AgentPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </TrackerProvider>
  );
}

export default function App() {
  return (
    <div className="dark">
      <BrowserRouter>
        <MeProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/sign-in/*" element={<Navigate to="/login" replace />} />
            <Route path="/set-password" element={<SetPasswordPage />} />
            <Route path="/*" element={<Gate />} />
          </Routes>
        </MeProvider>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" richColors />
    </div>
  );
}
