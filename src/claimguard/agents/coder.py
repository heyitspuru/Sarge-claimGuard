from claimguard import llm
from claimguard.models import CodedDiagnosis, DischargeSummary

SYSTEM = "Assign ICD-10 codes ONLY from the candidate list. Report your confidence honestly."

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "codes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "icd_code": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["icd_code", "confidence"],
            },
        },
    },
    "required": ["codes"],
}


# ponytail: single-query retrieval; per-secondary-diagnosis queries when multi-morbidity accuracy matters.
def assign_codes(summary: DischargeSummary, retrieve, llm=llm.complete,
                  threshold: float = 0.7) -> list[CodedDiagnosis]:
    query = " ".join([summary.primary_diagnosis, *summary.secondary_diagnoses])
    candidates = retrieve(query, 5)
    by_code = {c.code: c for c in candidates}

    prompt = "Candidates:\n" + "\n".join(f"{c.code} — {c.description}" for c in candidates)
    result = llm(prompt, system=SYSTEM, tier="fast", json_schema=JSON_SCHEMA)

    codes = [
        CodedDiagnosis(
            icd_code=entry["icd_code"],
            description=by_code[entry["icd_code"]].description,
            confidence=entry["confidence"],
            needs_review=entry["confidence"] < threshold,
        )
        for entry in result.get("codes", [])
        if entry["icd_code"] in by_code
    ]

    if not codes and candidates:
        top = candidates[0]
        codes = [CodedDiagnosis(icd_code=top.code, description=top.description,
                                 confidence=0.5, needs_review=True)]

    return codes
