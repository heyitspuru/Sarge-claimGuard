import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Building2, FlaskConical, Loader2 } from "lucide-react";
import { staffLogin, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const MICRO_LABEL = "text-[11px] font-medium uppercase tracking-wider text-muted-foreground";
const FIELD =
  "mt-1 block w-full rounded-md border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/30";

export function StaffLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await staffLogin(email, password);
      navigate("/hospital", { replace: true });
    } catch (err) {
      // One message for both unknown-email and wrong-password, matching the server:
      // a more specific error would tell an attacker which addresses are registered.
      setError(
        err instanceof ApiError
          ? "Those credentials were not recognised."
          : "Could not reach the server. Is the API running?",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
      <Link to="/" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> back
      </Link>

      <Card className="shadow-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <Building2 className="size-4 text-primary" />
            Hospital staff sign in
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit}>
            <label htmlFor="email" className={MICRO_LABEL}>
              Work email
            </label>
            <input
              id="email"
              type="email"
              className={FIELD}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />

            <label htmlFor="password" className={`mt-3 block ${MICRO_LABEL}`}>
              Password
            </label>
            <input
              id="password"
              type="password"
              className={FIELD}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />

            <Button type="submit" className="mt-4 w-full" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              Sign in
            </Button>
          </form>

          {error && (
            <p role="alert" className="mt-3 text-sm leading-relaxed text-breach">
              {error}
            </p>
          )}

          <p className="mt-4 border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
            Demo account:{" "}
            <span className="font-mono">claims@demo-hospital.test</span> /{" "}
            <span className="font-mono">demo-claims-officer</span>
          </p>
        </CardContent>
      </Card>

      <p className="mt-4 inline-flex items-start gap-1.5 text-xs leading-relaxed text-foreground/50">
        <FlaskConical className="mt-0.5 size-3.5 shrink-0 text-primary" />
        <span>
          Seeded demo credentials, no self-registration. Real staff accounts come from
          the hospital&apos;s identity provider.
        </span>
      </p>
    </div>
  );
}
