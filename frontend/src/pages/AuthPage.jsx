import { SignIn, SignUp } from "@clerk/react";
import { Activity, Camera, ShieldCheck } from "lucide-react";

const POINTS = [
  [Activity, "Attendance & activity", "Clock-in times, breaks, and active vs idle time from activity counts."],
  [Camera, "Opt-in screenshots", "Captured by the desktop agent only when an admin turns them on for your account."],
  [ShieldCheck, "Transparent by design", "No keystrokes or typed content are ever recorded. Every access is audit-logged."],
];

export default function AuthPage({ mode = "in" }) {
  return (
    <div className="grain flex min-h-screen bg-background">
      <div className="relative hidden w-[46%] flex-col justify-between overflow-hidden border-r bg-card p-12 lg:flex">
        <div className="absolute -left-24 top-1/3 h-72 w-72 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="relative w-56 rounded-xl bg-white px-4 py-3" data-testid="auth-brand-logo">
          <img src="/logo.png" alt="Al Arabia - Arabian Contracting Services" className="h-auto w-full" />
        </div>
        <div className="relative">
          <h1 className="font-heading text-4xl font-semibold leading-tight tracking-tight xl:text-5xl">Workforce visibility,<br />without the guesswork.</h1>
          <p className="mt-4 max-w-md text-muted-foreground">Attendance, activity and reporting for office and remote teams.</p>
          <ul className="mt-10 space-y-5">
            {POINTS.map(([Icon, t, d]) => (
              <li key={t} className="flex gap-3">
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-indigo-300" />
                <div><div className="font-medium">{t}</div><div className="text-sm text-muted-foreground">{d}</div></div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-muted-foreground">Access is limited to employees registered by your administrator.</p>
      </div>
      <div className="flex flex-1 flex-col items-center justify-center gap-6 p-4" data-testid={mode === "in" ? "sign-in-page" : "sign-up-page"}>
        <div className="w-44 rounded-xl bg-white px-3 py-2 lg:hidden"><img src="/logo.png" alt="Al Arabia" className="h-auto w-full" /></div>
        {mode === "in"
          ? <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" withSignUp />
          : <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" />}
      </div>
    </div>
  );
}
