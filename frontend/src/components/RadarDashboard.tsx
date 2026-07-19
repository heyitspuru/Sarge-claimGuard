import { useEffect, useState } from "react";
import {
  fetchJourney,
  fetchJourneys,
  type Baseline,
  type JourneyDetail,
  type RadarReport,
} from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge, StatusBadge } from "./ui/badge";

const STAGE_COLOR: Record<string, string> = {
  summary: "bg-primary/70",
  code: "bg-primary/50",
  package: "bg-primary/60",
  submit: "bg-primary",
};

export function RadarDashboard() {
  const [journeys, setJourneys] = useState<RadarReport[]>([]);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<JourneyDetail | null>(null);

  useEffect(() => {
    fetchJourneys().then((r) => {
      setJourneys(r.journeys);
      setBaseline(r.baseline);
      if (r.journeys.length) setSelected(r.journeys[0].record_id);
    });
  }, []);

  useEffect(() => {
    if (selected) fetchJourney(selected).then(setDetail);
  }, [selected]);

  const breaches = journeys.filter((j) => j.breach_status === "breach").length;
  const prebreaches = journeys.filter((j) => j.breach_status === "pre_breach").length;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 font-sans text-foreground">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-mono text-xl font-bold">
            ClaimGuard · <span className="text-primary">Compliance Radar</span>
          </h1>
          <p className="text-sm text-foreground/70">
            Pre-submission delay vs. IRDAI SLA — where claim time is lost.
          </p>
        </div>
        <span className="rounded-md border border-primary/40 bg-primary/10 px-3 py-1 font-mono text-xs font-semibold text-primary">
          SYNTHETIC DATA — not a live journey
        </span>
      </header>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Journeys" value={journeys.length} />
        <Stat label="Breaches (>3h)" value={breaches} tone="breach" />
        <Stat label="Pre-breach (2–3h)" value={prebreaches} tone="prebreach" />
        <Stat
          label="Discharge SLA"
          value={baseline ? `${baseline.discharge_sla_min}m` : "—"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Journeys (worst delay first)</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="font-mono text-xs text-foreground/60">
                <tr className="border-b border-border">
                  <th className="py-1 pr-2">record</th>
                  <th className="py-1 pr-2">type</th>
                  <th className="py-1 pr-2">delay</th>
                  <th className="py-1 pr-2">slowest</th>
                  <th className="py-1">status</th>
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
                    <td className="py-1.5 pr-2 font-mono">{j.record_id}</td>
                    <td className="py-1.5 pr-2">{j.claim_type}</td>
                    <td className="py-1.5 pr-2 font-mono tabular-nums">
                      {j.pre_submission_delay_min}m
                    </td>
                    <td className="py-1.5 pr-2">{j.slowest_stage}</td>
                    <td className="py-1.5">
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

      <p className="mt-4 text-center text-xs text-foreground/50">
        Synthetic timeline (deterministic per record). Real timestamps arrive with deployment;
        this measures where time <em>would</em> be lost. IRDAI baseline: pre-auth 1h, discharge 3h.
      </p>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  const color = tone === "breach" ? "text-breach" : tone === "prebreach" ? "text-prebreach" : "text-foreground";
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="font-mono text-xs text-foreground/60">{label}</div>
        <div className={`font-mono text-2xl font-bold tabular-nums ${color}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

function JourneyDetailPanel({ detail, baseline }: { detail: JourneyDetail; baseline: Baseline }) {
  const { report, journey } = detail;
  const gaps = report.stage_gaps;
  const maxGap = Math.max(...Object.values(gaps), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {report.record_id} · {report.claim_type}{" "}
          <StatusBadge status={report.breach_status} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex items-baseline gap-2">
          <span className="font-mono text-3xl font-bold tabular-nums">
            {report.pre_submission_delay_min}
          </span>
          <span className="text-sm text-foreground/60">min to submit</span>
        </div>

        {/* SLA comparison bar: 0 -> discharge SLA, with pre-breach marker */}
        <div className="relative mb-4 h-3 w-full rounded bg-muted">
          <div
            className="absolute inset-y-0 left-0 rounded"
            style={{
              width: `${Math.min(100, (report.pre_submission_delay_min / baseline.discharge_sla_min) * 100)}%`,
              background: report.breach_status === "breach" ? "#B91C1C" : report.breach_status === "pre_breach" ? "#B45309" : "#15803D",
            }}
          />
          <div
            className="absolute inset-y-0 w-px bg-foreground/50"
            style={{ left: `${(baseline.prebreach_min / baseline.discharge_sla_min) * 100}%` }}
            title="pre-breach (2h)"
          />
        </div>
        <div className="mb-4 flex justify-between font-mono text-[10px] text-foreground/50">
          <span>0</span>
          <span>pre-breach {baseline.prebreach_min}m</span>
          <span>SLA {baseline.discharge_sla_min}m</span>
        </div>

        {/* Where time was lost: per-stage gap bars, slowest highlighted */}
        <div className="mb-2 font-mono text-xs text-foreground/60">Where time was lost</div>
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
          Slowest handoff: <Badge className="text-primary">{report.slowest_stage}</Badge>
        </div>

        <div className="mt-3 border-t border-border pt-2 font-mono text-[11px] text-foreground/50">
          timeline:{" "}
          {journey.stages.map((s) => `${s.stage}@${s.at_minutes}m`).join(" → ")}
        </div>
      </CardContent>
    </Card>
  );
}
