import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, FlaskConical, Loader2, ShieldCheck } from "lucide-react";
import { requestOtp, verifyOtp, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const MICRO_LABEL = "text-[11px] font-medium uppercase tracking-wider text-muted-foreground";
const FIELD =
  "mt-1 block w-full rounded-md border border-border bg-card px-3 py-2 font-mono text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/30";

export function PatientLogin() {
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [challenge, setChallenge] = useState<{ id: string; otp: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onRequest(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await requestOtp(identifier);
      setChallenge({ id: r.challenge_id, otp: r.simulated_otp });
    } catch (err) {
      setError(
        err instanceof ApiError && err.message
          ? err.message
          : "Could not reach the server. Is the API running?",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onVerify(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await verifyOtp(challenge!.id, code);
      navigate("/patient", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "This record is no longer accessible."
          : "That code was not valid. Request a new one.",
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
          <CardTitle className="text-base font-semibold">
            Your claim,{" "}
            <em className="font-serif text-lg font-normal text-primary">in your words</em>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!challenge ? (
            <form onSubmit={onRequest}>
              <label htmlFor="identifier" className={MICRO_LABEL}>
                ABHA id or policy number
              </label>
              <input
                id="identifier"
                className={FIELD}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="03-0824-6281-9482"
                autoComplete="off"
                required
              />
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                Use an identifier from the demo corpus. Real identifiers are rejected by
                design — see below.
              </p>
              <Button type="submit" className="mt-4 w-full" disabled={busy}>
                {busy && <Loader2 className="size-4 animate-spin" />}
                Send code
              </Button>
            </form>
          ) : (
            <form onSubmit={onVerify}>
              <div className="mb-3 flex items-start gap-2 rounded-md border border-primary/40 bg-primary/10 p-3">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
                <div className="text-xs leading-relaxed">
                  <div className="font-semibold text-primary-text">
                    Simulated code: <span className="font-mono">{challenge.otp}</span>
                  </div>
                  <div className="mt-0.5 text-foreground/70">
                    Shown here because nothing is actually sent. Real ABHA delivers this
                    to your registered mobile via ABDM.
                  </div>
                </div>
              </div>
              <label htmlFor="otp" className={MICRO_LABEL}>
                Enter the 6-digit code
              </label>
              <input
                id="otp"
                className={FIELD}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                maxLength={6}
                autoComplete="one-time-code"
                required
              />
              <Button type="submit" className="mt-4 w-full" disabled={busy}>
                {busy && <Loader2 className="size-4 animate-spin" />}
                Sign in
              </Button>
              <button
                type="button"
                onClick={() => {
                  setChallenge(null);
                  setCode("");
                  setError(null);
                }}
                className="mt-2 w-full text-xs text-muted-foreground hover:text-foreground"
              >
                use a different identifier
              </button>
            </form>
          )}

          {error && (
            <p role="alert" className="mt-3 text-sm leading-relaxed text-breach">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      <p className="mt-4 inline-flex items-start gap-1.5 text-xs leading-relaxed text-foreground/50">
        <FlaskConical className="mt-0.5 size-3.5 shrink-0 text-primary" />
        <span>
          <strong>Never enter a real ABHA id or policy number.</strong> This build only
          accepts synthetic identifiers from its own demo corpus, and refuses anything
          else — that refusal is what keeps real personal data out.
        </span>
      </p>
    </div>
  );
}
