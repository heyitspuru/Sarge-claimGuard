from claimguard.agents.negotiator import draft_appeal
from claimguard.models import DenialScenario, InsurerDecision


def _scenario():
    return DenialScenario(
        scenario_id="D001", insurer_id="SYNTH1", plan_id="PLANA",
        diagnosis="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        decision=InsurerDecision(
            claim_id="CLM-D001", insurer_id="SYNTH1", plan_id="PLANA",
            outcome="partial", claimed_amount=100000, approved_amount=80000,
            reason_text="Room rent restricted to Rs.5000/day; excess disallowed.",
            cited_clause_id="SYNTH1-PLANA-C02",
        ),
    )


# candidates the fake retriever returns (subset of the real corpus)
_CANDIDATES = [
    {"clause_id": "SYNTH1-PLANA-C02", "clause_type": "sub_limit",
     "text": "Room rent limited to 1% of SI per day, max Rs.7500/day.", "structured": {}},
    {"clause_id": "SYNTH1-PLANA-C01", "clause_type": "coverage",
     "text": "The Company shall indemnify hospitalisation expenses.", "structured": {}},
]


def _retrieve(query, insurer_id, plan_id, k=5):
    return list(_CANDIDATES)


def test_viable_appeal_cites_real_clause():
    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "appeal", "appeal_text": "We appeal the deduction.",
                "citations": [{"clause_id": "SYNTH1-PLANA-C02",
                               "quoted_text": "max Rs.7500/day", "relevance": "true cap is 7500"}],
                "reasoning": "Sub-limit was over-applied."}
    r = draft_appeal(_scenario(), _retrieve, llm=fake_llm)
    assert r.status == "appeal"
    assert [c.clause_id for c in r.citations] == ["SYNTH1-PLANA-C02"]
    assert r.reasoning  # explainability trace present


def test_no_valid_appeal_carries_no_citations():
    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "no_valid_appeal", "appeal_text": "The exclusion genuinely applies.",
                "citations": [{"clause_id": "SYNTH1-PLANA-C01", "quoted_text": "x", "relevance": "y"}],
                "reasoning": "Pre-existing exclusion applies."}
    r = draft_appeal(_scenario(), _retrieve, llm=fake_llm)
    assert r.status == "no_valid_appeal"
    assert r.citations == []  # a refusal cites nothing


def test_hallucinated_clause_is_dropped_and_downgrades_to_refusal():
    # THE key negative test (§9-12): llm tries to cite a clause not in the corpus.
    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "appeal", "appeal_text": "Appeal on fabricated grounds.",
                "citations": [{"clause_id": "SYNTH1-PLANA-C99",  # does NOT exist
                               "quoted_text": "invented", "relevance": "fabricated"}],
                "reasoning": "..."}
    r = draft_appeal(_scenario(), _retrieve, llm=fake_llm)
    assert r.status == "no_valid_appeal"          # cannot appeal without grounding
    assert r.citations == []                       # the fabricated citation is gone
    assert all(c.clause_id != "SYNTH1-PLANA-C99" for c in r.citations)


def test_mixed_citations_keeps_only_grounded_ones():
    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "appeal", "appeal_text": "Appeal.",
                "citations": [
                    {"clause_id": "SYNTH1-PLANA-C02", "quoted_text": "real", "relevance": "a"},
                    {"clause_id": "SYNTH1-PLANA-C99", "quoted_text": "fake", "relevance": "b"},
                ],
                "reasoning": "..."}
    r = draft_appeal(_scenario(), _retrieve, llm=fake_llm)
    assert r.status == "appeal"
    assert [c.clause_id for c in r.citations] == ["SYNTH1-PLANA-C02"]


def test_degenerate_llm_output_defaults_to_refusal():
    # mock provider returns empty status -> must not crash, must refuse safely
    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "", "appeal_text": "", "citations": [], "reasoning": ""}
    r = draft_appeal(_scenario(), _retrieve, llm=fake_llm)
    assert r.status == "no_valid_appeal"
    assert r.citations == []


def test_quoted_text_comes_from_the_real_clause_not_the_model():
    # the model attaches a fabricated quotation to a real clause_id -> the gate
    # replaces it with the clause's authoritative text (no fabricated quotes).
    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "appeal", "appeal_text": "Appeal.",
                "citations": [{"clause_id": "SYNTH1-PLANA-C02",
                               "quoted_text": "the policy pays 100% with no cap",  # false
                               "relevance": "a"}],
                "reasoning": "..."}
    r = draft_appeal(_scenario(), _retrieve, llm=fake_llm)
    real_text = next(c["text"] for c in _CANDIDATES if c["clause_id"] == "SYNTH1-PLANA-C02")
    assert r.citations[0].quoted_text == real_text
    assert "no cap" not in r.citations[0].quoted_text


def test_malformed_citation_shapes_refuse_instead_of_crashing():
    # citations as strings, clause_id as a list -> must not raise; refuse safely.
    for bad in (["SYNTH1-PLANA-C02"], "SYNTH1-PLANA-C02",
                [{"clause_id": ["SYNTH1-PLANA-C02"], "quoted_text": "x", "relevance": "y"}]):
        def fake_llm(prompt, *, system="", tier="fast", json_schema=None, _bad=bad):
            return {"status": "appeal", "appeal_text": "x", "citations": _bad, "reasoning": "r"}
        r = draft_appeal(_scenario(), _retrieve, llm=fake_llm)
        assert r.status == "no_valid_appeal"
        assert r.citations == []
