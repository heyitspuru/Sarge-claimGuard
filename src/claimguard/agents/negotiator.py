"""Negotiation / Appeal agent — the centerpiece.

Given an insurer decision + the patient's policy clauses, drafts a
clause-grounded appeal, or returns an honest "no valid appeal". The hard rule
(CLAUDE.md prime directive 2) is enforced deterministically, not by trusting
the LLM: every citation the model emits is filtered against the clauses that
were actually retrieved from the patient's policy, so a citation whose
clause_id is not in the corpus can never survive into the AppealResult. An
"appeal" left with no grounded citation is downgraded to "no_valid_appeal".
"""
from claimguard import llm as _llm
from claimguard.models import AppealResult, Citation, DenialScenario

_SYSTEM = (
    "You are an insurance claims-appeal advocate whose credibility depends on "
    "raising ONLY grounded appeals — declining a weak or genuinely-excluded case "
    "is a correct outcome, not a failure. You are given an insurer's decision and "
    "the patient's own policy clauses (candidates). Draft an appeal ONLY when a "
    "candidate clause genuinely supports one, and cite ONLY the clause_id values "
    "from the provided candidates. If no candidate supports an appeal — the "
    "exclusion truly applies, or the basis is contradictory or absent — return "
    "status \"no_valid_appeal\" and explain why. Never invent a clause or cite an "
    "id that is not in the candidate list, and never invent a quotation: quote a "
    "clause only as its text actually reads. A persuasive but ungrounded appeal "
    "is a failure."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["appeal", "no_valid_appeal"]},
        "appeal_text": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause_id": {"type": "string"},
                    "quoted_text": {"type": "string"},
                    "relevance": {"type": "string"},
                },
                "required": ["clause_id", "quoted_text", "relevance"],
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["status", "appeal_text", "citations", "reasoning"],
}


def draft_appeal(scenario: DenialScenario, retrieve, llm=_llm.complete) -> AppealResult:
    d = scenario.decision
    candidates = retrieve(
        f"{scenario.diagnosis}. {d.reason_text}",
        scenario.insurer_id, scenario.plan_id, 5,
    )

    clause_lines = "\n".join(
        f"- {c['clause_id']} | {c['clause_type']} | {c['text']}" for c in candidates
    ) or "(no clauses found for this policy)"
    prompt = (
        f"Insurer decision: {d.outcome}. Claimed Rs.{d.claimed_amount}, "
        f"approved Rs.{d.approved_amount}. Reason: {d.reason_text}\n"
        f"Insurer cited clause: {d.cited_clause_id or 'none'}\n"
        f"Diagnosis: {scenario.diagnosis}; procedures: {', '.join(scenario.procedures)}\n\n"
        f"Candidate policy clauses (cite only these clause_ids):\n{clause_lines}"
    )

    result = llm(prompt, system=_SYSTEM, tier="reasoning", json_schema=_SCHEMA)
    if not isinstance(result, dict):
        result = {}

    status = result.get("status")
    if status not in ("appeal", "no_valid_appeal"):
        status = "no_valid_appeal"  # degenerate/empty output -> refuse safely
    reasoning = result.get("reasoning", "") or ""
    appeal_text = result.get("appeal_text", "") or ""

    # Deterministic grounding gate: keep only citations that resolve to a
    # retrieved candidate clause, and quote the clause's REAL text — never the
    # model's, since a fabricated quotation on a real clause_id is still a
    # fabrication. Malformed citation shapes degrade to a refusal, not a crash.
    citations: list[Citation] = []
    if status == "appeal":
        cand_by_id = {c["clause_id"]: c for c in candidates}
        raw = result.get("citations")
        if not isinstance(raw, list):
            raw = []
        seen: set[str] = set()
        for c in raw:
            if not isinstance(c, dict):
                continue
            cid = c.get("clause_id")
            if not isinstance(cid, str) or cid not in cand_by_id or cid in seen:
                continue
            seen.add(cid)
            citations.append(Citation(
                clause_id=cid,
                quoted_text=cand_by_id[cid]["text"],  # authoritative clause text
                relevance=str(c.get("relevance", "") or ""),
            ))
        if not citations:
            # an appeal with nothing grounded is not an appeal
            status = "no_valid_appeal"
            reasoning = ("No policy clause supports an appeal. " + reasoning).strip()

    return AppealResult(
        scenario_id=scenario.scenario_id,
        status=status,
        appeal_text=appeal_text,
        citations=citations,
        reasoning=reasoning,
    )
