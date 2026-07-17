from claimguard.agents.coder import assign_codes
from claimguard.icd import IcdEntry
from claimguard.models import DischargeSummary

CANDIDATES = [
    IcdEntry("K35.9", "Acute appendicitis, unspecified"),
    IcdEntry("K35.80", "Unspecified acute appendicitis"),
    IcdEntry("K37", "Unspecified appendicitis"),
]


def _summary(**kw):
    base = dict(
        record_id="R0001",
        primary_diagnosis="Acute appendicitis",
        secondary_diagnoses=[],
        procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone 1g IV BD"],
        admission_course="Admitted with RIF pain; surgery day 1; uneventful recovery.",
        source_fields={},
    )
    return DischargeSummary(**(base | kw))


def _fake_retrieve(candidates=CANDIDATES):
    def fn(query, k=5):
        return candidates
    return fn


def _fake_llm(result):
    def fn(prompt, *, system="", tier="fast", json_schema=None):
        return result
    return fn


def test_confident_code_not_flagged():
    result = {"codes": [{"icd_code": "K35.9", "confidence": 0.92}]}
    codes = assign_codes(_summary(), _fake_retrieve(), llm=_fake_llm(result))

    assert len(codes) == 1
    assert codes[0].icd_code == "K35.9"
    assert codes[0].description == "Acute appendicitis, unspecified"
    assert codes[0].confidence == 0.92
    assert codes[0].needs_review is False


def test_low_confidence_flagged():
    result = {"codes": [{"icd_code": "K35.9", "confidence": 0.4}]}
    codes = assign_codes(_summary(), _fake_retrieve(), llm=_fake_llm(result))

    assert len(codes) == 1
    assert codes[0].needs_review is True


def test_unretrieved_code_dropped_falls_back_to_top_candidate():
    result = {"codes": [{"icd_code": "Z99.9", "confidence": 0.9}]}
    codes = assign_codes(_summary(), _fake_retrieve(), llm=_fake_llm(result))

    assert len(codes) == 1
    assert codes[0].icd_code == CANDIDATES[0].code
    assert codes[0].description == CANDIDATES[0].description
    assert codes[0].confidence == 0.5
    assert codes[0].needs_review is True


def test_empty_codes_falls_back_to_top_candidate():
    result = {"codes": []}
    codes = assign_codes(_summary(), _fake_retrieve(), llm=_fake_llm(result))

    assert len(codes) == 1
    assert codes[0].icd_code == CANDIDATES[0].code
    assert codes[0].confidence == 0.5
    assert codes[0].needs_review is True
