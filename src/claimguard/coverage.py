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
