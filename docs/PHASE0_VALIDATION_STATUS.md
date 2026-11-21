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

- [ ] Check latest CI status against current head SHA `b5acda0` (runs pending).
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

Static review found a schema/model mismatch: the SQLAlchemy model accepted `cloud_resource`, but migration 0006's check constraint did not. It also found that the API trimmed references while the database unique index only lowercased them. Migration 0020 corrects both issues, adds a DB-level nonblank reference constraint, and includes a safe downgrade guard for existing `cloud_resource` records. A schema regression test covers the normalized index and nonblank constraint. Earlier CI run exposed an incorrect test assertion; that assertion has been corrected, and the newest CI runs succeeded on `60cd208`; PostgreSQL runtime validation remains pending.


## Current checkpoint — 2026-11-21

- Branch head: `60cd20847408031f739d5f3fe1ec79fb7c462ef3`.
- GitHub Actions Backend checks on the head: **success** (two runs observed).
- Static migration checks include the corrected named PL/pgSQL delimiter in migration 0020.
- Endpoint authorization structural coverage test added; it is not a substitute for role/object-level route tests.
- RBAC normalization and deny-by-default tests added.
- **Phase 0 remains open.** Runtime PostgreSQL migrations, fresh-stack Docker validation, legacy baseline compatibility, token rotation/revocation, and deeper authorization tests are outstanding.

### Practical completion estimate

Repository/static hardening is substantially progressed, but the remaining gates are high-value runtime and security validation. A percentage would be misleading; use the checklist below as the release gate rather than commit count.


### Additional refresh-token hardening

- Refresh policy now rejects JWTs missing the `iat` (issued-at) claim, even if signature and type are otherwise valid.
- Regression test added.
- This is defense-in-depth only; server-side refresh-token persistence, rotation and revocation remain required before production.


### Frontend session storage review

- Auth store persists access and refresh tokens in localStorage; Axios refresh interceptor replaces them on successful refresh.
- Local logout removes tokens but cannot revoke stateless refresh JWTs server-side.
- XSS impact and lack of server revocation are production release risks; cookie/session architecture and token rotation/reuse detection remain required.


### Refresh-session backend implementation checkpoint

- Added revision `0021_refresh_token_sessions` and SQLAlchemy model.
- Refresh flow now validates persisted session, row-locks it, performs one-time rotation and revokes active sessions on token reuse.
- Added `/auth/logout` revocation endpoint.
- Refresh-session records store a SHA-256 hash of `jti`, never the raw JWT.
- Initial refresh-session records are persisted after MFA login and mandatory password-change completion.
- **Pending validation:** current-head CI, PostgreSQL migration/runtime tests, concurrent refresh tests, frontend logout integration, and revoke-all/session management.


### Frontend logout integration

- Frontend auth store now calls `/auth/logout` with its refresh token before clearing local credentials.
- Local logout remains guaranteed if server revocation fails (error logged, local credentials cleared).
- API response interceptor excludes `/auth/logout` from automatic refresh handling to prevent logout requests triggering refresh recursion.
- **Deployment note:** refresh tokens issued before the persisted-session migration will not have session rows and will be rejected by the new refresh endpoint. Plan a forced re-authentication on rollout; do not attempt insecure fallback to stateless refresh.
- Latest code HEAD: `af1d52a093b0a28c5ca741252d4287b23483a848`; CI for this exact HEAD is pending.


### Current checkpoint — 2026-11-21 (refresh-session hardening)

- HEAD: `b5acda0f2476220a6ffce32457873c85990063db`.
- CI success observed on `f732ebc` (Backend checks); runs for later commits `dd980f8`, `d601d6f`, `44739ee`, `4f7c6a0`, and current HEAD are pending/in progress.
- Password change now revokes all existing active refresh sessions before issuing the new session.
- Refresh-policy denial now revokes active sessions before returning the denial.
- Frontend refresh-queue bug fixed: undefined `reject` reference removed from the queued request promise.
- Current implementation still requires runtime PostgreSQL integration tests, frontend build, and review of cross-tab refresh behavior.


### Current checkpoint — 2026-11-21 (frontend logout and queue review)

- HEAD: `be0569497789d46686d8078e4da344aa2b1113eb`.
- Backend checks succeeded on `01bafc8`.
- Runs for `7d4a308`, `c71af7c`, and current HEAD `be05694` are queued/in progress; do not treat these as validated yet.
- Frontend Axios refresh queue undefined `reject` reference fixed.
- Auth store logout now clears localStorage before Pinia `$reset()` to prevent stale credentials being reloaded into memory.
- Password change revokes existing active refresh sessions; refresh policy denial revokes active sessions.
- Frontend build and PostgreSQL runtime integration remain unverified.


### Latest logout credential cleanup

- Explicit logout and forced logout now clear Axios default `Authorization` header as well as localStorage credentials.
- Current HEAD: `c4df80cdcd3d2e041f85340f3e59b66749e3e25e`.
- CI status for this exact HEAD: pending; prior Backend checks succeeded on `01bafc8`.


### Current checkpoint — 2026-11-21 (refresh-session unit coverage)

- Current HEAD: `54348ad3f06640e594b2cf840524ff47d289b1c4`.
- Backend checks succeeded through `e6da608`; workflow for `6f469ea` is still in progress, and commits after it are pending.
- Added `backend/tests/test_refresh_token_sessions.py`: verifies SHA-256 JTI hash stability, invalid JTI rejection, session persistence of user/hash/expiry, absence of raw JWT in session representation, and expected refresh-token decode type.
- No local test runner is available through the GitHub connector; CI is the source of test execution evidence.
- PostgreSQL migration/runtime and concurrency tests remain outstanding.


### Logout endpoint unit coverage

- Added tests for invalid-token logout idempotency (no DB operation) and valid-token revocation path (DB update + commit).
- Current HEAD: `1796197a8bb409878838c6a29e550779692cff79`.
- CI status for `d60c9af` is in progress; runs for the current logout tests are queued.


### Current checkpoint — expiry claim validation

- Current HEAD: `90a702429ea9684a5f03309114baae935e909d85`.
- CI succeeded on `0d09755` after correcting the missing-exp test to expect the HTTP 401 validation response.
- Runs for current HEAD are in progress.
- Refresh-session persistence now rejects missing/non-numeric/boolean `exp` claims; regression tests cover these values.


### Latest auth concurrency review

- Refresh and password-change paths now lock the user row before session changes; static regression test added.
- Cross-tab frontend refresh coordination remains an identified residual: tabs may race a single-use refresh token and trigger replay revocation. Documented for resolution before Phase 0 auth closure.
- Current HEAD: `e48998ca25c9c0d317366e21beb55a479af8ff1`.
- CI for commits `16627da`, `d040494`, and latest documentation commit is pending/in progress; most recent completed run on `c970fab` succeeded.


### User-row locking correction

- CI exposed that the earlier lock patch had applied to refresh but not forced password-change; static assertion failed on `16627da` and `d040494`.
- Corrected password-change query to use `SELECT ... FOR UPDATE` in `9a45c31`.
- CI for `23d2136` was running at the checkpoint; latest code commit `9a45c31` is pending validation.


### Development model-registration checkpoint

- CI succeeded on `c43b1e3`.
- Found and corrected missing import of `RefreshTokenSession` in development startup model-registration imports. Without this, `Base.metadata.create_all()` could omit the refresh-session table in development.
- Added static regression test. Current HEAD `f034d9f`; CI pending.


### Review continuation — 2026-11-21

- Current observed branch head before this documentation update: `c898eea3b96ab5ca3dcaaf23d2600c32ad4c0163`.
- Backend checks for that exact head: **success** (push and PR workflow runs observed).
- Reviewed refresh-session migration `0021`, ORM registration, refresh/logout flow, and refresh-session unit/static tests.
- Corrected the database validation runbook to expect `0021_refresh_token_sessions` as the current head (previously stale at `0019`).
- Added `docs/PHASE0_SECURITY_REVIEW_FINDINGS.md` with source-review findings for token concurrency, PostgreSQL, document/RAG authorization, audit integrity, and API permissions.
- Documents upload is bounded to 10 MiB, file signature and extension are checked, extraction is bounded, and RAG chunk count is capped. However parser sandboxing/antivirus, retrieval-time document authorization, object-level API authorization, durable/tamper-resistant audit, and DB-backed concurrency tests remain open.
- **Phase 0 remains open**. No PostgreSQL runtime migration, Docker fresh-stack validation, or integration concurrency test is claimed by this checkpoint.


### Continued source review — 2026-11-21

- Reviewed RBAC matrix and asset-risk API tests. Explicit cross-module checks exist for risk/asset relationships, but endpoint-coverage AST remains structural and does not prove object-level authorization.
- Reviewed advanced AI context endpoint: it checks global documents-read permission, retrieves PSSI/control-reference documents, and treats retrieved content as untrusted prompt data. Document-level classification/ACL is absent from the Document model and must be designed before sensitive-document RAG is production-ready.
- Reviewed document upload/index/download/preview/delete paths. Upload is bounded and signature checked, but parser sandboxing/antivirus and retrieval-time classification authorization remain open. Indexing is synchronous.
- Reviewed compose configuration: development mounts and floating PostgreSQL image tag are not production-ready. No runtime Docker or PostgreSQL validation was performed.
- Updated `docs/PHASE0_SECURITY_REVIEW_FINDINGS.md` with the findings.
- CI for commit `53ebf90` was observed in progress at the time of checkpoint; do not infer success until completed.


### Refresh-token transaction review — 2026-11-21

- Source inspection confirms replay revocation is committed before the HTTP 401 is raised, avoiding rollback of the revocation on request exception.
- User row lock is acquired before refresh-session row lock, providing a consistent lock order in the refresh endpoint.
- Added static regression checks for commit-before-rejection on replay and lock ordering in `backend/tests/test_migrations_integrity.py` (commit `95f96e5`).
- CI for `9f7814a` (push and PR) completed successfully. CI for `95f96e5` has not yet been observed.
- These source/static checks do **not** prove PostgreSQL concurrency behavior. Real DB-backed concurrent requests remain an exit gate.


### PostgreSQL integration gate added — 2026-11-21

- Added opt-in PostgreSQL concurrency integration test `backend/tests/test_refresh_rotation_postgres.py`. It creates a disposable user/session, runs two concurrent rotations using PostgreSQL row locks, asserts exactly one succeeds, checks the old session is revoked and one active replacement remains, and cleans up the test user.
- Added CI job `postgres-integration` using PostgreSQL 16 with pgvector. It runs Alembic migrations from scratch and executes the concurrency test against the service database.
- Local execution remains skipped unless `PGCC_INTEGRATION_DATABASE_URL` is configured. Runtime proof is pending CI result.
- Commits: `9ffdb75` (integration test), `521bcf0` (CI gate).


### Migration CI failure and correction — 2026-11-21

- PostgreSQL integration job failed at initial revision `0001_initial`: SQLAlchemy could not resolve the FK from `action_items.iso_assessment_id` because `iso_control_assessment` model was not imported into the baseline metadata.
- Added the assessment model to revision 0001 imports and made revision 0002 table/index creation conditional to avoid duplicate creation on clean DBs while remaining compatible with already-applied deployments.
- Revision 0020 downgrade index expression mismatch was corrected: upgrade uses `lower(btrim(reference))`; downgrade now restores `lower(reference)`.
- Regression test added for the 0020 upgrade/downgrade index expression.
- CI reruns for these fixes are pending. The PostgreSQL job has not yet passed.


### Migration CI second failure — action ISO links

- PostgreSQL CI exposed another migration issue: revision `0004_action_iso_links` adds `iso_control_id` and `iso_assessment_id` even though the baseline's metadata `create_all` already created those columns.
- Updated revision 0004 to inspect existing columns, foreign keys, and indexes and add only missing objects. Downgrade now checks for objects before dropping them.
- The migration static test was also corrected to parse the actual typed Alembic function signatures (`def upgrade() -> None` / `def downgrade() -> None`).
- Commits: `5d624a7` migration fix; `d8d2775` test correction.
- CI must rerun; no green PostgreSQL runtime result yet.


### Migration 0004 follow-up — baseline FK detection and test parser

- Migration 0004 now detects existing action ISO foreign keys by constrained columns and referenced table, not only by the constraint name. This avoids creating duplicate FKs when SQLAlchemy baseline creates equivalent constraints with PostgreSQL-generated names.
- Corrected static test parsing to match Alembic's typed function declarations (`def upgrade() -> None`).
- Runtime CI for the latest migration corrections is pending.


### Migration 0006 asset inventory baseline overlap

- Latest PostgreSQL CI failure showed `assets` already exists when revision `0006_asset_inventory` runs, due to baseline `0001_initial` metadata creation.
- Updated revision 0006 to conditionally create `assets` and `asset_relationships`, and to create missing indexes only. Downgrade now checks table/index existence before dropping.
- Added static regression test for baseline overlap guards.
- Commit `cbc4156`: migration correction; `99d4f41`: test.
- Runtime PostgreSQL validation pending.
