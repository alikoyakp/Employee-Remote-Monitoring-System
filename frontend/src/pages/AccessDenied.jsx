import { useClerk, useUser } from "@clerk/react";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AccessDenied({ reason }) {
  const { signOut } = useClerk();
  const { user } = useUser();
  const inactive = reason === "account_inactive";
  return (
    <div className="grain flex min-h-screen items-center justify-center p-6" data-testid="access-denied-page">
      <div className="max-w-md rounded-xl border bg-card p-8 text-center rise">
        <ShieldAlert className="mx-auto h-10 w-10 text-amber-400" />
        <h1 className="mt-4 text-2xl font-semibold">{inactive ? "Account deactivated" : "Not registered yet"}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {inactive
            ? "Your employee account has been deactivated. Contact your administrator."
            : `${user?.primaryEmailAddress?.emailAddress || "This email"} is not on the employee list. Ask your administrator to add or import you with this work email, then sign in again.`}
        </p>
        {!inactive && reason !== "not_registered" && <p className="mt-2 text-xs text-red-300">Error: {String(reason)}</p>}
        <Button className="mt-6" variant="outline" onClick={() => signOut()} data-testid="access-denied-signout">Sign out</Button>
      </div>
    </div>
  );
}
