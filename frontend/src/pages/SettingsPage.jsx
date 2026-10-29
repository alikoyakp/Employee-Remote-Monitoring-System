import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader, Panel } from "@/components/Page";
import { errMsg, useApi } from "@/lib/api";

const FIELDS = [
  ["idle_threshold_min", "Idle threshold (minutes)", "No input for this long marks a person idle."],
  ["screenshot_interval_min", "Screenshot interval (minutes)", "Desktop agent capture frequency (default 60)."],
  ["screenshot_retention_days", "Screenshot retention (days)", "Older screenshots are deleted automatically."],
  ["activity_retention_days", "Activity data retention (days)", "Minute-level activity counts older than this are purged."],
  ["offline_after_min", "Offline after (minutes)", "No heartbeat for this long shows a person offline."],
  ["auto_close_after_min", "Auto-close missed logouts after (minutes)", "Open sessions with no heartbeat are closed at the last activity time."],
];

export default function SettingsPage() {
  const api = useApi();
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.get("/settings").then((r) => setS(r.data));
  }, [api]);
  const save = async () => {
    setBusy(true);
    try {
      const body = { ...s };
      FIELDS.forEach(([k]) => { body[k] = parseInt(body[k], 10) || 0; });
      setS((await api.put("/settings", body)).data);
      toast.success("Settings saved");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  const maintenance = async () => {
    try {
      const r = await api.post("/admin/maintenance");
      toast.success(`Closed ${r.data.sessions_auto_closed} session(s), expired ${r.data.screenshots_expired} screenshot(s)`);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  if (!s) return null;
  return (
    <div data-testid="settings-page">
      <PageHeader title="Settings" subtitle="Monitoring rules and data retention for the whole organisation.">
        <Button variant="outline" onClick={maintenance} data-testid="run-maintenance-button">Run cleanup now</Button>
        <Button onClick={save} disabled={busy} data-testid="save-settings-button">Save settings</Button>
      </PageHeader>
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Monitoring & retention">
          <div className="grid gap-4 sm:grid-cols-2">
            {FIELDS.map(([k, label, hint]) => (
              <div key={k} className="space-y-1.5">
                <Label className="text-xs">{label}</Label>
                <Input type="number" value={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.value })} data-testid={`setting-${k}`} />
                <p className="text-[11px] text-muted-foreground">{hint}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-muted-foreground">Cleanup runs automatically every 15 minutes. Screenshots are only captured for employees you enable on the Employees page (off by default).</p>
        </Panel>
        <Panel title="Employee monitoring notice">
          <Textarea rows={12} value={s.monitoring_notice} onChange={(e) => setS({ ...s, monitoring_notice: e.target.value })} data-testid="setting-monitoring-notice" />
          <p className="mt-2 text-xs text-muted-foreground">Every employee must acknowledge this notice on first sign-in. The desktop agent shows it before starting.</p>
        </Panel>
      </div>
    </div>
  );
}
