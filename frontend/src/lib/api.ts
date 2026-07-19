// Radar API client with a bundled sample-data fallback so the dashboard renders
// (and the build/demo works) even when the FastAPI backend isn't running.

export type BreachStatus = "ok" | "pre_breach" | "breach";

export interface Baseline {
  preauth_sla_min: number;
  discharge_sla_min: number;
  prebreach_min: number;
}

export interface RadarReport {
  record_id: string;
  claim_type: string;
  pre_submission_delay_min: number;
  stage_gaps: Record<string, number>;
  slowest_stage: string;
  breach_status: BreachStatus;
  alert: boolean;
  synthetic: boolean;
}

export interface Stage {
  stage: string;
  at_minutes: number;
}

export interface JourneyDetail {
  synthetic: boolean;
  journey: { record_id: string; claim_type: string; stages: Stage[] };
  report: RadarReport;
  baseline: Baseline;
}

export interface JourneysResponse {
  synthetic: boolean;
  baseline: Baseline;
  journeys: RadarReport[];
}

const API = "http://localhost:8000";

const SAMPLE_BASELINE: Baseline = { preauth_sla_min: 60, discharge_sla_min: 180, prebreach_min: 120 };

// A small deterministic-looking sample set spanning the three statuses.
const SAMPLE: RadarReport[] = [
  mk("R0008", "cashless", { summary: 41, code: 33, package: 46, submit: 92 }),
  mk("R0002", "reimbursement", { summary: 38, code: 27, package: 39, submit: 46 }),
  mk("R0001", "cashless", { summary: 22, code: 18, package: 25, submit: 40 }),
  mk("R0005", "cashless", { summary: 30, code: 20, package: 28, submit: 55 }),
  mk("R0003", "reimbursement", { summary: 18, code: 12, package: 20, submit: 35 }),
];

function mk(record_id: string, claim_type: string, gaps: Record<string, number>): RadarReport {
  const delay = Object.values(gaps).reduce((a, b) => a + b, 0);
  const slowest = Object.entries(gaps).sort((a, b) => b[1] - a[1])[0][0];
  const status: BreachStatus = delay > 180 ? "breach" : delay >= 120 ? "pre_breach" : "ok";
  return {
    record_id, claim_type, pre_submission_delay_min: delay, stage_gaps: gaps,
    slowest_stage: slowest, breach_status: status, alert: status !== "ok", synthetic: true,
  };
}

export async function fetchJourneys(): Promise<JourneysResponse> {
  try {
    const r = await fetch(`${API}/radar/journeys`);
    if (!r.ok) throw new Error(String(r.status));
    return await r.json();
  } catch {
    const journeys = [...SAMPLE].sort(
      (a, b) => b.pre_submission_delay_min - a.pre_submission_delay_min
    );
    return { synthetic: true, baseline: SAMPLE_BASELINE, journeys };
  }
}

export async function fetchJourney(recordId: string): Promise<JourneyDetail> {
  try {
    const r = await fetch(`${API}/radar/journey/${recordId}`);
    if (!r.ok) throw new Error(String(r.status));
    return await r.json();
  } catch {
    const report = SAMPLE.find((s) => s.record_id === recordId) ?? SAMPLE[0];
    let t = 0;
    const stages: Stage[] = [{ stage: "order", at_minutes: 0 }];
    for (const s of ["summary", "code", "package", "submit"]) {
      t += report.stage_gaps[s] ?? 0;
      stages.push({ stage: s, at_minutes: t });
    }
    stages.push({ stage: "decision", at_minutes: t + 60 });
    return {
      synthetic: true,
      journey: { record_id: report.record_id, claim_type: report.claim_type, stages },
      report,
      baseline: SAMPLE_BASELINE,
    };
  }
}
