# Evidence and Control Assessment Model

## Governance rule
A control may be declared implemented only through an assessment record. Textual matches in risks/actions and a manually set boolean are not verification. The current API remains a transitional, declaration-only matrix and must not be used to assert certification readiness.

## Proposed entities

### ControlAssessment
- id (UUID)
- control_id (FK to ISO control catalog)
- applicability: applicable / not_applicable / pending
- applicability_rationale (required for not_applicable)
- implementation_status: not_assessed / planned / partial / implemented / verified
- maturity_level (nullable; assessment methodology/version required)
- assessment_scope and rationale
- assessor_id (FK User), assessed_at
- next_review_at
- approved_by_id, approved_at
- methodology_version
- created_at; assessment history append-only

### EvidenceRecord
- id (UUID)
- assessment_id (FK)
- document_id (FK, nullable only for externally referenced evidence)
- evidence_type: policy / procedure / configuration / log / screenshot / test_result / interview / other
- title, description
- source_location or external_reference (validated and access controlled)
- collected_by_id, collected_at
- valid_until / review date
- integrity_hash (SHA-256 for uploaded file/version)
- verification_status: pending / reviewed / rejected
- reviewer_id, reviewed_at, review_notes
- confidentiality/classification

### ControlFinding
- assessment_id
- severity, description, recommendation
- linked risk/action references
- status and validation history

## Evidence acceptance rules
- Evidence is linked to a specific control and assessment period.
- A document alone is not evidence of operational effectiveness; the assessor records what it demonstrates and any testing performed.
- Expired or rejected evidence does not count as valid support.
- Verified status requires evidence review, reviewer, date and conclusion.
- Controls can be implemented but not verified; display these states separately.
- Not-applicable requires documented justification and authorized approval.
- A new assessment never overwrites prior assessments.

## Dashboard methodology
- Declared: an authorized user claims implementation.
- Implemented: assessment says implemented, with rationale.
- Verified: assessor reviewed sufficient evidence and recorded a conclusion.
- Not applicable: approved and justified; excluded from denominator according to the published scoring method.
- Not assessed: remains in denominator or shown separately; never silently treated as implemented.
- Score denominator, excluded controls, evidence freshness and methodology version must be visible.

## Implementation plan
1. Confirm ISO catalog IDs/version and add Alembic migration for assessment/evidence/finding tables.
2. Add RBAC permissions for assess, submit, review, approve and read evidence.
3. Implement endpoints with transaction boundaries and immutable assessment history.
4. Validate evidence uploads: byte limit, MIME/signature, file parser limits, malware scanning integration, SHA-256, access checks and safe download headers.
5. Build control assessment UI and evidence workflow.
6. Add tests for authorization, invalid evidence, expired evidence, not-applicable approvals, assessment history, and score calculations.
7. Add audit events for all assessment/evidence changes.

## Immediate scope
Do not add schema in this phase until catalog version, migration baseline and existing relationships have been verified. The current matrix should be labeled as preliminary/declarative.
