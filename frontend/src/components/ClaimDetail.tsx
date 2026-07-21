import { useEffect, useState } from "react";
import { CheckCircle2, FileWarning, Gavel, Loader2, ScrollText, XCircle } from "lucide-react";
import {
  ApiError,
  draftAppeal,
  fetchClaim,
  reviewAppeal,
  type ClaimDetail as Claim,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const MICRO_LABEL = "text-[11px] font-medium uppercase tracking-wider text-muted-foreground";

const REVIEW_STYLE: Record<string, string> = {
  drafted: "bg-prebreach/10 text-prebreach",
  approved: "bg-ok/10 text-ok",
  declined: "bg-muted text-muted-foreground",
};

export function ClaimDetail({ recordId }: { recordId: string }) {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const load = () => fetchClaim(recordId).then(setClaim);

  useEffect(() => {
    setClaim(null);
    setError(null);
    setNote("");
    load().catch(() => setError("Could not load this claim."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordId]);

  async function onDraft() {
    setBusy(true);
    setError(null);
    try {
      await draftAppeal(recordId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  async function onReview(state: "approved" | "declined") {
    setBusy(true);
    setError(null);
    try {
      await reviewAppeal(recordId, state, note);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  if (!claim) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-8 text-sm text-foreground/60">
          {error ?? (
            <>
              <Loader2 className="size-4 animate-spin text-primary" /> loading claim…
            </>
          )}
        </CardContent>
      </Card>
    );
  }

  const appeal = claim.appeal;
  const canDraft = ["partial", "rejected"].includes(claim.outcome) && !appeal;
  const noGroundedAppeal = claim.advocacy.state === "no_valid_appeal";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-sm font-semibold tracking-wide">
          <span className="font-mono">{claim.record_id}</span>
          <span className="font-normal text-muted-foreground">· {claim.claim_type}</span>
          <Badge variant="outline" className="font-mono">
            {claim.outcome}
          </Badge>
          {claim.consent_withdrawn && (
            <Badge variant="outline" className="bg-breach/10 font-mono text-breach">
              consent withdrawn
            </Badge>
          )}
        </CardTitle>
      </CardHeader>

      <CardContent>
        <div className="mb-4 grid grid-cols-3 gap-3">
          <div>
            <div className={MICRO_LABEL}>Delay</div>
            <div className="font-mono text-lg font-semibold tabular-nums">
              {claim.report.pre_submission_delay_min}m
            </div>
          </div>
          <div>
            <div className={MICRO_LABEL}>Slowest</div>
            <div className="text-sm">{claim.report.slowest_stage}</div>
          </div>
          <div>
            <div className={MICRO_LABEL}>SLA</div>
            <div className="text-sm">{claim.report.breach_status}</div>
          </div>
        </div>

        {/* Grounded skeleton — deterministic, costs nothing, always shown. */}
        {claim.advocacy.cited_clause && (
          <div className="mb-4 space-y-2 border-t border-border pt-3">
            <div className={MICRO_LABEL}>What the insurer applied</div>
            <div className="rounded-md border border-border bg-muted/40 p-2.5 text-sm leading-relaxed">
              <span className="font-mono text-xs text-primary-text">
                {claim.advocacy.cited_clause.clause_id}
              </span>
              <span className="text-muted-foreground"> · {claim.advocacy.cited_clause.kind}</span>
              <p className="mt-1 text-foreground/80">{claim.advocacy.cited_clause.text}</p>
            </div>
          </div>
        )}

        {noGroundedAppeal && (
          <div className="mb-4 flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3">
            <FileWarning className="mt-0.5 size-4 shrink-0 text-prebreach" />
            <p className="text-sm leading-relaxed">
              No grounded appeal available — the clause the insurer applied genuinely sits
              in this policy. Drafting one anyway would be an ungrounded argument.
            </p>
          </div>
        )}

        {canDraft && !noGroundedAppeal && (
          <div className="mb-4">
            <Button onClick={onDraft} disabled={busy} className="w-full">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Gavel className="size-4" />}
              Draft appeal with the Negotiator
            </Button>
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              Calls the model and spends provider quota, so it runs only when you ask.
              The draft is stored — reopening this claim is free.
            </p>
          </div>
        )}

        {appeal && (
          <div className="space-y-3 border-t border-border pt-3">
            <div className="flex items-center justify-between">
              <div className={MICRO_LABEL}>Drafted appeal</div>
              <Badge
                variant="outline"
                className={`font-mono ${REVIEW_STYLE[appeal.review_state] ?? ""}`}
              >
                {appeal.review_state}
              </Badge>
            </div>

            {appeal.appeal.status === "no_valid_appeal" ? (
              <p className="rounded-md border border-border bg-muted/40 p-3 text-sm leading-relaxed">
                The Negotiator declined to appeal: {appeal.appeal.reasoning}
              </p>
            ) : (
              <>
                <p className="rounded-md border border-border bg-card p-3 text-sm leading-relaxed whitespace-pre-wrap">
                  {appeal.appeal.appeal_text}
                </p>
                <div>
                  <div className={MICRO_LABEL}>
                    Citations — every one resolves to a real clause
                  </div>
                  <ul className="mt-1 space-y-1.5">
                    {appeal.appeal.citations.map((c) => (
                      <li key={c.clause_id} className="rounded-md border border-border p-2 text-sm">
                        <span className="font-mono text-xs text-primary-text">{c.clause_id}</span>
                        <p className="mt-1 text-foreground/80">“{c.quoted_text}”</p>
                        <p className="mt-1 text-xs text-muted-foreground">{c.relevance}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            )}

            <div className="text-xs text-muted-foreground">
              drafted by {appeal.drafted_by} · {appeal.drafted_at}
              {appeal.reviewed_by && (
                <>
                  <br />
                  {appeal.review_state} by {appeal.reviewed_by} · {appeal.reviewed_at}
                  {appeal.review_note && ` — “${appeal.review_note}”`}
                </>
              )}
            </div>

            {/* A refusal is terminal — there is no letter to approve. Offering the
                button once let a reviewer mark "approved to send" on an empty appeal. */}
            {appeal.review_state === "drafted" &&
              appeal.appeal.status !== "no_valid_appeal" && (
              <div className="border-t border-border pt-3">
                <label htmlFor="review-note" className={MICRO_LABEL}>
                  Reviewer note (optional)
                </label>
                <input
                  id="review-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  className="mt-1 mb-2 block w-full rounded-md border border-border bg-card px-2 py-1.5 text-sm"
                />
                <div className="flex gap-2">
                  <Button onClick={() => onReview("approved")} disabled={busy} className="flex-1">
                    <CheckCircle2 className="size-4" /> Approve to send
                  </Button>
                  <Button
                    onClick={() => onReview("declined")}
                    disabled={busy}
                    variant="outline"
                    className="flex-1"
                  >
                    <XCircle className="size-4" /> Decline
                  </Button>
                </div>
                <p className="mt-1.5 flex items-start gap-1 text-xs leading-relaxed text-muted-foreground">
                  <ScrollText className="mt-0.5 size-3 shrink-0" />
                  A model-drafted letter is never sent to an insurer without a person
                  reading it.
                </p>
              </div>
            )}
          </div>
        )}

        {error && (
          <p role="alert" className="mt-3 text-sm leading-relaxed text-breach">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
