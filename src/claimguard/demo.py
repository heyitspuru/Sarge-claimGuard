"""End-to-end walkthrough of one claim: agents, settlement, timeline, both surfaces.

Exists because the pieces were only ever visible separately — the pipeline in a test,
the radar in the dashboard, the patient copy in a snapshot — and nobody could see one
record travel the whole way. This runs the *real* orchestrator over a real golden
record and narrates what each agent did, then shows the same claim from the hospital
side and the patient side.

Runs offline on the mock provider by default: deterministic, free, and re-runnable
mid-recording without spending quota. The one thing the mock cannot honestly produce is
a drafted appeal — an empty completion downgrades to `no_valid_appeal`, which is
indistinguishable from the Negotiator genuinely declining. So on the mock this shows the
deterministic advocacy skeleton (real clause, real amounts) and says plainly that the
live draft needs a real provider, exactly as the API does.
"""

import json
from pathlib import Path

from claimguard import advocacy, appeal as appeal_mod, appeals_store, icd, llm
from claimguard.comms import advocacy_messages, patient_status
from claimguard.compliance_radar import radar
from claimguard.config import get_settings
from claimguard.coverage import PolicyRetriever, load_policies
from claimguard.models import SubmissionResult
from claimguard.orchestrator import PipelineDeps, run_claim

RULE = "=" * 72
STEP_LABEL = {
    "summarize": "Summarizer   LLM · structured facts only, no invention",
    "code": "Coder        RAG over ICD-10 + confidence score",
    "package": "Packager     rules only, NO LLM · builds FHIR R4",
    "submit": "Submitter    deterministic, idempotent, NO LLM",
    "appeal": "Negotiator   retrieves the patient's own policy clauses",
    "fraud_check": "Duplicate    advisory flag — never blocks",
}


def _section(title: str) -> None:
    print(f"\n{RULE}\n  {title}\n{RULE}")


def _money(n: int) -> str:
    return f"Rs {n:,}"


def pick_record(preferred: str | None = None) -> str | None:
    """A denied record, so the Negotiator actually has something to do.

    An approved claim makes a duller demo: the whole point of the project only appears
    when the insurer says no.
    """
    if preferred:
        return preferred
    golden = sorted((Path(get_settings().data_dir) / "golden").glob("*.json"))
    for path in golden:
        rid = json.loads(path.read_text(encoding="utf-8"))["record"]["record_id"]
        if advocacy.outcome_for(rid) in ("partial", "rejected"):
            return rid
    return None


def run(record_id: str | None = None, *, language: str = "en") -> int:
    settings = get_settings()
    rid = pick_record(record_id)
    if rid is None:
        print("No golden records found. Run `python -m claimguard gen-data` first.")
        return 1
    # advocacy already has this loader, and its error handling (truncated JSON, missing
    # "record" key) is the reason to reuse rather than re-write it.
    record = advocacy._load_record(rid)
    if record is None:
        print(f"{rid} is not in the golden corpus.")
        return 1

    _section(f"CLAIMGUARD END-TO-END DEMO  ·  {rid}  ·  SYNTHETIC DATA")
    print(f"  provider        {settings.llm_provider}"
          f"{'  (offline, deterministic)' if settings.llm_provider == 'mock' else ''}")
    print(f"  patient         {record.patient.name}, {record.patient.age}/"
          f"{record.patient.sex}   ABHA {record.patient.abha_id}")
    print(f"  admission       {record.admission_date} -> {record.discharge_date}"
          f"   ({record.claim_type}, {record.specialty})")
    print(f"  diagnosis       {record.diagnosis_text}")
    print(f"  procedures      {', '.join(record.procedures) or '—'}")
    print(f"  documents       {', '.join(record.documents)}")
    print(f"  insurer         {record.insurance.insurer_id} / {record.insurance.plan_id}"
          f"   claimed {_money(record.insurance.claimed_amount)}")

    # --- the agents, narrated from the real audit log ---------------------------
    _section("1 · THE AGENTS  (live audit log — this is the real orchestrator)")
    trail: list[dict] = []

    def audit(entry: dict) -> None:
        trail.append(entry)
        step, status = entry["step"], entry["status"]
        if status == "start":
            print(f"\n  ▸ {STEP_LABEL.get(step, step)}")
            return
        detail = entry.get("detail") or {}
        bullet = {"ok": "✓", "error": "✗", "halted": "■", "flagged": "⚑"}.get(status, "·")
        rendered = ", ".join(f"{k}={v}" for k, v in detail.items()) or status
        print(f"      {bullet} {rendered}")

    retriever = icd.InMemoryRetriever(
        icd.load_csv(Path(settings.data_dir) / "icd" / "icd10.csv"), llm.embed)
    policies = load_policies(Path(settings.data_dir) / "policies")

    # The appeal handler is wired only on a real provider. On the mock it would return an
    # empty completion that the grounding gate downgrades to `no_valid_appeal` — a fake
    # refusal, which is the one thing this project must never show.
    appeal_handler = None
    if settings.llm_provider != "mock":
        appeal_handler = appeal_mod.make_appeal_handler(
            policies, PolicyRetriever(policies, llm.embed), llm.complete)

    result = run_claim(record, PipelineDeps(
        llm=llm.complete, retrieve=retriever, store={}, audit=audit, appeal=appeal_handler))

    if settings.llm_provider == "mock":
        print("\n  ⚠ MOCK PROVIDER — the codes above are a deterministic stub, not a")
        print("    real coding attempt. They will not match the diagnosis and are")
        print("    meaningless as accuracy. Real numbers: docs/EVALUATION.md. What this")
        print("    section demonstrates is the WIRING — agent order, retries, the audit")
        print("    trail, and the packaging gate — all of which are provider-independent.")

    print(f"\n  final_status    {result['final_status']}")
    print(f"  icd_codes       {', '.join(result['icd_codes']) or '—'}")
    print(f"  packaging       {result['packaging']}")
    if result["packaging"] == "needs_review":
        print("                  ↳ held for a human. A low-confidence code cannot reach")
        print("                    submission unreviewed — CLAUDE.md treats that as a")
        print("                    hard failure, not a threshold to tune.")
    elif result["packaging"] == "rejected":
        print("                  ↳ caught PRE-submission (missing document), which is the")
        print("                    point: a malformed claim never reaches the insurer.")

    # --- settlement -------------------------------------------------------------
    outcome = advocacy.outcome_for(rid)
    _section("2 · THE SETTLEMENT  (simulated insurer — deterministic, not a real payer)")
    # outcome_for() adjudicates the record directly, independent of the run above. When
    # the pipeline halted pre-submission that is a real divergence, and printing the
    # settlement as though it happened would be exactly the dishonesty this demo exists
    # to argue against — so say which one you are looking at.
    if result["final_status"] != "adjudicated":
        print(f"  ⚠ the pipeline above did NOT submit this claim (it stopped at"
              f" {result['final_status']}).")
        print("    What follows is the insurer's decision for this record in the corpus,")
        print("    shown so the rest of the walkthrough has something to work on. On a")
        print("    real run the gate above is the end of the road until a human clears it.")
        print()
    scenario = appeal_mod.scenario_from_denial(
        record, SubmissionResult(record_id=rid, submission_id=f"SUB-{rid}",
                                 status="adjudicated", outcome=outcome), policies)
    claimed = record.insurance.claimed_amount
    if scenario is None:
        print(f"  outcome         {outcome}")
        print(f"  claimed         {_money(claimed)}")
        print(f"  approved        {_money(claimed)}   (settled in full)")
    else:
        d = scenario.decision
        shortfall = d.claimed_amount - d.approved_amount
        print(f"  outcome         {d.outcome.upper()}")
        print(f"  claimed         {_money(d.claimed_amount)}")
        print(f"  approved        {_money(d.approved_amount)}")
        print(f"  SHORTFALL       {_money(shortfall)}   <-- what the patient pays")
        print(f"  insurer reason  {d.reason_text}")
        print(f"  cited clause    {d.cited_clause_id}")

    # --- timeline ---------------------------------------------------------------
    journey = radar.generate_journey(rid, record.claim_type)
    report = radar.analyze(journey)
    _section("3 · THE RECORD TIMELINE  (Compliance Radar vs the IRDAI 3h SLA)")
    at = {s.stage: s.at_minutes for s in journey.stages}
    for stage in journey.stages:
        gap = report.stage_gaps.get(stage.stage)
        bar = "█" * min(40, (gap or 0) // 3)
        slow = "  <-- slowest handoff" if stage.stage == report.slowest_stage else ""
        gap_txt = f"+{gap:>3}m" if gap is not None else "    "
        print(f"  {stage.at_minutes:>4}m  {stage.stage:<9} {gap_txt} {bar}{slow}")
    print(f"\n  pre-submission  {report.pre_submission_delay_min}m of the 180m SLA"
          f"   status: {report.breach_status.upper()}")
    print("  NOTE            synthetic timeline — the pipeline runs in milliseconds, so")
    print("                  real handoff timestamps do not exist yet. Labelled as such.")

    # --- advocacy ---------------------------------------------------------------
    state = advocacy.advocacy_state(rid)
    _section("4 · THE ADVOCACY  (what the Negotiator does about the shortfall)")
    print(f"  state           {state['state']}")
    if state["cited_clause"]:
        c = state["cited_clause"]
        print(f"  clause applied  {c['clause_id']}  ({c['kind']})")
        print(f'                  "{c["text"]}"')
    stored = appeals_store.get(rid)
    live = result.get("appeal")
    if live:
        print(f"\n  LIVE DRAFT      status={live['status']}  "
              f"citations={len(live['citations'])}")
        if live["status"] == "no_valid_appeal":
            print("  honest refusal  the Negotiator examined it and declined:")
            print(f"                  {live['reasoning'][:300]}")
        else:
            for cite in live["citations"]:
                print(f"    · {cite['clause_id']}  \"{cite['quoted_text'][:80]}\"")
    elif stored:
        print(f"\n  STORED DRAFT    {stored['review_state']} · drafted {stored['drafted_at']}")
        ap = stored["appeal"]
        if ap["status"] == "no_valid_appeal":
            print("  honest refusal  the Negotiator examined this claim and declined to")
            print("                  appeal. That is the property worth showing:")
            print(f"                  {ap['reasoning'][:300]}")
        else:
            for cite in ap["citations"]:
                print(f"    · {cite['clause_id']}  \"{cite['quoted_text'][:80]}\"")
    else:
        print("\n  no live draft   running on the mock provider, which returns an empty")
        print("                  completion the grounding gate would downgrade to")
        print("                  `no_valid_appeal` — a refusal that looks identical to a")
        print("                  genuine one. Re-run with LLM_PROVIDER=gemini to draft.")

    # --- the two surfaces -------------------------------------------------------
    _section(f"5 · WHAT THE PATIENT SEES  (/patient · language={language})")
    decision_at = at.get("decision", 0)
    status = patient_status(journey, report, language=language,
                            now_minutes=decision_at, outcome=outcome)
    print(f"  stage           {status.stage}")
    print(f"  happening       {status.happening}")
    print(f"  next            {status.next_step}")
    for msg in advocacy_messages(rid, decision_at, state["state"], language=language,
                                 filed_after_min=state["filed_after_min"]):
        print(f"\n  +{msg.at_minutes}m  {msg.text}")
    if state["state"] == "no_valid_appeal":
        print("\n  The refusal is delivered too, not quietly dropped. An advocate that")
        print("  claims to be fighting when it is not is worse than one that never")
        print("  claimed to fight — and the patient is still handed a next step.")
    else:
        print("\n  The patient is told AFTER the appeal is filed, not during. A live feed")
        print("  of 'denied' with no resolution yet is anxiety, not transparency.")

    _section("6 · WHAT THE HOSPITAL SEES  (/hospital · staff only)")
    if stored:
        needed = f"appeal {stored['review_state']}"
    elif outcome in ("partial", "rejected"):
        needed = "no appeal drafted yet"
    elif report.breach_status == "breach":
        needed = "SLA breached"
    else:
        needed = "nothing — not denied, not breaching"
    print(f"  in the queue    {needed}")
    print(f"  outcome         {outcome}    SLA: {report.breach_status}")
    print("  the gate        a model-drafted appeal is NEVER sent to an insurer without a")
    print("                  person reading it. Drafting is not sending.")
    print("  not visible     the patient cannot reach this surface at all — separate")
    print("                  login, and /patient/me has no record id in the path, so")
    print("                  there is no id to tamper with.")

    _section("HONEST CLOSE")
    print("  · Every record here is synthetic. No real patient data, by design.")
    print("  · The insurer is a deterministic simulator, not real NHCX — individual")
    print("    developers cannot get sandbox access (docs/NHCX_ACCESS.md).")
    print("  · Coding accuracy is agreement with an UNADJUDICATED synthetic answer key.")
    print("    No certified coder has reviewed it. It is not clinical accuracy.")
    print("  · docs/PRODUCTION_READINESS.md lists what real deployment needs. Most of")
    print("    it is not code.\n")
    return 0
