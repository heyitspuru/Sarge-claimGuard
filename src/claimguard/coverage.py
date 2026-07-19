"""Synthetic policy corpus loader.

Loads insurer policy JSON files (data/policies/*.json) and validates their
shape so downstream agents (Negotiator) can ground clause citations against
exactly these clause_ids.
"""

import json
from pathlib import Path

ALLOWED_CLAUSE_TYPES = {"coverage", "exclusion", "sub_limit", "waiting_period"}


def load_policies(policies_dir: Path) -> list[dict]:
    """Load and validate all policy JSON files in a directory."""
    policies = []
    seen_ids: set[str] = set()

    for path in sorted(Path(policies_dir).glob("*.json")):
        policy = json.loads(path.read_text(encoding="utf-8"))

        for field in ("insurer_id", "insurer_name", "plan_id", "plan_name", "clauses"):
            if field not in policy:
                raise ValueError(f"{path}: missing required field '{field}'")

        for clause in policy["clauses"]:
            for field in ("clause_id", "clause_type", "text", "structured"):
                if field not in clause:
                    raise ValueError(f"{path}: clause missing required field '{field}'")
            if clause["clause_type"] not in ALLOWED_CLAUSE_TYPES:
                raise ValueError(
                    f"{path}: clause {clause['clause_id']} has invalid "
                    f"clause_type '{clause['clause_type']}'"
                )
            if clause["clause_id"] in seen_ids:
                raise ValueError(f"{path}: duplicate clause_id '{clause['clause_id']}'")
            seen_ids.add(clause["clause_id"])

        policies.append(policy)

    return policies


def clause_ids(policies: list[dict]) -> set[str]:
    """Return the set of all clause_ids across the given policies."""
    return {clause["clause_id"] for policy in policies for clause in policy["clauses"]}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class PolicyRetriever:
    """Retrieve policy clauses scoped to one insurer+plan, cosine-ranked.

    The Negotiator grounds appeals only against the patient's own policy, so
    retrieval is keyed by (insurer_id, plan_id); clauses from other policies
    are never returned. Mirrors the ICD InMemoryRetriever.
    """

    def __init__(self, policies: list[dict], embed_fn):
        # index: (insurer_id, plan_id) -> list of (clause_dict, embedding)
        self._index: dict[tuple[str, str], list[tuple[dict, list[float]]]] = {}
        for policy in policies:
            key = (policy["insurer_id"], policy["plan_id"])
            clauses = policy["clauses"]
            vecs = embed_fn([c["text"] for c in clauses]) if clauses else []
            self._index[key] = list(zip(clauses, vecs))
        self._embed = embed_fn

    def __call__(self, query: str, insurer_id: str, plan_id: str, k: int = 5) -> list[dict]:
        entries = self._index.get((insurer_id, plan_id))
        if not entries:
            return []
        qv = self._embed([query])[0]
        ranked = sorted(entries, key=lambda e: _cosine(qv, e[1]), reverse=True)
        return [clause for clause, _ in ranked[:k]]
