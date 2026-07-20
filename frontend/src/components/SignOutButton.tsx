import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { logout } from "@/lib/api";

export function SignOutButton() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  async function onClick() {
    setBusy(true);
    // Navigate regardless: the server-side revocation is what ends the session, so a
    // failed round-trip must not strand the user on a page they meant to leave.
    try {
      await logout();
    } catch {
      /* already signed out, or the API is unreachable */
    }
    navigate("/", { replace: true });
  }

  return (
    <button
      onClick={onClick}
      disabled={busy}
      className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      <LogOut className="size-3.5" />
      Sign out
    </button>
  );
}
