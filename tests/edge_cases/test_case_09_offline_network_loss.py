"""§9-9 — offline / dropped network → graceful degradation, no data loss.

Two failure shapes matter here and they fail in opposite directions:

  - **Lost work**: the network drops and a completed claim vanishes, so it is never
    submitted and nobody knows.
  - **Duplicate work**: the network drops *after* the payer accepted the claim but
    before we recorded the acknowledgement, and a retry submits it a second time.

The Submitter is deterministic and keyed on record_id precisely so the retry path is
safe. These tests pin that: a retry after a drop must re-attach to the original
submission rather than mint a second one.
"""

from claimguard.agents.submitter import submit
from claimguard.eval import real_run
from claimguard.icd import IcdEntry, InMemoryRetriever
from claimguard.llm import _mock_embed
from claimguard.models import ClaimPackage, DischargeRecord, Insurance, Patient
from claimguard.orchestrator import PipelineDeps, run_claim


def _package(record_id="R9001"):
    return ClaimPackage(record_id=record_id, status="ready", fhir_claim={"resourceType": "Claim"})


def _record(record_id="R9001"):
    return DischargeRecord(
        record_id=record_id,
        patient=Patient(name="Test Patient", age=36, sex="F", abha_id="91-0000-0000-9001"),
        admission_date="2026-06-01", discharge_date="2026-06-03",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL-9001",
                            sum_insured=500000, claimed_amount=80000),
    )


def _flaky_llm(fail_times):
    """LLM that raises a connection error the first `fail_times` calls, then works."""
    state = {"calls": 0}

    def llm(prompt, *, system="", tier="fast", json_schema=None):
        state["calls"] += 1
        if state["calls"] <= fail_times:
            raise ConnectionError("network is unreachable")
        if json_schema and "codes" in str(json_schema):
            return {"codes": [{"icd_code": "K35.80", "description": "Acute appendicitis",
                               "confidence": 0.95}]}
        return {"primary_diagnosis": "Acute appendicitis", "secondary_diagnoses": [],
                "procedures": ["Laparoscopic appendectomy"], "medications": ["Inj Ceftriaxone"],
                "admission_course": "Uneventful."}

    return llm, state


def _deps(llm, store, audit=None):
    return PipelineDeps(
        llm=llm,
        retrieve=InMemoryRetriever([IcdEntry("K35.80", "Acute appendicitis")], _mock_embed),
        store=store, audit=audit if audit is not None else (lambda e: None),
    )


# --- no duplicate submission across a dropped connection ---


def test_retry_after_a_drop_reattaches_to_the_original_submission():
    store = {}
    first = submit(_package(), store)
    second = submit(_package(), store)  # the retry after a lost acknowledgement

    assert first.submission_id == second.submission_id, "a retry must not mint a second claim"
    assert len(store) == 1


def test_submission_id_is_derived_from_the_record_not_from_call_order():
    """Determinism is what makes the retry safe — nothing depends on when it ran."""
    assert submit(_package("R9001"), {}).submission_id == submit(_package("R9001"), {}).submission_id
    assert submit(_package("R9001"), {}).outcome == submit(_package("R9001"), {}).outcome


def test_a_dropped_run_leaves_no_partial_submission_behind():
    """If the pipeline dies before submit, the store must be empty, not half-written."""
    llm, _ = _flaky_llm(fail_times=99)  # never recovers
    store = {}
    result = run_claim(_record(), _deps(llm, store))

    assert result["final_status"] == "error"
    assert store == {}, "a failed run must not leave a phantom submission"


# --- graceful degradation: transient drops recover ---


def test_a_transient_drop_is_survived_by_the_retry_and_the_claim_completes():
    llm, state = _flaky_llm(fail_times=1)  # one blip, then the network returns
    store = {}
    result = run_claim(_record(), _deps(llm, store))

    assert result["final_status"] == "adjudicated", "a single blip must not lose the claim"
    assert state["calls"] > 1, "the retry path did not actually fire"
    assert len(store) == 1


def test_network_failures_are_recorded_in_the_audit_log():
    """No silent loss: a drop that cost work has to be visible afterwards."""
    llm, _ = _flaky_llm(fail_times=1)
    events = []
    run_claim(_record(), _deps(llm, {}, audit=events.append))

    errors = [e for e in events if e["status"] == "error"]
    assert errors, "a dropped connection left no trace in the audit log"
    assert "network" in errors[0]["detail"]["error"].lower()


# --- durable progress: an interrupted batch resumes without reprocessing ---


def test_interrupted_batch_resumes_from_its_checkpoint(tmp_path):
    """The eval checkpoint is the durability mechanism for long multi-day runs."""
    ckpt = tmp_path / "ckpt.jsonl"
    row = {"record_id": "R9001", "icd_codes": ["K35.80"], "expected_icd": ["K35.80"],
           "f1": 1.0, "packaging": "ready", "expected_packaging": "ready", "errored": False}
    ckpt.write_text(__import__("json").dumps(row) + "\n", encoding="utf-8")

    assert "R9001" in real_run.load_checkpoint(ckpt)
    # a record already recorded is never handed out for reprocessing
    assert real_run.select_records(tmp_path, done={"R9001"}, limit=10) == []


def test_a_half_written_checkpoint_line_costs_one_record_not_the_run(tmp_path):
    ckpt = tmp_path / "ckpt.jsonl"
    good = {"record_id": "R9001", "icd_codes": [], "expected_icd": [], "f1": 0.0,
            "packaging": "ready", "expected_packaging": "ready", "errored": False}
    ckpt.write_text(__import__("json").dumps(good) + "\n" + '{"record_id": "R9002"',
                    encoding="utf-8")

    survived = real_run.load_checkpoint(ckpt)
    assert list(survived) == ["R9001"], "a torn write must not discard completed work"
