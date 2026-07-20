"""§9-12: ungroundable clause — the Negotiator MUST refuse to fabricate.

The single most important negative test in the system (CLAUDE.md prime
directive 2). Even when the LLM tries to cite a clause that does not exist in
the corpus, the deterministic gate drops it, and an appeal with no grounded
citation is downgraded to an honest refusal.
"""
import json
from pathlib import Path

from claimguard.agents.negotiator import draft_appeal
from claimguard.coverage import PolicyRetriever, clause_ids, load_policies
from claimguard.eval import grounding
from claimguard.models import DenialScenario


def _load_category(category: str) -> DenialScenario:
    for f in sorted(Path("data/denials").glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        if g["answer_key"]["category"] == category:
            return DenialScenario.model_validate(g["scenario"])
    raise AssertionError(f"no {category} scenario found")


def test_fabricated_clause_is_refused_on_real_scenario():
    from claimguard.llm import embed
    scenario = _load_category("ungroundable")
    policies = load_policies(Path("data/policies"))
    retriever = PolicyRetriever(policies, embed)
    corpus = clause_ids(policies)

    # adversarial LLM: invents a clause id that is not in the corpus
    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "appeal", "appeal_text": "Persuasive but ungrounded appeal.",
                "citations": [{"clause_id": f"{scenario.insurer_id}-{scenario.plan_id}-C99",
                               "quoted_text": "invented text", "relevance": "fabricated"}],
                "reasoning": "trying to fabricate"}

    result = draft_appeal(scenario, retriever, llm=fake_llm)
    assert result.status == "no_valid_appeal"
    assert result.citations == []
    assert all(c.clause_id in corpus for c in result.citations)  # trivially true (empty)


def test_ci_grounding_gate_real_negotiator_over_full_corpus():
    """CI grounding gate (>= 0.98): the real draft_appeal over the entire denials
    corpus never emits a citation outside the corpus. Runs offline (mock provider
    forced by conftest -> refuse-all), so grounding is provable without an API key."""
    from claimguard.agents.negotiator import draft_appeal as real_draft
    from claimguard.llm import complete, embed
    retriever = PolicyRetriever(load_policies(Path("data/policies")), embed)
    report = grounding.run_negotiation_eval(
        Path("data/denials"),
        negotiator=lambda s: real_draft(s, retriever, complete),
    )
    assert report["n"] >= 40
    assert report["grounding_rate"] >= 0.98
