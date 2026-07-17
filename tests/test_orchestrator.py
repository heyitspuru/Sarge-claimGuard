from claimguard import orchestrator
from claimguard.models import (
    ClaimPackage,
    CodedDiagnosis,
    DischargeSummary,
    Insurance,
    Patient,
    SubmissionResult,
)
from claimguard.orchestrator import PipelineDeps, run_claim


def _record(**kw):
    base = dict(
        record_id="R0001",
        patient=Patient(name="Asha Rao", age=34, sex="F", abha_id="12-3456-7890-0001"),
        admission_date="2026-07-01", discharge_date="2026-07-04",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone 1g IV BD"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL123",
                             sum_insured=500000, claimed_amount=80000),
    )
    from claimguard.models import DischargeRecord
    return DischargeRecord(**(base | kw))


def _summary(record):
    return DischargeSummary(
        record_id=record.record_id,
        primary_diagnosis=record.diagnosis_text,
        secondary_diagnoses=[],
        procedures=record.procedures,
        medications=record.medications,
        admission_course=record.clinical_notes,
        source_fields={},
    )


def _codes():
    return [CodedDiagnosis(icd_code="K35.9", description="Acute appendicitis, unspecified",
                            confidence=0.9, needs_review=False)]


def _deps(events):
    return PipelineDeps(llm=None, retrieve=None, store={}, audit=events.append)


def _seq(events):
    return [(e["step"], e["status"]) for e in events]


def test_happy_path_adjudicated(monkeypatch):
    record = _record()
    monkeypatch.setattr(orchestrator, "summarize", lambda r, llm=None: _summary(r))
    monkeypatch.setattr(orchestrator, "assign_codes", lambda s, retrieve, llm=None: _codes())
    monkeypatch.setattr(orchestrator, "package",
                         lambda r, s, c: ClaimPackage(record_id=r.record_id, status="ready",
                                                       fhir_claim={"resourceType": "Claim"}))
    monkeypatch.setattr(orchestrator, "submit",
                         lambda pkg, store: SubmissionResult(record_id=pkg.record_id,
                                                              submission_id=f"SIM-{pkg.record_id}",
                                                              status="adjudicated", outcome="approved"))

    events = []
    result = run_claim(record, _deps(events))

    assert result["final_status"] == "adjudicated"
    assert result["icd_codes"] == ["K35.9"]
    assert result["packaging"] == "ready"
    assert result["outcome"] == "approved"
    assert _seq(events) == [
        ("summarize", "start"), ("summarize", "ok"),
        ("code", "start"), ("code", "ok"),
        ("package", "start"), ("package", "ok"),
        ("submit", "start"), ("submit", "ok"),
    ]


def test_missing_doc_rejects_without_submit(monkeypatch):
    record = _record(documents=["discharge_summary"])
    monkeypatch.setattr(orchestrator, "summarize", lambda r, llm=None: _summary(r))
    monkeypatch.setattr(orchestrator, "assign_codes", lambda s, retrieve, llm=None: _codes())
    monkeypatch.setattr(orchestrator, "package",
                         lambda r, s, c: ClaimPackage(record_id=r.record_id, status="rejected",
                                                       rejection_reasons=["missing document: final_bill"]))

    def _fail_submit(pkg, store):
        raise AssertionError("submit must not run for a rejected package")

    monkeypatch.setattr(orchestrator, "submit", _fail_submit)

    events = []
    result = run_claim(record, _deps(events))

    assert result["final_status"] == "rejected"
    assert result["outcome"] is None
    assert result["packaging"] == "rejected"
    assert not any(e["step"] == "submit" for e in events)


def test_summarize_retried_once_then_succeeds(monkeypatch):
    record = _record()
    calls = {"n": 0}

    def flaky_summarize(r, llm=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient LLM error")
        return _summary(r)

    monkeypatch.setattr(orchestrator, "summarize", flaky_summarize)
    monkeypatch.setattr(orchestrator, "assign_codes", lambda s, retrieve, llm=None: _codes())
    monkeypatch.setattr(orchestrator, "package",
                         lambda r, s, c: ClaimPackage(record_id=r.record_id, status="ready",
                                                       fhir_claim={"resourceType": "Claim"}))
    monkeypatch.setattr(orchestrator, "submit",
                         lambda pkg, store: SubmissionResult(record_id=pkg.record_id,
                                                              submission_id=f"SIM-{pkg.record_id}",
                                                              status="adjudicated", outcome="partial"))

    events = []
    result = run_claim(record, _deps(events))

    assert result["final_status"] == "adjudicated"
    assert _seq(events) == [
        ("summarize", "start"), ("summarize", "error"), ("summarize", "ok"),
        ("code", "start"), ("code", "ok"),
        ("package", "start"), ("package", "ok"),
        ("submit", "start"), ("submit", "ok"),
    ]


def test_summarize_always_fails_yields_error(monkeypatch):
    record = _record()

    def always_fails(r, llm=None):
        raise RuntimeError("LLM is down")

    monkeypatch.setattr(orchestrator, "summarize", always_fails)

    def _unreached(*a, **kw):
        raise AssertionError("must not be reached after summarize fails")

    monkeypatch.setattr(orchestrator, "assign_codes", _unreached)
    monkeypatch.setattr(orchestrator, "package", _unreached)
    monkeypatch.setattr(orchestrator, "submit", _unreached)

    events = []
    result = run_claim(record, _deps(events))

    assert result["final_status"] == "error"
    assert result["icd_codes"] == []
    assert result["outcome"] is None
    assert _seq(events) == [("summarize", "start"), ("summarize", "error"), ("summarize", "error")]
    assert not any(e["step"] in {"code", "package", "submit"} for e in events)
