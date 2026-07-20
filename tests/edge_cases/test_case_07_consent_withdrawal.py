"""§9-7 — consent withdrawal mid-process → stop + honor erasure interface.

Two distinct obligations, and passing only the first is a failure: **stop** processing,
and **erase** what was already produced. The withdrawal must be honoured whenever it
arrives, including partway through a claim — a gate that only fires at intake is not a
withdrawal mechanism.
"""

from claimguard.consent import ConsentRegistry, erase
from claimguard.icd import IcdEntry, InMemoryRetriever
from claimguard.llm import _mock_embed
from claimguard.models import DischargeRecord, Insurance, Patient
from claimguard.orchestrator import PipelineDeps, run_claim


def _record(record_id="R7001"):
    return DischargeRecord(
        record_id=record_id,
        patient=Patient(name="Test Patient", age=44, sex="M", abha_id="91-0000-0000-7001"),
        admission_date="2026-04-01", discharge_date="2026-04-04",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL-7001",
                            sum_insured=500000, claimed_amount=80000),
    )


def _llm(prompt, *, system="", tier="fast", json_schema=None):
    if json_schema and "codes" in str(json_schema):
        return {"codes": [{"icd_code": "K35.80", "description": "Acute appendicitis",
                           "confidence": 0.95}]}
    return {"primary_diagnosis": "Acute appendicitis", "secondary_diagnoses": [],
            "procedures": ["Laparoscopic appendectomy"], "medications": ["Inj Ceftriaxone"],
            "admission_course": "Uneventful."}


def _deps(consent=None, store=None, audit=None):
    return PipelineDeps(
        llm=_llm,
        retrieve=InMemoryRetriever([IcdEntry("K35.80", "Acute appendicitis")], _mock_embed),
        store=store if store is not None else {},
        audit=audit if audit is not None else (lambda e: None),
        consent=consent,
    )


def test_withdrawal_before_intake_stops_the_claim_entirely():
    registry = ConsentRegistry({"R7001"})
    store = {}
    result = run_claim(_record(), _deps(consent=registry, store=store))

    assert result["final_status"] == "consent_withdrawn"
    assert result["outcome"] is None
    assert store == {}, "a withdrawn claim must never reach submission"


def test_withdrawal_arriving_mid_pipeline_still_halts():
    """The realistic case: consent is live at intake and withdrawn while work is running."""
    registry = ConsentRegistry()
    calls = {"n": 0}

    def consent_check(record_id):
        # live for the intake check, withdrawn by the time packaging is reached
        calls["n"] += 1
        if calls["n"] > 1:
            registry.withdraw(record_id)
        return registry.is_withdrawn(record_id)

    store = {}
    result = run_claim(_record(), _deps(consent=consent_check, store=store))

    assert result["final_status"] == "consent_withdrawn"
    assert calls["n"] > 1, "consent must be re-checked between steps, not only at entry"
    assert store == {}, "no submission after a mid-pipeline withdrawal"


def test_consent_intact_claim_proceeds_normally():
    result = run_claim(_record(), _deps(consent=ConsentRegistry()))
    assert result["final_status"] == "adjudicated"


def test_no_consent_registry_configured_does_not_block():
    """Absent a registry the pipeline behaves exactly as before — opt-in, not a new gate."""
    assert run_claim(_record(), _deps(consent=None))["final_status"] == "adjudicated"


def test_halt_is_recorded_in_the_audit_log():
    """A withdrawal the system cannot evidence is not auditable."""
    events = []
    run_claim(_record(), _deps(consent=ConsentRegistry({"R7001"}), audit=events.append))

    halted = [e for e in events if e["status"] == "halted"]
    assert len(halted) == 1
    assert halted[0]["detail"]["reason"] == "consent_withdrawn"
    assert halted[0]["record_id"] == "R7001"


def test_erasure_purges_stores_and_audit_trail():
    """Stopping is not enough — what was already produced has to go."""
    events = []
    store = {}
    deps = _deps(store=store, audit=events.append)
    run_claim(_record(), deps)

    assert "R7001" in store
    assert any(e["record_id"] == "R7001" for e in events)

    receipt = erase("R7001", store, audit_log=events)

    assert receipt["erased"] is True
    assert receipt["stores_purged"] == 1
    assert receipt["audit_entries_removed"] > 0
    assert "R7001" not in store
    assert not [e for e in events if e.get("record_id") == "R7001"]


def test_erasure_of_an_unknown_record_is_a_no_op_not_an_error():
    receipt = erase("NEVER-EXISTED", {}, audit_log=[])
    assert receipt["erased"] is True
    assert receipt["stores_purged"] == 0


def test_erasure_leaves_other_patients_untouched():
    store = {"R7001": "a", "R7002": "b"}
    events = [{"record_id": "R7001"}, {"record_id": "R7002"}]
    erase("R7001", store, audit_log=events)

    assert list(store) == ["R7002"]
    assert [e["record_id"] for e in events] == ["R7002"]
