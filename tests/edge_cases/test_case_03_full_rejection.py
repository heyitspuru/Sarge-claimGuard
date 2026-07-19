"""§9-3: full rejection on a genuine exclusion -> honest 'no valid appeal', no citations."""
import json
from pathlib import Path

from claimguard.agents.negotiator import draft_appeal
from claimguard.coverage import PolicyRetriever, load_policies
from claimguard.models import DenialScenario


def _load_category(category: str) -> DenialScenario:
    for f in sorted(Path("data/denials").glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        if g["answer_key"]["category"] == category:
            return DenialScenario.model_validate(g["scenario"])
    raise AssertionError(f"no {category} scenario found")


def test_genuine_exclusion_returns_honest_no():
    from claimguard.llm import embed
    scenario = _load_category("genuine_exclusion")
    retriever = PolicyRetriever(load_policies(Path("data/policies")), embed)

    # the model correctly judges the exclusion genuine and refuses
    def fake_llm(prompt, *, system="", tier="fast", json_schema=None):
        return {"status": "no_valid_appeal",
                "appeal_text": "The cited exclusion genuinely applies to this claim.",
                "citations": [], "reasoning": "Exclusion applies; no grounds to appeal."}

    result = draft_appeal(scenario, retriever, llm=fake_llm)
    assert result.status == "no_valid_appeal"
    assert result.citations == []
    assert result.reasoning
