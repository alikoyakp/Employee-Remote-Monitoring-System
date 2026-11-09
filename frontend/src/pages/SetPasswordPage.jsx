import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthLayout } from "@/components/AuthLayout";
import { useMe } from "@/context/MeContext";
import api, { errMsg, saveTokens } from "@/lib/api";

export default function SetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const { reload } = useMe();
  const navigate = useNavigate();
  const [info, setInfo] = useState(null);
  const [linkError, setLinkError] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/auth/link-info", { params: { token } }).then((r) => setInfo(r.data)).catch((e) => setLinkError(errMsg(e)));
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (pw !== pw2) return setError("Passwords do not match");
    setBusy(true);
    setError("");
    try {
      saveTokens((await api.post("/auth/set-password", { token, password: pw })).data);
      await reload();
      navigate("/", { replace: true });
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout testId="set-password-page">
      <h2 className="text-xl font-semibold">Set your password</h2>
      {linkError && (
        <div className="mt-4 space-y-4">
          <p className="rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200" data-testid="set-password-link-error">{linkError}</p>
          <Link to="/login" className="text-sm text-indigo-300">Back to sign in</Link>
        </div>
      )}
      {info && (
        <form onSubmit={submit} className="mt-4 space-y-4">
          <p className="text-sm text-muted-foreground" data-testid="set-password-account">{info.full_name} · {info.email}</p>
          <div className="space-y-1.5">
            <Label htmlFor="pw">New password</Label>
            <Input id="pw" type="password" autoComplete="new-password" required value={pw} onChange={(e) => setPw(e.target.value)} data-testid="set-password-input" />
            <p className="text-[11px] text-muted-foreground">At least 8 characters, including a number or symbol.</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pw2">Confirm password</Label>
            <Input id="pw2" type="password" autoComplete="new-password" required value={pw2} onChange={(e) => setPw2(e.target.value)} data-testid="set-password-confirm-input" />
          </div>
          {error && <p className="rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200" data-testid="set-password-error">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy} data-testid="set-password-submit-button">{busy ? "Saving…" : "Save and sign in"}</Button>
        </form>
      )}
    </AuthLayout>
  );
}
