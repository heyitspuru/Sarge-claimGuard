import { useEffect, useState } from "react";
import { Inbox, Loader2 } from "lucide-react";
import { fetchQueue, type QueueRow } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ClaimDetail } from "@/components/ClaimDetail";
import { cn } from "@/lib/utils";

const MICRO_LABEL = "text-[11px] font-medium uppercase tracking-wider text-muted-foreground";

const ACTION_LABEL: Record<QueueRow["action"], string> = {
  needs_review: "awaiting review",
  needs_draft: "no appeal drafted",
  sla_breach: "SLA breached",
  no_appeal_available: "no grounded appeal",
  approved: "approved",
  declined: "declined",
};

const ACTION_STYLE: Record<QueueRow["action"], string> = {
  needs_review: "bg-prebreach/10 text-prebreach",
  needs_draft: "bg-primary/10 text-primary-text",
  sla_breach: "bg-breach/10 text-breach",
  no_appeal_available: "bg-muted text-muted-foreground",
  approved: "bg-ok/10 text-ok",
  declined: "bg-muted text-muted-foreground",
};

export function WorkQueue() {
  const [rows, setRows] = useState<QueueRow[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    fetchQueue()
      .then((q) => {
        setRows(q);
        if (q.length) setSelected(q[0].record_id);
      })
      .catch(() => setRows([]));
  }, []);

  if (rows === null) {
    return (
      <div className="flex items-center gap-2 py-10 text-sm text-foreground/60">
        <Loader2 className="size-4 animate-spin text-primary" /> loading queue…
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.15fr]">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-semibold tracking-wide">
            <Inbox className="size-4 text-primary" />
            Needs{" "}
            <em className="font-serif text-base font-normal text-muted-foreground">
              a person
            </em>
            <span className="ml-auto font-mono text-xs text-muted-foreground">
              {rows.length}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {rows.length === 0 ? (
            <p className="py-6 text-sm text-foreground/60">
              Nothing needs attention — no denials and no SLA breaches.
            </p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className={MICRO_LABEL}>
                <tr className="border-b border-border">
                  <th className="py-1.5 pr-2 font-medium">record</th>
                  <th className="py-1.5 pr-2 font-medium">decision</th>
                  <th className="py-1.5 font-medium">what&apos;s needed</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.record_id}
                    onClick={() => setSelected(r.record_id)}
                    className={cn(
                      "cursor-pointer border-b border-border/60 transition-colors hover:bg-muted/60",
                      selected === r.record_id && "bg-muted",
                    )}
                  >
                    <td className="py-2 pr-2 font-mono text-xs">{r.record_id}</td>
                    <td className="py-2 pr-2">{r.outcome}</td>
                    <td className="py-2">
                      <span
                        className={cn(
                          "inline-flex rounded-md px-2 py-0.5 font-mono text-[11px] font-semibold",
                          ACTION_STYLE[r.action],
                        )}
                      >
                        {ACTION_LABEL[r.action]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {selected && <ClaimDetail recordId={selected} />}
    </div>
  );
}
