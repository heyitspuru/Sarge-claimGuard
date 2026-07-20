import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Clock,
  FlaskConical,
  Loader2,
  Radar,
  TimerReset,
  User,
} from "lucide-react";
import { PatientView } from "@/components/PatientView";
import {
  fetchJourney,
  fetchJourneys,
  type Baseline,
  type JourneyDetail,
  type RadarReport,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STAGE_COLOR: Record<string, string> = {
  summary: "bg-primary/70",
  code: "bg-primary/50",
  package: "bg-primary/60",
  submit: "bg-primary",
};

type Status = "ok" | "pre_breach" | "breach";

const STATUS_STYLES: Record<Status, string> = {
  ok: "bg-ok/10 text-ok",
  pre_breach: "bg-prebreach/10 text-prebreach",
  breach: "bg-breach/10 text-breach",
};

const STATUS_LABEL: Record<Status, string> = {
  ok: "OK",
  pre_breach: "PRE-BREACH",
  breach: "BREACH",
};

function StatusBadge({ status }: { status: Status }) {
  return (
    <Badge variant="outline" className={cn("font-mono font-semibold", STATUS_STYLES[status])}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}

// MASTER.md card hover: shadow lift + translateY(-2px), 200ms
const CARD_HOVER =
  "transition-all duration-200 shadow-md hover:shadow-lg hover:-translate-y-0.5";

// Typography roles: mono = data (ids, numbers, timeline); sans = prose, titles, labels.
const MICRO_LABEL = "text-[11px] font-medium uppercase tracking-wider text-muted-foreground";

export function RadarDashboard() {
  const [journeys, setJourneys] = useState<RadarReport[]>([]);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<JourneyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"radar" | "patient">("radar");

  useEffect(() => {
    fetchJourneys()
      .then((r) => {
        setJourneys(r.journeys);
        setBaseline(r.baseline);
        if (r.journeys.length) setSelected(r.journeys[0].record_id);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selected) fetchJourney(selected).then(setDetail);
  }, [selected]);

  const breaches = journeys.filter((j) => j.breach_status === "breach").length;
  const prebreaches = journeys.filter((j) => j.breach_status === "pre_breach").length;

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 font-mono text-sm text-foreground/60">
        <Loader2 className="size-5 animate-spin text-primary" />
        loading radar…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 font-sans text-foreground">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Radar className="size-6 text-primary" />
            ClaimGuard · Compliance{" "}
            <em className="font-serif text-[1.2em] font-normal leading-none text-primary">
              Radar
            </em>
          </h1>
          <p className="mt-1 text-sm leading-relaxed text-foreground/70">
            Pre-submission delay vs. IRDAI SLA — where claim time is lost.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-md border border-primary/40 bg-primary/10 px-3 py-1 font-mono text-xs font-semibold text-primary">
          <FlaskConical className="size-3.5" />
          SYNTHETIC DATA — not a live journey
        </span>
      </header>

      <div className="mb-5 flex gap-1 border-b border-border">
        {([
          ["radar", "Compliance Radar", Radar],
          ["patient", "Patient view", User],
        ] as const).map(([key, label, Icon]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm transition-colors ${
              tab === key
                ? "border-primary font-medium text-primary"
                : "border-transparent text-foreground/60 hover:text-foreground"
            }`}
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === "patient" ? (
        <PatientView journeys={journeys} />
      ) : (
      <>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Journeys" value={journeys.length} icon={Activity} />
        <Stat label="Breaches (>3h)" value={breaches} tone="breach" icon={AlertTriangle} />
        <Stat label="Pre-breach (2–3h)" value={prebreaches} tone="prebreach" icon={TimerReset} />
        <Stat
          label="Discharge SLA"
          value={baseline ? `${baseline.discharge_sla_min}m` : "—"}
          icon={Clock}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <Card className={CARD_HOVER}>
          <CardHeader>
            <CardTitle className="text-sm font-semibold tracking-wide">
              Journeys{" "}
              <em className="font-serif text-base font-normal text-muted-foreground">
                worst delay first
              </em>
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className={MICRO_LABEL}>
                <tr className="border-b border-border">
                  <th className="py-1.5 pr-2 font-medium">record</th>
                  <th className="py-1.5 pr-2 font-medium">type</th>
                  <th className="py-1.5 pr-2 font-medium">delay</th>
                  <th className="py-1.5 pr-2 font-medium">slowest</th>
                  <th className="py-1.5 font-medium">status</th>
                </tr>
              </thead>
              <tbody>
                {journeys.map((j) => (
                  <tr
                    key={j.record_id}
                    onClick={() => setSelected(j.record_id)}
                    className={`cursor-pointer border-b border-border/60 transition-colors hover:bg-muted/60 ${
                      selected === j.record_id ? "bg-muted" : ""
                    }`}
                  >
                    <td className="py-2 pr-2 font-mono text-xs">{j.record_id}</td>
                    <td className="py-2 pr-2">{j.claim_type}</td>
                    <td className="py-2 pr-2 font-mono text-xs font-semibold tabular-nums">
                      {j.pre_submission_delay_min}m
                    </td>
                    <td className="py-2 pr-2">{j.slowest_stage}</td>
                    <td className="py-2">
                      <StatusBadge status={j.breach_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {detail && baseline && <JourneyDetailPanel detail={detail} baseline={baseline} />}
      </div>
      </>
      )}

      <p className="mt-4 text-center text-xs text-foreground/50">
        Synthetic timeline (deterministic per record). Real timestamps arrive with deployment;
        this measures where time <em>would</em> be lost. IRDAI baseline: pre-auth 1h, discharge 3h.
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  tone?: string;
  icon: typeof Activity;
}) {
  const color =
    tone === "breach" ? "text-breach" : tone === "prebreach" ? "text-prebreach" : "text-foreground";
  const iconColor =
    tone === "breach" ? "text-breach" : tone === "prebreach" ? "text-prebreach" : "text-primary";
  return (
    <Card className={CARD_HOVER}>
      <CardContent>
        <div className={`flex items-center gap-1.5 ${MICRO_LABEL}`}>
          <Icon className={`size-3.5 ${iconColor}`} />
          {label}
        </div>
        <div className={`mt-1 font-mono text-3xl font-bold tabular-nums ${color}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

function JourneyDetailPanel({ detail, baseline }: { detail: JourneyDetail; baseline: Baseline }) {
  const { report, journey } = detail;
  const gaps = report.stage_gaps;
  const maxGap = Math.max(...Object.values(gaps), 1);

  return (
    <Card className={CARD_HOVER}>
      <CardHeader>
        <CardTitle className="text-sm font-semibold tracking-wide">
          <span className="font-mono">{report.record_id}</span>{" "}
          <span className="font-normal text-muted-foreground">· {report.claim_type}</span>{" "}
          <StatusBadge status={report.breach_status} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex items-baseline gap-2">
          <span className="font-mono text-3xl font-bold tabular-nums">
            {report.pre_submission_delay_min}
          </span>
          <em className="font-serif text-base text-foreground/60">min to submit</em>
        </div>

        {/* SLA comparison bar: 0 -> discharge SLA, with pre-breach marker */}
        <div className="relative mb-4 h-3 w-full rounded bg-muted">
          <div
            className="absolute inset-y-0 left-0 rounded"
            style={{
              width: `${Math.min(100, (report.pre_submission_delay_min / baseline.discharge_sla_min) * 100)}%`,
              background:
                report.breach_status === "breach"
                  ? "#B91C1C"
                  : report.breach_status === "pre_breach"
                    ? "#B45309"
                    : "#15803D",
            }}
          />
          <div
            className="absolute inset-y-0 w-px bg-foreground/50"
            style={{ left: `${(baseline.prebreach_min / baseline.discharge_sla_min) * 100}%` }}
            title="pre-breach (2h)"
          />
        </div>
        <div className="mb-4 flex justify-between text-[10px] font-medium uppercase tracking-wide text-foreground/50">
          <span>0</span>
          <span>pre-breach {baseline.prebreach_min}m</span>
          <span>SLA {baseline.discharge_sla_min}m</span>
        </div>

        {/* Where time was lost: per-stage gap bars, slowest highlighted */}
        <div className="mb-2 text-sm">
          <em className="font-serif text-base text-foreground/70">Where time was lost</em>
        </div>
        <div className="space-y-1.5">
          {Object.entries(gaps).map(([stage, mins]) => (
            <div key={stage} className="flex items-center gap-2">
              <span className="w-16 font-mono text-xs">{stage}</span>
              <div className="h-4 flex-1 rounded bg-muted">
                <div
                  className={`h-4 rounded ${STAGE_COLOR[stage] ?? "bg-primary"} ${
                    stage === report.slowest_stage ? "ring-2 ring-primary/60" : ""
                  }`}
                  style={{ width: `${(mins / maxGap) * 100}%` }}
                />
              </div>
              <span className="w-10 text-right font-mono text-xs tabular-nums">{mins}m</span>
            </div>
          ))}
        </div>
        <div className="mt-3 text-xs text-foreground/60">
          Slowest handoff:{" "}
          <Badge variant="outline" className="font-mono text-primary">
            {report.slowest_stage}
          </Badge>
        </div>

        <div className="mt-3 border-t border-border pt-2 font-mono text-[11px] text-foreground/50">
          timeline: {journey.stages.map((s) => `${s.stage}@${s.at_minutes}m`).join(" → ")}
        </div>
      </CardContent>
    </Card>
  );
}
