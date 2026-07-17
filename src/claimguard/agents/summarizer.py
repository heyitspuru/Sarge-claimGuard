from claimguard import llm
from claimguard.models import DischargeRecord, DischargeSummary

SYSTEM = (
    "You are a clinical summarizer. Use ONLY facts present in the record. "
    "Never invent findings, dates, or treatments."
)

SOURCE_FIELDS = {
    "primary_diagnosis": "diagnosis_text",
    "secondary_diagnoses": "diagnosis_text",
    "procedures": "procedures",
    "medications": "medications",
    "admission_course": "clinical_notes",
}

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_diagnosis": {"type": "string"},
        "secondary_diagnoses": {"type": "array", "items": {"type": "string"}},
        "procedures": {"type": "array", "items": {"type": "string"}},
        "medications": {"type": "array", "items": {"type": "string"}},
        "admission_course": {"type": "string"},
    },
    "required": list(SOURCE_FIELDS),
}


def summarize(record: DischargeRecord, llm=llm.complete) -> DischargeSummary:
    prompt = (
        f"Diagnosis: {record.diagnosis_text}\n"
        f"Procedures: {', '.join(record.procedures)}\n"
        f"Medications: {', '.join(record.medications)}\n"
        f"Clinical notes: {record.clinical_notes}\n"
        f"Admission date: {record.admission_date}\n"
        f"Discharge date: {record.discharge_date}\n"
    )
    result = llm(prompt, system=SYSTEM, tier="reasoning", json_schema=JSON_SCHEMA)
    return DischargeSummary(
        record_id=record.record_id,
        source_fields=SOURCE_FIELDS,
        **{k: result[k] for k in SOURCE_FIELDS},
    )
