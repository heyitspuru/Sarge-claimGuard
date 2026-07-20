"""Compliance Radar — timestamps a claim's handoffs, finds where pre-submission
time was lost, and compares it to the IRDAI SLA baseline.

The pipeline runs in milliseconds, so journeys are a DETERMINISTIC SYNTHETIC
timeline per record_id until real deployment timestamps exist — every report
carries synthetic=True. IRDAI baseline: cashless pre-auth 1h, discharge 3h; we
alert at the 2h pre-breach mark, before the 3h discharge breach.
"""
import hashlib

from claimguard.models import Journey, RadarReport, RadarStage

PREAUTH_SLA_MIN = 60
DISCHARGE_SLA_MIN = 180
PREBREACH_MIN = 120

# order is T0; decision is the insurer's, after submit (shown, not gated).
STAGE_ORDER = ["order", "summary", "code", "package", "submit", "decision"]
# per-stage gap bands (minutes) the synthetic generator draws from, keyed by the
# stage the gap leads INTO.
_GAP_BANDS = {
    "summary": (15, 55),
    "code": (10, 40),
    "package": (15, 50),
    "submit": (20, 95),
    "decision": (30, 180),
}


def _seed(record_id: str) -> int:
    return int(hashlib.sha1(record_id.encode()).hexdigest(), 16)


def generate_journey(record_id: str, claim_type: str) -> Journey:
    """Deterministic synthetic journey. The hash bucket steers the pre-submission
    delay into ok / pre_breach / breach so all three occur across a record set."""
    h = _seed(record_id)
    bucket = h % 3  # 0 ok, 1 pre_breach, 2 breach

    gaps: dict[str, int] = {}
    for i, stage in enumerate(STAGE_ORDER[1:]):
        lo, hi = _GAP_BANDS[stage]
        gaps[stage] = lo + (h >> (i * 5)) % (hi - lo + 1)

    # nudge the order→submit total into the target band
    pre = gaps["summary"] + gaps["code"] + gaps["package"] + gaps["submit"]
    if bucket == 0:
        target = 60 + h % 55            # < 120 (ok)
    elif bucket == 1:
        target = 120 + h % 55           # [120, 180) (pre_breach)
    else:
        target = 190 + h % 90           # > 180 (breach)
    # scale the pre-submission gaps to hit the target, keep decision as-is
    if pre > 0:
        scale = target / pre
        for s in ("summary", "code", "package", "submit"):
            gaps[s] = max(1, round(gaps[s] * scale))

    stages = [RadarStage(stage="order", at_minutes=0)]
    t = 0
    for stage in STAGE_ORDER[1:]:
        t += gaps[stage]
        stages.append(RadarStage(stage=stage, at_minutes=t))
    return Journey(record_id=record_id, claim_type=claim_type, stages=stages)


def analyze(journey: Journey) -> RadarReport:
    at = {s.stage: s.at_minutes for s in journey.stages}
    # per-consecutive-stage gaps up to submit (where pre-submission time was lost)
    gaps: dict[str, int] = {}
    prev = "order"
    for stage in STAGE_ORDER[1:]:
        if stage in at:
            gaps[stage] = at[stage] - at[prev]
            prev = stage
        if stage == "submit":
            break
    pre_submission_delay = at.get("submit", 0)
    slowest = max(gaps, key=gaps.get) if gaps else "order"

    if pre_submission_delay > DISCHARGE_SLA_MIN:
        status = "breach"
    elif pre_submission_delay >= PREBREACH_MIN:
        status = "pre_breach"
    else:
        status = "ok"

    return RadarReport(
        record_id=journey.record_id,
        claim_type=journey.claim_type,
        pre_submission_delay_min=pre_submission_delay,
        stage_gaps=gaps,
        slowest_stage=slowest,
        breach_status=status,
        alert=status != "ok",
        synthetic=True,
    )
