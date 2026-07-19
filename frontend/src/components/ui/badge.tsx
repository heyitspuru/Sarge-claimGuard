import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type Status = "ok" | "pre_breach" | "breach";

const STATUS_STYLES: Record<Status, string> = {
  ok: "bg-ok/10 text-ok border-ok/30",
  pre_breach: "bg-prebreach/10 text-prebreach border-prebreach/30",
  breach: "bg-breach/10 text-breach border-breach/30",
};

const STATUS_LABEL: Record<Status, string> = {
  ok: "OK",
  pre_breach: "PRE-BREACH",
  breach: "BREACH",
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-xs font-semibold",
        STATUS_STYLES[status]
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border border-border px-2 py-0.5 font-mono text-xs",
        className
      )}
      {...props}
    />
  );
}
