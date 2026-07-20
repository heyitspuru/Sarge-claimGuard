"""§9-10 — ABHA identity linkage + duplicate/fraud flag.

The invariant is that a suspected duplicate is **flagged, never blocked**. Most repeat
(ABHA, admission date) pairs are resubmissions or data-entry artifacts rather than
fraud, and a system that silently refuses legitimate claims harms the patient it exists
to serve. Flagging routes to a human; blocking substitutes an automated guess for a
judgement that isn't the system's to make.
"""

from claimguard import fraud
from claimguard.icd import IcdEntry, InMemoryRetriever
from claimguard.llm import _mock_embed
from claimguard.models import DischargeRecord, Insurance, Patient
from claimguard.orchestrator import PipelineDeps, run_claim


def _record(record_id="R1001", abha="91-0000-0000-1001", admission="2026-05-01",
            name="Test Patient"):
    return DischargeRecord(
        record_id=record_id,
        patient=Patient(name=name, age=52, sex="F", abha_id=abha),
        admission_date=admission, discharge_date="2026-05-04",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL-1001",
                            sum_insured=500000, claimed_amount=80000),
    )


def _llm(prompt, *, system="", tier="fast", json_schema=None):
    if json_schema and "codes" in str(json_schema):
        return {"codes": [{"icd_code": "K35.80", "description": "Acute appendicitis",
                           "confidence": 0.95}]}
    return {"primary_diagnosis": "Acute appendicitis", "secondary_diagnoses": [],
            "procedures": ["Laparoscopic appendectomy"], "medications": ["Inj Ceftriaxone"],
            "admission_course": "Uneventful."}


def _deps(index, store=None, audit=None):
    return PipelineDeps(
        llm=_llm,
        retrieve=InMemoryRetriever([IcdEntry("K35.80", "Acute appendicitis")], _mock_embed),
        store=store if store is not None else {},
        audit=audit if audit is not None else (lambda e: None),
        admission_index=index,
    )


def test_duplicate_admission_is_flagged():
    index = {}
    assert fraud.check(_record("R1001"), index) == []

    flags = fraud.check(_record("R1002"), index)  # same ABHA + admission date
    assert len(flags) == 1
    assert fraud.DUPLICATE_ADMISSION in flags[0]
    assert "R1001" in flags[0], "the flag must name the claim it collides with"


def test_same_patient_different_admission_is_not_a_duplicate():
    index = {}
    fraud.check(_record("R1001", admission="2026-05-01"), index)
    assert fraud.check(_record("R1002", admission="2026-09-14"), index) == []


def test_reprocessing_the_same_record_id_is_not_a_duplicate():
    """Re-running a claim is routine and must not flag itself."""
    index = {}
    fraud.check(_record("R1001"), index)
    assert fraud.check(_record("R1001"), index) == []


def test_flagged_claim_still_completes():
    """The hard invariant: flag, don't block."""
    index = {}
    store = {}
    run_claim(_record("R1001"), _deps(index, store=store))
    result = run_claim(_record("R1002"), _deps(index, store=store))

    assert result["final_status"] == "adjudicated", "a flagged claim must not be denied"
    assert result["flags"], "the flag must survive to the caller"
    assert fraud.DUPLICATE_ADMISSION in result["flags"][0]


def test_flag_is_audited():
    index = {}
    events = []
    run_claim(_record("R1001"), _deps(index))
    run_claim(_record("R1002"), _deps(index, audit=events.append))

    flagged = [e for e in events if e["status"] == "flagged"]
    assert len(flagged) == 1
    assert flagged[0]["detail"]["flags"]


def test_no_index_configured_leaves_behaviour_unchanged():
    result = run_claim(_record(), PipelineDeps(
        llm=_llm,
        retrieve=InMemoryRetriever([IcdEntry("K35.80", "Acute appendicitis")], _mock_embed),
        store={}, audit=lambda e: None,
    ))
    assert result["final_status"] == "adjudicated"
    assert result["flags"] == []


def test_identity_linkage_groups_records_by_abha():
    records = [_record("R1001"), _record("R1002"), _record("R1003", abha="91-0000-0000-9999")]
    linked = fraud.link_identities(records)

    assert linked["91-0000-0000-1001"] == ["R1001", "R1002"]
    assert linked["91-0000-0000-9999"] == ["R1003"]


def test_same_abha_under_different_names_is_an_identity_red_flag():
    records = [_record("R1001", name="Asha Rao"), _record("R1002", name="Ravi Kumar")]
    conflicts = fraud.name_conflicts(records)

    assert "91-0000-0000-1001" in conflicts
    assert conflicts["91-0000-0000-1001"] == {"Asha Rao", "Ravi Kumar"}


def test_consistent_identities_produce_no_conflict():
    records = [_record("R1001", name="Asha Rao"), _record("R1002", name="Asha Rao")]
    assert fraud.name_conflicts(records) == {}
