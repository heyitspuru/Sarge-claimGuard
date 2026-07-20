import { FileText, Scale, ShieldQuestion } from "lucide-react";
import type { Advocacy, Clause } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const MICRO_LABEL = "text-[11px] font-medium uppercase tracking-wider text-muted-foreground";

function ClauseQuote({ clause, label }: { clause: Clause; label: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/40 p-3">
      <div className={MICRO_LABEL}>{label}</div>
      <div className="mt-1 text-sm">{clause.kind}</div>
      {/* The clause is quoted verbatim. A 'simplified' rewrite of a policy term would be
          a legal statement we are not qualified to make, and a patient acting on our
          paraphrase rather than their policy would be our fault. */}
      <blockquote className="mt-2 border-l-2 border-primary/40 pl-3 text-sm leading-relaxed text-foreground/80">
        “{clause.text}”
      </blockquote>
      <div className="mt-1.5 font-mono text-[11px] text-muted-foreground">
        your policy · {clause.clause_id}
      </div>
    </div>
  );
}

/**
 * The advocacy track. Deliberately separate from the claim-status card: this answers
 * "is anyone fighting for me", which is a different question from "where is my claim".
 */
export function AdvocacyPanel({ advocacy }: { advocacy: Advocacy }) {
  if (advocacy.state === "none") return null;

  const filed = advocacy.state === "filed";
  const Icon = filed ? Scale : ShieldQuestion;

  return (
    <Card className="transition-all duration-200 shadow-md hover:shadow-lg hover:-translate-y-0.5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-semibold tracking-wide">
          <Icon className="size-4 text-primary" />
          {filed ? (
            <>
              We&apos;re{" "}
              <em className="font-serif text-base font-normal text-primary">
                challenging this
              </em>{" "}
              for you
            </>
          ) : (
            <>
              What we{" "}
              <em className="font-serif text-base font-normal text-muted-foreground">
                found
              </em>
            </>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-4">
          {advocacy.messages.map((m, i) => (
            <li key={`${m.event}-${i}`} className="flex gap-3">
              <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <FileText className="size-3.5 text-primary" />
              </div>
              <div className="min-w-0">
                <div className="font-mono text-[11px] tabular-nums text-muted-foreground">
                  +{m.at_minutes}m
                </div>
                <p className="mt-0.5 text-sm leading-relaxed">{m.text}</p>
              </div>
            </li>
          ))}
        </ol>

        {(advocacy.cited_clause || advocacy.supporting_clause) && (
          <div className="mt-4 space-y-3 border-t border-border pt-4">
            <div className={MICRO_LABEL}>The exact wording this turns on</div>
            {advocacy.cited_clause && (
              <ClauseQuote clause={advocacy.cited_clause} label="What your insurer applied" />
            )}
            {advocacy.supporting_clause && (
              <ClauseQuote
                clause={advocacy.supporting_clause}
                label="What we pointed them to"
              />
            )}
          </div>
        )}

        <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
          {filed
            ? "Your insurer has not replied to this yet. We'll tell you as soon as they do — you don't need to chase it."
            : "Nothing here is hidden from you: the wording above is quoted directly from your own policy."}
        </p>
      </CardContent>
    </Card>
  );
}
