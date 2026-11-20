# PGCC — ISO 27002 Control Assessment Model

## Purpose
Separate control reference metadata from an organization's assessment of implementation. A control reference is not proof of implementation or conformity.

## Reference metadata
- Standard: ISO/IEC 27002
- Edition: 2022
- Control reference: A.5.1 through A.8.34
- Official title (French/English, as sourced and licensed)
- Theme: Organizational / People / Physical / Technological
- Control type and attributes (when verified)
- Reference source and verification date

## Assessment record (per organization and control)
- Assessment ID
- Control reference ID
- Applicability: Applicable / Not applicable / To determine
- Applicability rationale (mandatory when Not applicable)
- Implementation status: Not assessed / Planned / Partially implemented / Implemented / Verified / Nonconformity
- Maturity: 0–5, optional and explicitly defined
- Assessment scope, entity, site, process or system
- Control owner
- Assessor
- Assessment date
- Next review date
- Findings and gaps
- Risks linked
- Actions linked
- Evidence linked
- Validation reviewer and validation date
- Assessment history

## Evidence
Evidence is a first-class record:
- Document or evidence reference
- Evidence type
- Owner/source
- Collection date
- Validity period
- Confidentiality/classification
- Hash (for uploaded files)
- Related control(s), finding(s), risk(s) and action(s)
- Reviewer and review result
- Comments

## Status semantics
- Not assessed: no assessment performed.
- Planned: work is scheduled, no implementation claim.
- Partially implemented: some requirements/activities exist; gaps remain.
- Implemented: organization declares implementation.
- Verified: implementation was checked against defined evidence and scope.
- Nonconformity: assessment identifies an unmet requirement or control objective.

Do not calculate a certification percentage from a simple status count. If a dashboard displays coverage, it must state the calculation, scope, applicability exclusions and whether evidence was independently validated.

## Workflow
1. Assign assessor and control owner.
2. Determine applicability and document rationale.
3. Assess implementation and identify gaps.
4. Link risks and actions.
5. Attach evidence.
6. Submit for review.
7. Reviewer validates or returns the assessment.
8. Schedule next review.
9. Preserve version history.

## Permissions
- Assessors may draft/update assessments in their scope.
- Control owners may submit evidence and comments.
- RSSI or delegated reviewer validates.
- Admins manage reference metadata but cannot silently overwrite assessment history.
- Every status transition and evidence operation is audit logged.

## Migration
Existing manual coverage flags must migrate as *declared/unverified* assessments. Existing links inferred from text matching must not be migrated as validated coverage. Preserve legacy IDs and data, and provide a reconciliation report.
