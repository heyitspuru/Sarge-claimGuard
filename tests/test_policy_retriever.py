from claimguard.coverage import PolicyRetriever, load_policies
from claimguard.llm import embed


def _policies():
    from pathlib import Path
    return load_policies(Path("data/policies"))


def test_retriever_scopes_to_insurer_plan():
    policies = _policies()
    r = PolicyRetriever(policies, embed)
    hits = r("room rent deduction", insurer_id="SYNTH1", plan_id="PLANA", k=5)
    assert 1 <= len(hits) <= 5
    # every returned clause_id belongs to the SYNTH1-PLANA policy
    assert all(c["clause_id"].startswith("SYNTH1-PLANA-") for c in hits)
    # returned dicts carry the full clause shape
    assert all({"clause_id", "clause_type", "text", "structured"} <= c.keys() for c in hits)


def test_retriever_returns_empty_for_unknown_policy():
    r = PolicyRetriever(_policies(), embed)
    assert r("anything", insurer_id="NOPE", plan_id="NOPE", k=5) == []


def test_retriever_exact_text_ranks_its_own_clause_first():
    policies = _policies()
    # take a real clause and query with its own text -> mock embed is deterministic,
    # identical text -> cosine 1.0, so it ranks first within its policy
    star = next(p for p in policies if p["insurer_id"] == "SYNTH1")
    target = star["clauses"][3]
    r = PolicyRetriever(policies, embed)
    hits = r(target["text"], insurer_id="SYNTH1", plan_id="PLANA", k=5)
    assert hits[0]["clause_id"] == target["clause_id"]
