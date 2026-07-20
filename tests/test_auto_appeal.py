"""Auto-appeal wiring: a denied claim raises a grounded appeal without human prompting.

The invariant that matters is NOT "every denial produces an appeal". It is that a denial
gets *examined*, and the Negotiator's verdict — including an honest `no_valid_appeal` —
survives to the caller unchanged. Auto-raising must never pressure the agent into
finding an appeal that isn't there; that would invert prime directive 2.
"""

from claimguard import appeal as appeal_mod
from claimguard.icd import IcdEntry, InMemoryRetriever
from claimguard.llm import _mock_embed
from claimguard.models import (
    DischargeRecord,
    Insurance,
    Patient,
    SubmissionResult,
)
from claimguard.orchestrator import PipelineDeps, run_claim

POLICIES = [{
    "insurer_id": "INS1", "insurer_name": "Test Insurer",
    "plan_id": "P1", "plan_name": "Test Plan",
    "clauses": [
        {"clause_id": "INS1-P1-C01", "clause_type": "coverage",
         "text": "Hospitalisation for surgical procedures is covered up to the sum insured.",
         "structured": {}},
        {"clause_id": "INS1-P1-C02", "clause_type": "sub_limit",
         "text": "Room rent is limited to 1% of sum insured per day.", "structured": {}},
        {"clause_id": "INS1-P1-C03", "clause_type": "exclusion",
         "text": "Cosmetic procedures are excluded.", "structured": {}},
    ],
}]


def _record(record_id="R5001", claimed=80000):
    return DischargeRecord(
        record_id=record_id,
        patient=Patient(name="Test Patient", age=40, sex="F", abha_id="91-0000-0000-5001"),
        admission_date="2026-07-01", discharge_date="2026-07-04",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL-5001",
                            sum_insured=500000, claimed_amount=claimed),
    )


def _retriever(query, insurer_id, plan_id, k=5):
    return [c for p in POLICIES if p["insurer_id"] == insurer_id and p["plan_id"] == plan_id
            for c in p["clauses"]][:k]


def _pipeline_llm(prompt, *, system="", tier="fast", json_schema=None):
    if json_schema and "codes" in str(json_schema):
        return {"codes": [{"icd_code": "K35.80", "description": "Acute appendicitis",
                           "confidence": 0.95}]}
    return {"primary_diagnosis": "Acute appendicitis", "secondary_diagnoses": [],
            "procedures": ["Laparoscopic appendectomy"], "medications": ["Inj Ceftriaxone"],
            "admission_course": "Uneventful."}


def _appealing_llm(prompt, *, system="", tier="fast", json_schema=None):
    """Negotiator that cites a real clause."""
    if json_schema and "citations" in str(json_schema):
        return {"status": "appeal", "appeal_text": "The sub-limit was over-applied.",
                "citations": [{"clause_id": "INS1-P1-C02", "quoted_text": "whatever",
                               "relevance": "limits room rent only"}],
                "reasoning": "grounded"}
    return _pipeline_llm(prompt, system=system, tier=tier, json_schema=json_schema)


def _refusing_llm(prompt, *, system="", tier="fast", json_schema=None):
    if json_schema and "citations" in str(json_schema):
        return {"status": "no_valid_appeal", "appeal_text": "",
                "citations": [], "reasoning": "the exclusion genuinely applies"}
    return _pipeline_llm(prompt, system=system, tier=tier, json_schema=json_schema)


def _deps(llm, store=None, audit=None, with_appeal=True):
    handler = (appeal_mod.make_appeal_handler(POLICIES, _retriever, llm)
               if with_appeal else None)
    return PipelineDeps(
        llm=_pipeline_llm,
        retrieve=InMemoryRetriever([IcdEntry("K35.80", "Acute appendicitis")], _mock_embed),
        store=store if store is not None else {},
        audit=audit if audit is not None else (lambda e: None),
        appeal=handler,
    )


def _denied_record():
    """Find a record_id whose deterministic adjudication is partial or rejected."""
    for i in range(200):
        rid = f"R{i:04d}"
        from claimguard.agents.submitter import submit
        from claimguard.models import ClaimPackage
        outcome = submit(ClaimPackage(record_id=rid, status="ready"), {}).outcome
        if outcome in ("partial", "rejected"):
            return _record(rid), outcome
    raise AssertionError("no denied record found in the deterministic simulator")


# --- scenario construction ---


def test_scenario_is_built_only_for_appealable_outcomes():
    record = _record()
    approved = SubmissionResult(record_id=record.record_id, submission_id="SIM-1",
                                status="adjudicated", outcome="approved")
    assert appeal_mod.scenario_from_denial(record, approved, POLICIES) is None

    rejected = approved.model_copy(update={"outcome": "rejected"})
    assert appeal_mod.scenario_from_denial(record, rejected, POLICIES) is not None


def test_denial_cites_a_real_clause_from_the_patients_own_policy():
    """A denial citing an invented clause would make the whole exercise circular."""
    record = _record()
    result = SubmissionResult(record_id="R5001", submission_id="SIM-1",
                              status="adjudicated", outcome="rejected")
    scenario = appeal_mod.scenario_from_denial(record, result, POLICIES)

    real_ids = {c["clause_id"] for c in POLICIES[0]["clauses"]}
    assert scenario.decision.cited_clause_id in real_ids
    assert scenario.decision.cited_clause_id in scenario.decision.reason_text


def test_denial_never_cites_a_coverage_clause():
    """Denying a claim by citing the clause that covers it is not a scenario."""
    for i in range(30):
        record = _record(f"R{i:04d}")
        result = SubmissionResult(record_id=record.record_id, submission_id="S",
                                  status="adjudicated", outcome="rejected")
        scenario = appeal_mod.scenario_from_denial(record, result, POLICIES)
        cited = next(c for c in POLICIES[0]["clauses"]
                     if c["clause_id"] == scenario.decision.cited_clause_id)
        assert cited["clause_type"] != "coverage"


def test_scenario_construction_is_deterministic():
    record = _record()
    result = SubmissionResult(record_id="R5001", submission_id="SIM-1",
                              status="adjudicated", outcome="partial")
    a = appeal_mod.scenario_from_denial(record, result, POLICIES)
    b = appeal_mod.scenario_from_denial(record, result, POLICIES)
    assert a.decision.cited_clause_id == b.decision.cited_clause_id
    assert a.decision.approved_amount == b.decision.approved_amount


def test_partial_pays_something_and_rejection_pays_nothing():
    record = _record(claimed=80000)
    base = SubmissionResult(record_id="R5001", submission_id="S", status="adjudicated",
                            outcome="partial")
    partial = appeal_mod.scenario_from_denial(record, base, POLICIES)
    rejected = appeal_mod.scenario_from_denial(
        record, base.model_copy(update={"outcome": "rejected"}), POLICIES)

    assert 0 < partial.decision.approved_amount < 80000
    assert rejected.decision.approved_amount == 0


def test_unknown_policy_yields_no_scenario_rather_than_a_fabricated_one():
    record = _record()
    record.insurance.insurer_id = "NOPE"
    result = SubmissionResult(record_id="R5001", submission_id="S",
                              status="adjudicated", outcome="rejected")
    assert appeal_mod.scenario_from_denial(record, result, POLICIES) is None


# --- orchestrator wiring ---


def test_denied_claim_raises_an_appeal_automatically():
    record, outcome = _denied_record()
    result = run_claim(record, _deps(_appealing_llm))

    assert result["outcome"] == outcome
    assert result["appeal"] is not None, "a denial went unappealed"
    assert result["appeal"]["status"] == "appeal"
    assert result["appeal"]["citations"], "an appeal with no citation is not grounded"


def test_honest_refusal_survives_to_the_caller_unchanged():
    """Auto-raising must not pressure the agent into inventing an appeal."""
    record, _ = _denied_record()
    result = run_claim(record, _deps(_refusing_llm))

    assert result["appeal"] is not None
    assert result["appeal"]["status"] == "no_valid_appeal"
    assert result["appeal"]["citations"] == []


def test_approved_claim_raises_no_appeal():
    from claimguard.agents.submitter import submit
    from claimguard.models import ClaimPackage
    approved = next(f"R{i:04d}" for i in range(200)
                    if submit(ClaimPackage(record_id=f"R{i:04d}", status="ready"),
                              {}).outcome == "approved")
    result = run_claim(_record(approved), _deps(_appealing_llm))

    assert result["outcome"] == "approved"
    assert result["appeal"] is None


def test_no_handler_configured_leaves_the_pipeline_unchanged():
    record, _ = _denied_record()
    result = run_claim(record, _deps(_appealing_llm, with_appeal=False))
    assert result["final_status"] == "adjudicated"
    assert result["appeal"] is None


def test_appeal_failure_does_not_fail_the_claim():
    """The adjudication already happened; a broken appeal must not erase it."""
    def exploding_llm(prompt, *, system="", tier="fast", json_schema=None):
        if json_schema and "citations" in str(json_schema):
            raise RuntimeError("negotiator exploded")
        return _pipeline_llm(prompt, system=system, tier=tier, json_schema=json_schema)

    record, _ = _denied_record()
    result = run_claim(record, _deps(exploding_llm))

    assert result["final_status"] == "adjudicated", "a failed appeal must not fail the claim"
    assert result["appeal"] is None


def test_appeal_is_audited():
    record, _ = _denied_record()
    events = []
    run_claim(record, _deps(_appealing_llm, audit=events.append))

    appeal_events = [e for e in events if e["step"] == "appeal" and e["status"] == "ok"]
    assert len(appeal_events) == 1
    assert appeal_events[0]["detail"]["status"] == "appeal"
    assert appeal_events[0]["detail"]["citations"] >= 1
