import { useState } from "react";
import { KeyRound, LogOut } from "lucide-react";
import { toast } from "sonner";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useMe } from "@/context/MeContext";
import api, { errMsg, saveTokens } from "@/lib/api";

function ChangePasswordDialog({ open, onOpenChange }) {
  const [cur, setCur] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const close = (o) => {
    if (!o) {
      setCur("");
      setPw("");
      setPw2("");
    }
    onOpenChange(o);
  };
  const save = async () => {
    if (pw !== pw2) return toast.error("New passwords do not match");
    setBusy(true);
    try {
      saveTokens((await api.post("/auth/change-password", { current_password: cur, new_password: pw })).data);
      toast.success("Password changed");
      setCur("");
      setPw("");
      setPw2("");
      onOpenChange(false);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-w-sm" data-testid="change-password-dialog">
        <DialogHeader><DialogTitle>Change password</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5"><Label>Current password</Label><Input type="password" value={cur} onChange={(e) => setCur(e.target.value)} data-testid="current-password-input" /></div>
          <div className="space-y-1.5"><Label>New password</Label><Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} data-testid="new-password-input" /><p className="text-[11px] text-muted-foreground">At least 8 characters, including a number or symbol.</p></div>
          <div className="space-y-1.5"><Label>Confirm new password</Label><Input type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} data-testid="confirm-new-password-input" /></div>
        </div>
        <DialogFooter><Button onClick={save} disabled={busy} data-testid="change-password-save">Save</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function UserMenu() {
  const { me, logout } = useMe();
  const [open, setOpen] = useState(false);
  const initials = me.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="grid h-9 w-9 place-items-center rounded-full bg-indigo-500 text-sm font-semibold text-white transition-transform hover:scale-105" data-testid="user-menu-button">{initials}</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <div className="truncate">{me.full_name}</div>
            <div className="truncate text-xs font-normal text-muted-foreground">{me.email}</div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setOpen(true)} data-testid="change-password-menu-item"><KeyRound className="mr-2 h-4 w-4" /> Change password</DropdownMenuItem>
          <DropdownMenuItem onClick={logout} data-testid="logout-menu-item"><LogOut className="mr-2 h-4 w-4" /> Sign out</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ChangePasswordDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
