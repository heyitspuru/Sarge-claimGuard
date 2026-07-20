"""§9-2: partial approval -> clause-grounded appeal, every citation resolves."""
import json
from pathlib import Path

from claimguard.agents.negotiator import draft_appeal
from claimguard.coverage import PolicyRetriever, clause_ids, load_policies
from claimguard.models import DenialScenario


def _load_category(category: str) -> DenialScenario:
    for f in sorted(Path("data/denials").glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        if g["answer_key"]["category"] == category:
            return DenialScenario.model_validate(g["scenario"])
    raise AssertionError(f"no {category} scenario found")


def test_partial_sublimit_yields_grounded_appeal():
    from claimguard.llm import embed
    scenario = _load_category("partial_sublimit")
    policies = load_policies(Path("data/policies"))
    retriever = PolicyRetriever(policies, embed)

    # the model drafts an appeal citing a clause the retriever actually surfaced
    candidates = retriever(scenario.diagnosis, scenario.insurer_id, scenario.plan_id, 5)
    cited = candidates[0]["clause_id"]

    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "appeal",
                "appeal_text": "The sub-limit was applied more strictly than the policy states.",
                "citations": [{"clause_id": cited, "quoted_text": candidates[0]["text"][:30],
                               "relevance": "states the true cap"}],
                "reasoning": "Over-deduction against the stated sub-limit."}

    result = draft_appeal(scenario, retriever, llm=fake_llm)
    assert result.status == "appeal"
    assert result.citations, "a partial-approval appeal must cite at least one clause"
    corpus = clause_ids(policies)
    assert all(c.clause_id in corpus for c in result.citations)
    assert result.reasoning  # explainability trace
