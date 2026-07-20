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

export type Language = "en" | "hi" | "ta";

export interface PatientMessage {
  record_id: string;
  event: string;
  language: string;
  text: string;
  at_minutes: number;
  channel: string;
  synthetic: boolean;
}

export interface PatientStatus {
  record_id: string;
  language: string;
  stage: string;
  happening: string;
  next_step: string;
  eta_min: number | null;
  sla_min: number;
  elapsed_min: number;
  messages: PatientMessage[];
  synthetic: boolean;
}

// Mirrors the backend templates so the patient view demos without the API.
const SAMPLE_COPY: Record<Language, { happening: string; next: string; pharmacy: string; submitted: string }> = {
  en: {
    happening: "Your claim is with your insurer.",
    next: "They are reviewing it. We will message you as soon as there is news.",
    pharmacy:
      "Your discharge medicines are being prepared now. The hospital team will tell you when they are ready to collect.",
    submitted:
      "Your claim has been sent to your insurer. We will message you as soon as there is an update. Nothing is needed from you.",
  },
  hi: {
    happening: "आपका क्लेम आपकी बीमा कंपनी के पास है।",
    next: "वे इसकी समीक्षा कर रहे हैं। जानकारी मिलते ही हम आपको बता देंगे।",
    pharmacy:
      "आपकी छुट्टी की दवाइयाँ अभी तैयार की जा रही हैं। अस्पताल की टीम आपको बता देगी कि उन्हें कब लेना है।",
    submitted:
      "आपका क्लेम आपकी बीमा कंपनी को भेज दिया गया है। जैसे ही कोई जानकारी मिलेगी, हम आपको बता देंगे। आपको अभी कुछ नहीं करना है।",
  },
  ta: {
    happening: "உங்கள் க்ளெய்ம் காப்பீட்டு நிறுவனத்திடம் உள்ளது.",
    next: "அவர்கள் பரிசீலித்து வருகின்றனர். தகவல் கிடைத்தவுடன் தெரிவிப்போம்.",
    pharmacy:
      "உங்கள் வீட்டுக்குச் செல்லும் மருந்துகள் இப்போது தயாராகி வருகின்றன. எப்போது பெற்றுக்கொள்ளலாம் என்பதை மருத்துவமனைக் குழு தெரிவிக்கும்.",
    submitted:
      "உங்கள் க்ளெய்ம் காப்பீட்டு நிறுவனத்திற்கு அனுப்பப்பட்டுள்ளது. தகவல் கிடைத்தவுடன் உங்களுக்குத் தெரிவிப்போம். இப்போது உங்களிடமிருந்து எதுவும் தேவையில்லை.",
  },
};

export async function fetchPatientStatus(
  recordId: string,
  lang: Language = "en"
): Promise<PatientStatus> {
  try {
    const r = await fetch(`${API}/patient/${recordId}?lang=${lang}`);
    if (!r.ok) throw new Error(String(r.status));
    return (await r.json()).status;
  } catch {
    const report = SAMPLE.find((s) => s.record_id === recordId) ?? SAMPLE[0];
    const submitAt = report.pre_submission_delay_min;
    const copy = SAMPLE_COPY[lang];
    const messages: PatientMessage[] = [
      { event: "pharmacy_ready", text: copy.pharmacy, at_minutes: 0 },
      { event: "claim_submitted", text: copy.submitted, at_minutes: submitAt },
    ].map((m) => ({
      ...m,
      record_id: report.record_id,
      language: lang,
      channel: "whatsapp_sandbox",
      synthetic: true,
    }));
    return {
      record_id: report.record_id,
      language: lang,
      stage: "submit",
      happening: copy.happening,
      next_step: copy.next,
      eta_min: null,
      sla_min: SAMPLE_BASELINE.discharge_sla_min,
      elapsed_min: submitAt,
      messages,
      synthetic: true,
    };
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
