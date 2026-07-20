import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { fetchMe, type Me } from "@/lib/api";

/**
 * Route guard. This is UX, NOT security — an attacker never runs it. Every rule it
 * expresses is independently enforced server-side in `auth/deps.py`; this exists only
 * so a signed-out user sees a login page instead of a broken screen.
 */
export function RequireAuth({
  kind,
  loginPath,
  children,
}: {
  kind: Me["kind"];
  loginPath: string;
  children: ReactNode;
}) {
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<"checking" | "in" | "out">("checking");

  useEffect(() => {
    fetchMe()
      .then((m) => {
        setMe(m);
        setState("in");
      })
      .catch(() => setState("out"));
  }, []);

  if (state === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 text-sm text-foreground/60">
        <Loader2 className="size-5 animate-spin text-primary" />
        checking your session…
      </div>
    );
  }
  if (state === "out") return <Navigate to={loginPath} replace />;
  // Signed in as the wrong kind of user: send them to their own surface rather than
  // showing an error for a place they were never meant to be.
  if (me && me.kind !== kind) {
    return <Navigate to={me.kind === "staff" ? "/hospital" : "/patient"} replace />;
  }
  return <>{children}</>;
}
