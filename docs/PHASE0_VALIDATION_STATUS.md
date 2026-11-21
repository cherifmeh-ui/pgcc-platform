# Phase 0 Validation Status

Updated: 2026-11-21

## Scope

This document records repository-level checks and static-review findings for the
`chore/phase0-stabilization` branch. It is not a production readiness claim,
penetration-test report, or runtime integration validation.

## Pull request

- PR: #1
- Base: `main`
- Head: `chore/phase0-stabilization`
- Current head SHA: `3ab97fa09f754a9bccc460a7511644d97b60f4de`
- State: open, draft

## Verified from repository metadata

- Backend CI workflow exists and runs dependency installation, Python compile checks, and pytest.
- Frontend CI workflow installs from lockfile and runs the Vite build.
- The PR description records that earlier workflow runs succeeded, but the current head must be checked before treating the branch as validated.
- Alembic configuration, migration environment, and a 20-revision linear history are present.
- Static migration graph checks and migration integrity tests were added.
- Migration `0020_asset_reference_and_type_constraints` aligns normalized asset references and the `cloud_resource` asset type between the DB and SQLAlchemy model.
- PostgreSQL-backed migration execution remains unverified.

## Required before merge

- [ ] Check latest CI status against the current head SHA (workflows pending after latest changes).
- [ ] Run a clean Docker build.
- [ ] Start the stack against a fresh PostgreSQL database.
- [ ] Validate Alembic baseline strategy against both fresh and existing databases.
- [ ] Add API integration tests for authentication, risk lifecycle, action lifecycle, document upload, and permissions.
- [ ] Review token/session invalidation and MFA flows.
- [ ] Review document access authorization and malware-scanning strategy.
- [ ] Validate ISO dataset references against an authoritative licensed source.
- [ ] Review the full PR diff for unintended changes.
- [ ] Obtain human review before merge.

## Static-review risks still open

1. Authentication tokens and sessions require a complete revocation/rotation design.
2. Compliance status is not yet evidence-backed control assessment.
3. Action ownership remains a free-text field rather than a user relationship.
4. Risk history and formal residual-risk acceptance are not yet modeled.
5. Document extraction is bounded, but parsing is not sandboxed and no antivirus scan is integrated.
6. RAG authorization must be enforced at retrieval time, including document classification and user permissions.
7. Audit logs need tamper-resistance, retention, and operational alerting.
8. Production deployment still requires a hardened reverse proxy, secret management, backup/restore tests, and observability.

## Validation principle

A green compile or unit-test workflow is not equivalent to a clean runtime deployment.
Only checks actually executed against the current commit should be marked complete.

## Additional asset inventory validation

Static review found a schema/model mismatch: the SQLAlchemy model accepted `cloud_resource`, but migration 0006's check constraint did not. It also found that the API trimmed references while the database unique index only lowercased them. Migration 0020 corrects both issues, adds a DB-level nonblank reference constraint, and includes a safe downgrade guard for existing `cloud_resource` records. A schema regression test covers the normalized index and nonblank constraint. Earlier CI run exposed an incorrect test assertion; that assertion has been corrected, and the newest CI runs are pending.
