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
    # §9-4: "deceased" routes to the expedited/compassionate path and suppresses every
    # patient-addressed message. Defaults so existing records and fixtures stay valid.
    disposition: Literal["discharged", "deceased"] = "discharged"


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
    # §9-10: advisory flags (duplicate admission, identity mismatch). Never block on
    # these — they route a claim to a human, they don't decide it.
    flags: list[str] = Field(default_factory=list)


class SubmissionResult(BaseModel):
    record_id: str
    submission_id: str
    status: str
    outcome: str | None = None


# --- Phase 2: Negotiation / Appeal ---


class InsurerDecision(BaseModel):
    claim_id: str
    insurer_id: str
    plan_id: str
    outcome: Literal["partial", "rejected"]
    claimed_amount: int
    approved_amount: int
    reason_text: str
    cited_clause_id: str | None = None


class DenialScenario(BaseModel):
    scenario_id: str
    insurer_id: str
    plan_id: str
    diagnosis: str
    procedures: list[str]
    decision: InsurerDecision


class Citation(BaseModel):
    clause_id: str
    quoted_text: str
    relevance: str


class AppealResult(BaseModel):
    scenario_id: str
    status: Literal["appeal", "no_valid_appeal"]
    appeal_text: str
    citations: list[Citation] = Field(default_factory=list)
    reasoning: str = ""


class DenialAnswerKey(BaseModel):
    scenario_id: str
    appeal_viable: bool
    expected_clause_ids: list[str]
    category: str


# --- Phase 3: Compliance Radar ---


class RadarStage(BaseModel):
    stage: str
    at_minutes: int  # offset from the order handoff (order = 0)


class Journey(BaseModel):
    record_id: str
    claim_type: str
    stages: list[RadarStage]


class RadarReport(BaseModel):
    record_id: str
    claim_type: str
    pre_submission_delay_min: int
    stage_gaps: dict[str, int]
    slowest_stage: str
    breach_status: Literal["ok", "pre_breach", "breach"]
    alert: bool
    synthetic: bool = True


# --- Phase 4: Patient communication ---


class PatientMessage(BaseModel):
    record_id: str
    event: str
    language: str
    text: str
    at_minutes: int  # offset from the order handoff, same clock as Journey
    channel: str = "whatsapp_sandbox"
    synthetic: bool = True


class PatientStatus(BaseModel):
    record_id: str
    language: str
    stage: str
    happening: str  # what's happening, in the patient's words
    next_step: str  # what's next
    eta_min: int | None = None
    sla_min: int
    elapsed_min: int
    messages: list[PatientMessage] = Field(default_factory=list)
    synthetic: bool = True
