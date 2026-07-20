import { useEffect, useState } from "react";
import { CheckCircle2, Clock, FlaskConical, Loader2, MessageCircle, Pill } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { fetchPatientStatus, AuthError, type Language, type PatientStatus } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SignOutButton } from "@/components/SignOutButton";
import { cn } from "@/lib/utils";

const LANGS: { code: Language; label: string }[] = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "ta", label: "தமிழ்" },
];

const EVENT_ICON: Record<string, typeof Pill> = {
  pharmacy_ready: Pill,
  claim_submitted: CheckCircle2,
  sla_prebreach: Clock,
};

const MICRO_LABEL = "text-[11px] font-medium uppercase tracking-wider text-muted-foreground";
const CARD_HOVER = "transition-all duration-200 shadow-md hover:shadow-lg hover:-translate-y-0.5";

/**
 * A patient's own claim. There is deliberately no record picker and no record id in the
 * props: the server derives the record from the session, so this component has no way
 * to ask for anyone else's claim even if it wanted to.
 */
export function PatientView() {
  const navigate = useNavigate();
  const [lang, setLang] = useState<Language>("en");
  const [status, setStatus] = useState<PatientStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPatientStatus(lang)
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch((err) => {
        // The session ended (expired, signed out elsewhere, consent withdrawn).
        if (err instanceof AuthError) navigate("/patient/login", { replace: true });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lang, navigate]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 font-sans text-foreground">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Your claim,{" "}
            <em className="font-serif text-[1.2em] font-normal leading-none text-primary">
              in your words
            </em>
          </h1>
          <p className="mt-1 text-sm leading-relaxed text-foreground/70">
            What&apos;s happening, and what happens next.
          </p>
        </div>
        <SignOutButton />
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-2" role="group" aria-label="Language">
        <span className={MICRO_LABEL}>Language</span>
        {LANGS.map((l) => (
          <button
            key={l.code}
            onClick={() => setLang(l.code)}
            aria-pressed={lang === l.code}
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs transition-colors",
              lang === l.code
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border hover:bg-muted",
            )}
          >
            {l.label}
          </button>
        ))}
      </div>

      {loading || !status ? (
        <div className="flex items-center gap-2 py-10 text-sm text-foreground/60">
          <Loader2 className="size-4 animate-spin text-primary" /> loading…
        </div>
      ) : (
        <div className="grid gap-4">
          <Card className={CARD_HOVER}>
            <CardContent>
              <p className="text-lg leading-relaxed font-medium">{status.happening}</p>
              <p className="mt-2 leading-relaxed text-foreground/70">{status.next_step}</p>

              <div className="mt-4 flex flex-wrap items-center gap-6 border-t border-border pt-3">
                <div>
                  <div className={MICRO_LABEL}>Elapsed</div>
                  <div className="font-mono text-lg font-semibold tabular-nums">
                    {status.elapsed_min}m
                  </div>
                </div>
                {status.eta_min !== null && (
                  <div>
                    <div className={MICRO_LABEL}>Next update in</div>
                    <div className="font-mono text-lg font-semibold tabular-nums text-primary-text">
                      ~{status.eta_min}m
                    </div>
                  </div>
                )}
                <div>
                  <div className={MICRO_LABEL}>Insurer SLA</div>
                  <div className="font-mono text-lg font-semibold tabular-nums">
                    {status.sla_min}m
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className={CARD_HOVER}>
            <CardHeader>
              <CardTitle className="text-sm font-semibold tracking-wide">
                Messages{" "}
                <em className="font-serif text-base font-normal text-muted-foreground">
                  we sent you
                </em>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {status.messages.length ? (
                <ol className="space-y-3">
                  {status.messages.map((m, i) => {
                    const Icon = EVENT_ICON[m.event] ?? MessageCircle;
                    return (
                      <li key={`${m.event}-${i}`} className="flex gap-3">
                        <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
                          <Icon className="size-3.5 text-primary" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-baseline gap-2">
                            <span className="font-mono text-xs font-semibold">{m.event}</span>
                            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                              +{m.at_minutes}m
                            </span>
                          </div>
                          <p className="mt-0.5 text-sm leading-relaxed text-foreground/80">
                            {m.text}
                          </p>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              ) : (
                <div className="py-6 text-sm text-foreground/60">No messages yet.</div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <p className="mt-6 inline-flex items-start gap-1.5 text-xs leading-relaxed text-foreground/50">
        <FlaskConical className="mt-0.5 size-3.5 shrink-0 text-primary" />
        <span>
          Synthetic data. Messages are shown as they would be delivered — nothing is
          actually sent to a phone.
        </span>
      </p>
    </div>
  );
}
