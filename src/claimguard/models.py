from typing import Literal
from pydantic import BaseModel, Field


class Patient(BaseModel):
    name: str
    age: int
    sex: str
    abha_id: str


class Insurance(BaseModel):
    insurer_id: str
    plan_id: str
    policy_number: str
    sum_insured: int
    claimed_amount: int


class DischargeRecord(BaseModel):
    record_id: str
    patient: Patient
    admission_date: str
    discharge_date: str
    claim_type: Literal["cashless", "reimbursement"]
    specialty: str
    diagnosis_text: str
    procedures: list[str]
    medications: list[str]
    clinical_notes: str
    documents: list[str]
    insurance: Insurance


class AnswerKey(BaseModel):
    record_id: str
    icd_codes: list[str]
    expected_packaging: Literal["ready", "rejected", "needs_review"]


class DischargeSummary(BaseModel):
    record_id: str
    primary_diagnosis: str
    secondary_diagnoses: list[str]
    procedures: list[str]
    medications: list[str]
    admission_course: str
    source_fields: dict[str, str]


class CodedDiagnosis(BaseModel):
    icd_code: str
    description: str
    confidence: float
    needs_review: bool


class ClaimPackage(BaseModel):
    record_id: str
    status: Literal["ready", "rejected", "needs_review"]
    fhir_claim: dict | None = None
    rejection_reasons: list[str] = Field(default_factory=list)


class SubmissionResult(BaseModel):
    record_id: str
    submission_id: str
    status: str
    outcome: str | None = None
