# Risk Management Model — Target Design

## Purpose
Evolve the prototype risk register into an auditable risk-management workflow. This document describes the target model; it is not a claim that every field or workflow is implemented.

## Risk record
- Stable reference (RISK-YYYY-NNNN), title, scenario, cause, threat, vulnerability.
- Organization: direction, service, process, site, risk owner, treatment owner.
- Asset/application links and dependencies.
- Impact dimensions: confidentiality, integrity, availability, operational, financial, legal/regulatory, reputation; scale and rationale.
- Likelihood scale and rationale.
- Inherent risk: score and level calculated server-side from approved methodology.
- Existing controls: linked control IDs, implementation/evidence state.
- Treatment decision: avoid, reduce, transfer, accept; decision rationale and approver.
- Treatment plan: actions, owner, due dates, budget, milestones, evidence.
- Residual risk: re-assessment after controls/actions, score, rationale.
- Acceptance: explicit decision, accepting authority, date, justification, compensating controls, expiry/review date.
- Lifecycle: status, created/updated, assessment date, next review, history.

## Recommended status workflow
Identified -> Assessed -> Treatment proposed -> Treatment approved -> In progress -> Residual assessment -> (Accepted / Further treatment) -> Monitoring -> Closed.

Acceptance must be a separate decision record and not merely a status string. An accepted risk requires a documented residual assessment, justification, approving authority, and review/expiry date. Role and authority thresholds must be configurable and enforced server-side.

## Scoring
Keep impact and likelihood scales configurable and versioned. Scores are computed server-side. Do not imply that a numeric score is universally comparable across organizations. Preserve the score methodology version and supporting rationale with each assessment.

## Data integrity
- Risk references unique and immutable.
- Risk owner and treatment owner reference active users or organization records.
- Historical assessments and approvals are append-only records; changes create a new assessment or decision, not silent overwrites.
- Risk/action/control/document relationships use foreign keys and validated permissions.
- Status transitions are enforced by domain service, not only frontend.
- Audit events capture create/update/transition/acceptance/closure.

## Suggested entities
- Risk
- RiskAssessment (inherent/residual; methodology version; dimensions; rationale; assessed_by; assessed_at)
- RiskTreatmentDecision (strategy; rationale; decision authority; decision date)
- RiskAcceptance (residual assessment reference; accepting authority; rationale; compensating controls; expiry/review date)
- RiskAction (linked action plan item)
- RiskControlLink (control, applicability, effectiveness/evidence)

## Implementation sequence
1. Review existing Risk and ActionItem models/API/UI and tests.
2. Add schema through reviewed Alembic migration; avoid destructive changes.
3. Backfill legacy fields into new records with explicit migration provenance.
4. Add domain validation and transition service.
5. Add API endpoints and RBAC tests.
6. Update frontend forms and dashboards.
7. Add PostgreSQL integration tests for acceptance, transitions, ownership and rollback.

## Acceptance criteria
- Scores are calculated on backend using documented/versioned methodology.
- Risk acceptance is explicit, traceable, authorized, and reviewable.
- Residual risk is distinguishable from inherent risk.
- No data is lost during migration.
- API enforces transition and ownership rules.
- Audit trail records important decisions.


## Current prototype status and migration notes

The current code implements a basic 1–5 impact and likelihood matrix (score = impact × likelihood), server-side score calculation, a small status set, active-user owner validation, and refusal to hard-delete risks that have linked actions. These are foundational safeguards only.

Not yet implemented in the current risk model: separate inherent and residual assessments, rationale/evidence for ratings, methodology version, acceptance authority and expiry, assessment history, formal treatment options, risk appetite thresholds, and archival workflow. Risk score must not be interpreted as compliance or formal acceptance.

Migration strategy: establish and test an Alembic baseline first; then introduce assessment/history/acceptance entities with an explicit legacy methodology label for existing records. Avoid destructive backfills or silently changing existing scores.


## Data integrity note

The API currently blocks hard deletion of risks with linked actions. The ORM/database cascade behavior is not yet changed because the repository does not have a validated migration baseline. A future Alembic migration should change the risk-action foreign key to RESTRICT/NO ACTION and remove ORM delete-orphan cascade, after testing existing data and upgrade/rollback behavior. Do not make this schema change only in ORM metadata against an existing database.
