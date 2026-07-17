from fhir.resources.claim import Claim

from claimguard.models import ClaimPackage, CodedDiagnosis, DischargeRecord, DischargeSummary
from claimguard.synth.templates import REQUIRED_DOCS


def package(record: DischargeRecord, summary: DischargeSummary, codes: list[CodedDiagnosis]) -> ClaimPackage:
    missing = [d for d in REQUIRED_DOCS[record.claim_type] if d not in record.documents]
    if missing:
        return ClaimPackage(record_id=record.record_id, status="rejected",
                             rejection_reasons=[f"missing document: {d}" for d in missing])

    if not codes:
        return ClaimPackage(record_id=record.record_id, status="rejected",
                             rejection_reasons=["no ICD codes assigned"])

    low_confidence = [c for c in codes if c.needs_review]
    if low_confidence:
        return ClaimPackage(record_id=record.record_id, status="needs_review",
                             rejection_reasons=[f"low-confidence code: {c.icd_code}" for c in low_confidence])

    # ponytail: NHCX profile checks = FHIR R4 base validation; add NHCX-specific
    # profile constraints when targeting the real sandbox.
    claim = Claim.model_validate({
        "status": "active",
        "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type",
                              "code": "institutional"}]},
        "use": "claim",
        "patient": {"display": record.patient.name},
        "created": record.discharge_date,
        "provider": {"display": "ClaimGuard Simulated Provider"},
        "priority": {"coding": [{"code": "normal"}]},
        "insurance": [{"sequence": 1, "focal": True,
                        "coverage": {"display": record.insurance.policy_number}}],
        "diagnosis": [
            {"sequence": i + 1,
             "diagnosisCodeableConcept": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10",
                                                       "code": code.icd_code}]}}
            for i, code in enumerate(codes)
        ],
        "supportingInfo": [
            {"sequence": i + 1, "category": {"coding": [{"code": "info"}]}, "valueString": doc}
            for i, doc in enumerate(record.documents)
        ],
    })

    return ClaimPackage(record_id=record.record_id, status="ready",
                         fhir_claim=claim.model_dump(mode="json", exclude_none=True))
