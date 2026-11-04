import { useState } from "react";
import { NavLink } from "react-router-dom";
import { UserButton } from "@clerk/react";
import {
  Activity, Building2, CalendarClock, Camera, FileClock, FileSpreadsheet, LayoutDashboard, Menu, MonitorDown,
  ScrollText, Settings, Sun, Upload, Users,
} from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useMe } from "@/context/MeContext";
import { ClockWidget, MonitoringBanner } from "@/components/ClockWidget";
import { NoticeDialog } from "@/components/NoticeDialog";
import { RoleBadge } from "@/components/StatusPill";
import { cn } from "@/lib/utils";

const ALL = ["admin", "manager", "employee"];
export const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "manager"], end: true },
  { to: "/my-day", label: "My day", icon: Sun, roles: ALL },
  { to: "/employees", label: "Employees", icon: Users, roles: ["admin", "manager"] },
  { to: "/departments", label: "Departments", icon: Building2, roles: ["admin"] },
  { to: "/import", label: "Bulk import", icon: Upload, roles: ["admin"] },
  { to: "/import/history", label: "Import history", icon: FileClock, roles: ["admin"] },
  { to: "/attendance", label: "Attendance", icon: CalendarClock, roles: ALL },
  { to: "/activity", label: "Activity", icon: Activity, roles: ALL },
  { to: "/screenshots", label: "Screenshots", icon: Camera, roles: ["admin", "manager"] },
  { to: "/reports", label: "Reports", icon: FileSpreadsheet, roles: ALL },
  { to: "/audit-logs", label: "Audit logs", icon: ScrollText, roles: ["admin"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: ["admin"] },
  { to: "/agent", label: "Desktop agent", icon: MonitorDown, roles: ALL },
];

function NavList({ onNavigate }) {
  const { me } = useMe();
  return (
    <nav className="flex flex-col gap-0.5">
      {NAV.filter((n) => n.roles.includes(me.role)).map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.end || n.to === "/import"}
          onClick={onNavigate}
          data-testid={`nav-${n.to.replace(/\//g, "-").replace(/^-/, "") || "dashboard"}`}
          className={({ isActive }) => cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150",
            isActive ? "bg-indigo-500/15 text-indigo-200" : "text-muted-foreground hover:bg-secondary hover:text-foreground",
          )}
        >
          <n.icon className="h-4 w-4" /> {n.label}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="px-3" data-testid="brand-logo">
      <div className="rounded-lg bg-white px-3 py-2">
        <img src="/logo.png" alt="Al Arabia - Arabian Contracting Services" className="h-auto w-full" />
      </div>
      <div className="mt-2 px-1 font-mono text-[11px] uppercase tracking-widest text-muted-foreground">WorkPulse</div>
    </div>
  );
}

export function AppShell({ children }) {
  const { me } = useMe();
  const [open, setOpen] = useState(false);
  return (
    <div className="grain min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r bg-card/60 py-5 lg:flex">
        <Brand />
        <div className="mt-6 flex-1 overflow-y-auto px-3 scrollbar-thin"><NavList /></div>
        <div className="mx-3 rounded-lg border bg-background/60 p-3 text-xs text-muted-foreground">
          <div className="truncate font-medium text-foreground" data-testid="sidebar-user-name">{me.full_name}</div>
          <div className="mt-1 flex items-center gap-2"><RoleBadge role={me.role} /><span className="font-mono">{me.employee_id}</span></div>
        </div>
      </aside>
      <div className="relative z-10 lg:pl-60">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between gap-3 border-b bg-background/80 px-4 backdrop-blur-md sm:px-6">
          <div className="flex items-center gap-2 lg:hidden">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" data-testid="mobile-nav-toggle"><Menu className="h-5 w-5" /></Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 bg-card p-0 pt-6">
                <Brand />
                <div className="mt-6 px-3"><NavList onNavigate={() => setOpen(false)} /></div>
              </SheetContent>
            </Sheet>
            <img src="/logo-mark.png" alt="Al Arabia" className="h-8 w-8 rounded-md bg-white p-0.5" data-testid="mobile-brand-logo" />
          </div>
          <div className="hidden text-sm text-muted-foreground lg:block">
            {new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:block"><ClockWidget prefix="header-" /></div>
            <UserButton />
          </div>
        </header>
        <main className="mx-auto max-w-[1400px] p-4 sm:p-6 lg:p-8">
          <div className="mb-4 sm:hidden"><ClockWidget prefix="mobile-" /></div>
          <MonitoringBanner />
          {children}
        </main>
      </div>
      <NoticeDialog />
    </div>
  );
}
