import { useCallback, useEffect, useState } from "react";
import { Copy, Download, KeyRound, MonitorDown, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader, Panel } from "@/components/Page";
import { API, blobError, downloadFile, errMsg, fmtDateTime, useApi } from "@/lib/api";

const SERVER = API.replace(/\/api$/, "");
const NEEDS_AGENT = [
  "Full-desktop screenshots (browsers cannot capture the screen silently)",
  "Mouse / click / key activity counts across all applications, not only this tab",
  "Activity tracking while the ERM System tab is closed",
];

function Copyable({ text, testId }) {
  return (
    <div className="flex gap-2">
      <Input readOnly value={text} className="font-mono text-xs" data-testid={testId} />
      <Button size="icon" variant="outline" onClick={() => navigator.clipboard.writeText(text).then(() => toast.success("Copied"))} data-testid={`${testId}-copy`}><Copy className="h-4 w-4" /></Button>
    </div>
  );
}

export default function AgentPage() {
  const api = useApi();
  const [info, setInfo] = useState(null);
  const [token, setToken] = useState("");
  const load = useCallback(() => api.get("/me/agent").then((r) => setInfo(r.data)), [api]);
  useEffect(() => {
    load();
  }, [load]);
  const generate = async () => {
    try {
      setToken((await api.post("/me/agent-token")).data.token);
      load();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  const revoke = async () => {
    await api.delete("/me/agent-token");
    setToken("");
    toast.success("Agent token revoked");
    load();
  };
  const download = async () => {
    try {
      await downloadFile(api, "/agent/download", {}, "erm_agent.py");
    } catch (e) {
      toast.error(await blobError(e));
    }
  };
  const cmd = `python erm_agent.py --server ${SERVER} --token ${token || "<YOUR_TOKEN>"} --clock-in --clock-out-on-exit`;
  return (
    <div data-testid="agent-page">
      <PageHeader title="Desktop agent" subtitle="A small separately-installed program for full-desktop activity and screenshots." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Features that require the desktop agent" testId="agent-required-features">
          <ul className="space-y-2 text-sm text-muted-foreground">{NEEDS_AGENT.map((f) => <li key={f}>• {f}</li>)}</ul>
          <p className="mt-4 text-sm text-muted-foreground">Everything else (clock in/out, breaks, attendance, in-tab activity, reports) works in the browser without installing anything.</p>
          <p className="mt-3 text-sm">Screenshots for your account: <strong data-testid="agent-screenshot-state">{info?.screenshots_enabled ? "enabled by admin" : "disabled"}</strong></p>
        </Panel>
        <Panel title="1. Download & install" testId="agent-install-panel">
          <Button onClick={download} data-testid="download-agent-button"><Download className="mr-1 h-4 w-4" /> Download agent (Python)</Button>
          <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Install Python 3.9+ (Windows, macOS or Linux X11).</li>
            <li>Run <code className="rounded bg-background px-1 text-xs">pip install requests pynput mss pillow</code></li>
            <li>macOS: allow Screen Recording and Input Monitoring for your terminal.</li>
          </ol>
        </Panel>
        <Panel title="2. Connect with your personal token" testId="agent-token-panel">
          <p className="text-sm text-muted-foreground">
            {info?.has_token ? `Token created ${fmtDateTime(info.created_at)} · last used ${info.last_used_at ? fmtDateTime(info.last_used_at) : "never"}` : "No token yet."}
          </p>
          {token && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-amber-300">Copy it now - it will not be shown again.</p>
              <Copyable text={token} testId="agent-token-value" />
            </div>
          )}
          <div className="mt-4 flex gap-2">
            <Button onClick={generate} data-testid="generate-agent-token-button"><KeyRound className="mr-1 h-4 w-4" /> {info?.has_token ? "Replace token" : "Generate token"}</Button>
            {info?.has_token && <Button variant="outline" onClick={revoke} data-testid="revoke-agent-token-button"><Trash2 className="mr-1 h-4 w-4" /> Revoke</Button>}
          </div>
        </Panel>
        <Panel title="3. Run it" testId="agent-run-panel">
          <Copyable text={cmd} testId="agent-run-command" />
          <p className="mt-3 flex items-start gap-2 text-sm text-muted-foreground"><MonitorDown className="mt-0.5 h-4 w-4 shrink-0" /> The agent shows the monitoring notice, prints "MONITORING ACTIVE" each minute while tracking, and pauses automatically on breaks or after you clock out.</p>
        </Panel>
      </div>
    </div>
  );
}
