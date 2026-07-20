import { useEffect, useState } from "react";
import { CheckCircle2, Clock, Loader2, MessageCircle, Pill } from "lucide-react";
import {
  fetchPatientStatus,
  type Language,
  type PatientStatus,
  type RadarReport,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

const CARD_HOVER =
  "transition-all duration-200 shadow-md hover:shadow-lg hover:-translate-y-0.5";

export function PatientView({ journeys }: { journeys: RadarReport[] }) {
  const [lang, setLang] = useState<Language>("en");
  const [recordId, setRecordId] = useState<string | null>(null);
  const [status, setStatus] = useState<PatientStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!recordId && journeys.length) setRecordId(journeys[0].record_id);
  }, [journeys, recordId]);

  useEffect(() => {
    if (!recordId) return;
    setLoading(true);
    fetchPatientStatus(recordId, lang)
      .then(setStatus)
      .finally(() => setLoading(false));
  }, [recordId, lang]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
      <Card className={CARD_HOVER}>
        <CardHeader>
          <CardTitle className="text-sm font-semibold tracking-wide">
            What&apos;s happening{" "}
            <em className="font-serif text-base font-normal text-muted-foreground">
              in your words
            </em>
          </CardTitle>
        </CardHeader>
        <CardContent>
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
                    : "border-border hover:bg-muted"
                )}
              >
                {l.label}
              </button>
            ))}
          </div>

          <div className="mb-4">
            <label htmlFor="patient-record" className={cn("block", MICRO_LABEL)}>
              Record
            </label>
            <select
              id="patient-record"
              value={recordId ?? ""}
              onChange={(e) => setRecordId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border bg-card px-2 py-1.5 font-mono text-xs"
            >
              {journeys.map((j) => (
                <option key={j.record_id} value={j.record_id}>
                  {j.record_id} · {j.claim_type}
                </option>
              ))}
            </select>
          </div>

          {loading || !status ? (
            <div className="flex items-center gap-2 py-6 text-sm text-foreground/60">
              <Loader2 className="size-4 animate-spin text-primary" /> loading…
            </div>
          ) : (
            <>
              <p className="text-lg leading-relaxed font-medium">{status.happening}</p>
              <p className="mt-2 leading-relaxed text-foreground/70">{status.next_step}</p>

              <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-border pt-3">
                <div>
                  <div className={MICRO_LABEL}>Elapsed</div>
                  <div className="font-mono text-lg font-semibold tabular-nums">
                    {status.elapsed_min}m
                  </div>
                </div>
                {status.eta_min !== null && (
                  <div>
                    <div className={MICRO_LABEL}>Next update in</div>
                    <div className="font-mono text-lg font-semibold tabular-nums text-primary">
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
            </>
          )}
        </CardContent>
      </Card>

      <Card className={CARD_HOVER}>
        <CardHeader>
          <CardTitle className="text-sm font-semibold tracking-wide">
            Messages sent{" "}
            <em className="font-serif text-base font-normal text-muted-foreground">
              to the patient
            </em>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {status?.messages.length ? (
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
                      <p className="mt-0.5 text-sm leading-relaxed text-foreground/80">{m.text}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          ) : (
            <div className="py-6 text-sm text-foreground/60">No messages yet.</div>
          )}
          <p className="mt-4 border-t border-border pt-2 text-xs text-foreground/50">
            Delivered via WhatsApp/SMS sandbox. Copy is template-based and reviewed — never
            model-generated — so bad news is always phrased safely.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
