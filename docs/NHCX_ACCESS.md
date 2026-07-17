# NHCX Access: Reality Check

## NHCX Sandbox Status

**NHCX (National Health Claims Exchange)** has been live since **June 2024**. It is FHIR R4–based and operated by the NHA (National Health Authority) under ABDM (Ayushman Bharat Digital Mission).

The sandbox environment is available at `hcxsbx.abdm.gov.in`.

## Individual Developer Access Limitation

**Access to the NHCX sandbox requires organization-level onboarding with NHA.** Valid organizations include:
- Hospitals / healthcare providers
- Payers / insurance entities
- TPAs (Third-Party Administrators)

**Individual developers cannot obtain direct end-to-end submission access** to the live sandbox. Real claim submission to NHCX is deferred to product stage (see PROJECT_SPEC §14).

## ClaimGuard's Approach

To enable Phase 0 development and testing without organization-level NHCX credentials:

1. **Deterministic FHIR/NHCX Simulator** (Task 13): ClaimGuard ships a simulator that reproduces the NHCX API contract and FHIR validation rules.
2. **Simulated Submission Label**: Every claim submission in development is marked as **simulated**. This label is preserved in audit logs and claim records.
3. **Real Submission Deferral**: Conversion to real NHCX submission is product-stage work, not included in Phase 0. It requires:
   - Organization registration with NHA
   - Live credentials provisioning
   - Staging → production pipeline validation
   - Human sign-off on claim integrity

## Summary

During Phase 0 and development, ClaimGuard operates against a faithful simulator. No real claims are submitted. This is intentional and documented. Production deployment will add real NHCX submission when organization credentials are available.
