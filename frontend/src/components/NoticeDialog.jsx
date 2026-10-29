import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useMe } from "@/context/MeContext";
import { errMsg, useApi } from "@/lib/api";
import { toast } from "sonner";

export function NoticeDialog() {
  const { me, reload } = useMe();
  const api = useApi();
  const [busy, setBusy] = useState(false);
  if (me.notice_acknowledged_at) return null;
  const ack = async () => {
    setBusy(true);
    try {
      await api.post("/me/acknowledge-notice");
      await reload();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open>
      <DialogContent className="max-w-lg [&>button]:hidden" onInteractOutside={(e) => e.preventDefault()} onEscapeKeyDown={(e) => e.preventDefault()} data-testid="monitoring-notice-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-emerald-400" /> Employee monitoring notice</DialogTitle>
          <DialogDescription className="pt-2 text-sm leading-relaxed text-muted-foreground whitespace-pre-line">{me.monitoring_notice}</DialogDescription>
        </DialogHeader>
        <div className="rounded-lg border bg-background/60 p-3 text-xs text-muted-foreground">
          Screenshots for your account are currently <strong className="text-foreground">{me.screenshots_enabled ? "enabled" : "disabled"}</strong>.
          A green "Monitoring active" bar is always shown while monitoring runs.
        </div>
        <DialogFooter>
          <Button onClick={ack} disabled={busy} data-testid="acknowledge-notice-button">I have read and understand this notice</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
