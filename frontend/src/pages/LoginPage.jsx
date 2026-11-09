import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "@/components/AuthLayout";
import { useMe } from "@/context/MeContext";
import api, { errMsg, saveTokens } from "@/lib/api";

export default function LoginPage() {
  const { me, reload } = useMe();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (me) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      saveTokens((await api.post("/auth/login", { email, password })).data);
      await reload();
      navigate("/", { replace: true });
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout testId="login-page">
      <h2 className="text-xl font-semibold">Sign in to ERM System</h2>
      <p className="mt-1 text-sm text-muted-foreground">Use your work email.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="email">Work email</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email-input" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password-input" />
        </div>
        {error && <p className="rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200" data-testid="login-error">{error}</p>}
        <Button type="submit" className="w-full" disabled={busy} data-testid="login-submit-button">{busy ? "Signing in…" : "Sign in"}</Button>
      </form>
      <p className="mt-5 text-xs text-muted-foreground">First time here or forgot your password? Ask your administrator for a login link.</p>
    </AuthLayout>
  );
}
