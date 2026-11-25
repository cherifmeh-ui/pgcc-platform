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


### CI failure: syntax error in migration 0006

- The previous automated guard insertion left two `op.create_index` statements under an `if` without the required indentation. This caused Alembic's migration graph loading to fail before database execution.
- Corrected indentation in revision `0006_asset_inventory`.
- Added a static test parsing every migration with Python AST, preventing syntax errors from reaching the Alembic runtime.
- Commits: `1521f96` (syntax correction), `44ee3a2` (AST test).
- CI rerun pending.


### Migration CI findings — revisions 0007–0011

- PostgreSQL CI detected duplicate table `asset_risk_links` in revision 0007. The migration now guards table creation and index creation, and downgrade checks for table/index presence.
- Review identified baseline overlap in revisions 0009–0011: asset filter indexes and the asset-risk FK/index can already exist from model metadata. Revisions 0009 and 0011 now guard indexes; 0010 inspects the existing FK delete rule and only alters it when required.
- Static regression checks added for revisions 0007 and 0009–0011.
- Runtime PostgreSQL CI remains required; these edits are not yet declared validated.


### Migration review 0009–0013

- Revisions 0009–0011 were reviewed and guarded against indexes/FK objects already created by the SQLAlchemy baseline.
- Revisions 0012 (supplier register/contact) and 0013 (supplier contracts) were updated to conditionally create tables and indexes and to guard downgrade table drops.
- Added static migration regression tests for revisions 0009–0013.
- Runtime CI is pending. The hybrid baseline still risks schema drift; guards are a stabilization measure, not a replacement for a frozen baseline.


### Migration review 0014–0019

- Supplier assessments, supplier-asset links, access requests, access reviews, supplier-risk links and monthly risk snapshots are now guarded against baseline-created tables and indexes.
- Downgrades check table existence before dropping the revision's table.
- Added static regression coverage across revisions 0014–0019.
- Runtime PostgreSQL CI is pending.


### Migration review 0020–0021

- Revision 0020 was rewritten after inspection to guard existing normalized-reference indexes and check constraints. It still rejects duplicate normalized references before enforcing uniqueness and protects downgrade from cloud_resource values.
- Revision 0021 refresh-token session table/index creation and downgrade now check baseline overlap.
- Added static regression checks for revisions 0020–0021.
- Runtime upgrade/downgrade PostgreSQL CI remains the acceptance gate; the baseline overlap guards do not prove exact schema equivalence.


### PostgreSQL migration failure — revision 0008 (2026-11-23)

- CI at the branch head failed in `postgres-integration` during `alembic upgrade head`: revision 0008 attempted to drop `uq_assets_application_id`, but the baseline-created `assets` table did not contain that named constraint.
- Revision 0008 now introspects the existing unique constraints and drops only a constraint whose constrained columns are exactly `application_id`; it safely returns if the table is absent.
- Downgrade now checks whether the uniqueness constraint already exists and rejects downgrade if duplicate non-null application references would make restoration unsafe.
- Added static regression coverage for the guard and duplicate-data downgrade check.
- Backend unit tests and frontend build were green in the observed run; PostgreSQL migration job failed before the refresh-rotation integration test could run. The fix is committed, but CI validation on the new head is pending.


### Alembic revision length compatibility — follow-up (2026-11-23)

- PostgreSQL's Alembic version table stores revision identifiers in a 32-character field. The earlier revision names exceeded this limit, so migration execution failed even after the 0008 constraint guard.
- Shortened revision IDs and aligned dependency references: 0008 `0008_asset_app_cardinality`, 0009 `0009_asset_filter_indexes`, 0010 `0010_asset_risk_restrict`, 0011 `0011_asset_ref_ci`, and 0020 `0020_asset_ref_type`.
- Updated downstream `down_revision` links and static test references.
- Added a regression test asserting every Alembic revision identifier is at most 32 characters.
- Corrected the 0008 migration static test to match the actual column introspection expression.
- These commits require a fresh PostgreSQL CI run; no runtime migration validation is claimed yet.


### Refresh-session PostgreSQL concurrency test — fixture correction (2026-11-23)

- The migration job successfully applied Alembic head on PostgreSQL 16. The integration test then failed while inserting a refresh-token session because the referenced user row was not yet present.
- The test fixture previously added the User and RefreshTokenSession in one ORM flush without an explicit relationship; SQLAlchemy did not guarantee insert ordering for these independent objects.
- The fixture now commits the user first, then creates and commits the initial refresh-token session. The concurrent rotation assertions remain unchanged.
- The correction is committed; CI must rerun before claiming the PostgreSQL integration test is green.


### Asset lifecycle consistency review — 2026-11-23

- Source review found active-inventory queries relied only on `retired_at IS NULL`, which could include records whose `lifecycle_status` was `Retiré` or `Décommissionné` if legacy/inconsistent data existed.
- Added `_active_asset_filter()` and applied it to graph, paginated inventory, list, export, and completeness statistics when retired assets are excluded.
- Retirement endpoint now normalizes inconsistent records: it fills `retired_at` when missing and preserves `Décommissionné` rather than downgrading it to `Retiré`.
- Regression coverage extended for lifecycle predicate behavior.
- Commits: `b6628fa` (asset endpoint consistency), `4a99ad2` (test).
- CI status for latest commit not yet available through the workflow-run query; no validation claim is made.
- Phase 0 remains open; DB/runtime validation and security gates remain required.


### Supplier access lifecycle review — 2026-11-23

- Reviewed supplier access request, decision, review, revocation, and expiration endpoints.
- Confirmed request creation checks supplier approval, active supplier-asset link, asset lifecycle eligibility, and open-request duplication; decisions lock the request row and reject self-approval.
- Confirmed periodic reviews lock the request and reject reviewers who were the requester or initial approver; review outcomes validate privilege reduction and revoke access when requested.
- Remaining hardening items: verify duplicate-request protection under concurrent PostgreSQL transactions (application check alone may race); ensure expiration/revocation transitions are consistently audit logged and tested; validate that access checks use current status and dates rather than only persisted status.
- Latest observed workflow for commit `011c4f82`: Backend checks succeeded. This does not establish full CI or runtime validation for subsequent commits.
- Phase 0 remains open.

- Follow-up inspection of `SupplierAccessRequest` model confirmed a PostgreSQL partial unique index `uq_supplier_access_requests_open_link` on `supplier_asset_link_id` for statuses `Demandé`, `Approuvé`, and `Suspendu`. This mitigates the concurrent duplicate-request race at the database layer; runtime migration/index parity and concurrency tests remain to be verified. Corrected the earlier finding: the model already declares this guard.


### Asset mutation concurrency review — 2026-11-23

- Asset retirement now obtains a row lock before normalizing lifecycle markers, preventing concurrent retirement requests from racing on state changes.
- Asset-risk association creation now locks the asset row before checking retirement state and inserting the association, serializing link creation with retirement.
- The latest previously observed Backend checks workflow on commit `9acbbd0` completed successfully. The new commit `eb74f54` is awaiting its own workflow result.
- Full PostgreSQL concurrency tests for retirement/link operations remain required; source-level row locks alone are not runtime proof.


### Asset-risk integrity and deletion review — 2026-11-23

- `AssetRiskLink` enforces unique `(asset_id, risk_id)` and RESTRICT foreign keys to assets and risks.
- Risk deletion endpoint refuses deletion while corrective actions or asset-risk links exist, preserving traceability; explicit unlinking is required before deletion.
- Asset retirement is logical (not physical), so risk associations remain traceable after retirement. New links reject retired assets; unlink remains available to authorized users.
- Asset-risk linking now locks the asset row before checking lifecycle and inserting, serializing against retirement. PostgreSQL integration testing of concurrent link/retire is still outstanding.
- Backend checks run #1574 passed on commit `9acbbd0`; commit `eb74f54` has no workflow result returned yet, and documentation commit `0cc20b0` also awaits status.


### Asset update lifecycle concurrency — 2026-11-23

- Asset update now locks the asset row (`FOR UPDATE`) before applying lifecycle status and `retired_at` normalization, preventing concurrent update/retirement operations from overwriting lifecycle state based on stale reads.
- Source-level change is committed as `05261a63`; workflow result is not yet available.
- This adds serialization to update/retire/link-risk paths. PostgreSQL concurrency tests are still required before claiming runtime correctness.


### CSV inventory import integrity review — 2026-11-23

- CSV preview validates duplicate references, hostnames, and serial numbers within the file and against current inventory.
- Confirm endpoint re-runs preview, revalidates application references, and commits the complete import atomically; failure rolls back and returns conflict.
- Asset reference case/whitespace uniqueness is enforced by model-level `uq_assets_reference_ci` index and nonblank check. Hostname and serial number are currently checked by preview only, with no database uniqueness constraint visible in the Asset model; concurrent imports or direct API writes may therefore bypass those duplicate checks.
- Before adding DB uniqueness constraints, inspect existing inventory for duplicate hostname/serial data and choose nullable/case-insensitive semantics; then add a migration and PostgreSQL tests. No migration was created without this evidence.
- The test directory path guessed for CSV import tests was not found by GitHub file fetch, so test discovery remains incomplete; no claim of tests run.


### CI follow-up — 2026-11-23

- Backend checks run #1582 for commit `05261a63` were observed in progress.
- Backend checks run #1584 for commit `160e5de2` were observed in progress.
- Workflow status for documentation-only commit `78c9aea6` was not returned.
- These are pending observations; do not mark them successful until final conclusions are available.


### CI and dependency-graph concurrency review — 2026-11-23

- Backend checks run #1582 (`05261a63`) completed SUCCESS.
- Backend checks run #1584 (`160e5de2`) completed SUCCESS.
- Backend checks run #1588 (`cfc75d59`) completed SUCCESS.
- Dependency relationship creation locks both endpoint asset rows in deterministic ID order, checks both endpoints are active, and rejects `depends_on` cycles after locking. This serializes concurrent relationship mutations on shared endpoints and reduces the cycle race.
- Asset update, retirement, and asset-risk association paths now also use row locks.
- Application endpoint file and dedicated asset-application tests could not be located at the attempted paths through repository file fetch; no changes were made to that module. Need identify correct paths before further review.
- Runtime PostgreSQL concurrency tests and fresh-stack validation remain outstanding; CI success does not replace them.


### Dependency graph cycle concurrency hardening — 2026-11-23

- Cycle detection now excludes retired/decommissioned assets and their dependency edges, so the active dependency graph is evaluated rather than historical retired nodes.
- Added a PostgreSQL transaction-scoped advisory lock for `depends_on` relationship creation. Endpoint row locks alone could not serialize disjoint concurrent edge additions that jointly form a cycle.
- Commit `fe53937e` contains this source-level hardening. CI and PostgreSQL concurrency tests remain pending.

- Backend checks run #1592 for commit `fe53937e` is currently IN PROGRESS. Its outcome must be verified before claiming this graph-cycle hardening passes CI.

- Backend checks run #1592 for `fe53937e` and #1596 for `d1ca302e` are both currently IN PROGRESS. The documentation update commit `fe94d6aa` has run #1596 also in progress. No CI conclusion is recorded yet for these graph-lock changes.


### Supplier access revocation/expiration concurrency — 2026-11-23

- CI: Backend checks #1592 (`fe53937e`), #1598 (`d1ca302e`), and #1600 (`59dc97c5`) completed SUCCESS.
- Supplier access revocation and expiration endpoints now lock the access-request row with `FOR UPDATE` before checking status and mutating it, reducing concurrent double-transition races.
- Commit `8cd7650c` is awaiting CI. Concurrency integration tests for approve/revoke/expire/review transitions remain outstanding.

- Backend checks #1602 for `8cd7650c` (supplier access revocation/expiration locking) are IN PROGRESS. Documentation commit `6d13cb3e` has no workflow result returned. No CI success is claimed for the supplier transition change yet.


### Supplier state concurrency — 2026-11-23

- Supplier asset-link creation, supplier status update, and supplier archiving now lock the supplier row with `FOR UPDATE` before eligibility checks and mutation. This serializes these operations against one another and reduces races that could create a new link while a supplier is being suspended/terminated/archived.
- Access-request revoke/expire endpoints also lock the request row before transition checks (`8cd7650c`).
- CI #1602 for `8cd7650c` was IN PROGRESS when last checked. New commit `ca0fb162` is awaiting workflow result.
- PostgreSQL integration tests covering concurrent supplier status/link/archive and access transitions remain necessary.


### RBAC cross-module review and access expiration — 2026-11-23

- `require_permission` is enforced server-side using `role_has_permission`; frontend permission data is informational only. The suppliers-to-risks link additionally checks `risks:update`, preventing suppliers permission alone from authorizing risk linkage.
- Access expiration now also locks the supplier access request row with `FOR UPDATE` before checking status and end date and mutating to `Expiré`. Commit `4d030a33` awaits CI.
- Access decision, review, and revocation already use request row locks. Supplier lifecycle changes now lock supplier rows.
- RBAC review found explicit module/action entries and deny-by-default behavior for unknown module/action. Existing dedicated RBAC test file could not be located by repository fetch; test coverage needs path discovery.
- Remaining concerns: expire vs revoke status transitions are serialized by row locks; supplier-risk link creation should be reviewed for duplicate races and transaction behavior; supplier asset-link termination should lock link row and be reviewed for termination/access-request races. No runtime concurrency claim.

- CI Backend checks #1608 for supplier state locking commit `ca0fb162` completed SUCCESS. CI #1612 for access expiration lock commit `4d030a33` is QUEUED. Documentation commit `3ef9c8da` has no workflow run returned.


### Supplier risk-link and RBAC review — 2026-11-23

- Supplier-risk links have a database unique constraint on `(supplier_id, risk_id)` and RESTRICT foreign keys, so concurrent duplicate link creation is rejected by PostgreSQL even if endpoint pre-checks race.
- The endpoint explicitly checks `suppliers:manage_risks` and `risks:update`, with backend deny-by-default RBAC.
- Document/RAG endpoint paths were not discoverable through the attempted GitHub search queries; review is deferred until exact file paths are identified.
- CI #1608 for supplier state row-lock hardening (`ca0fb162`) passed. CI #1612 for supplier access expiration locking (`4d030a33`) was IN PROGRESS at last observation. No result claimed for the latter.


## Current checkpoint — 2026-11-24

- Branch: `chore/phase0-stabilization`.
- HEAD before this correction: `70e2bbf6bb57c462f8d320ed824bf8edd98bdacb`.
- PR #1: open, draft, not merged; base `main`.
- GitHub Actions for that exact HEAD: Backend checks success; backend tests **268 passed, 1 skipped**; frontend Vite build success; PostgreSQL 16 integration job success (Alembic upgrade to head and refresh-token concurrency test: **1 passed**).
- Static review identified broad database exception mapping in asset create/update/CSV import; only `IntegrityError` should become HTTP 409. Correction and focused regression tests are committed on this branch; CI for the resulting HEAD is pending.
- Remaining: relationship create/delete and asset retirement/deletion behavior require broader PostgreSQL-backed API integration tests; full clean Docker application stack, document/RAG ACL and audit durability remain unverified. Phase 0 is **not closed**.


## Cartography relationship checkpoint — 2026-11-24

- Last fully green HEAD before this change: `e4ed3d20e7586ebad09913a239a16811934efe23`; backend 271 passed / 1 skipped, frontend build passed, PostgreSQL migrations and refresh-token integration passed.
- Relationship creation already uses a PostgreSQL advisory transaction lock for `depends_on` edges and locks endpoint assets in deterministic order. Existing tests covered the pure cycle helper, not the endpoint transaction path.
- Corrective change: relationship create/delete now explicitly roll back and re-raise unexpected database errors; create continues to map only `IntegrityError` to HTTP 409.
- New API regression tests cover unexpected commit errors, duplicate constraint mapping, cycle rejection and delete rollback. CI for the new HEAD is pending.
- Remaining: PostgreSQL concurrency test for opposing dependency edges, FK/RESTRICT behavior for relationship deletion and asset deletion, and end-to-end validation of supplier/application/risk link lifecycles. Phase 0 remains open.


## Supplier database error handling — 2026-11-24

- Review found seven supplier endpoint handlers converting all commit failures into HTTP 409, masking infrastructure errors as business conflicts.
- Correction committed on `chore/phase0-stabilization`: only `IntegrityError` maps to HTTP 409; other exceptions trigger rollback and are re-raised.
- Added a source-level AST regression test covering all seven handlers.
- Validation on supplier-correction HEAD `459a8fb668e845b71a3663d9add2a50713ebf28a`: backend **276 passed, 1 skipped**, frontend passed, PostgreSQL migrations and refresh-token integration passed (run `45457457094`).
- A further PostgreSQL integration test now submits opposing dependency edges concurrently through the actual relationship API. Its CI run on HEAD `205f82a19ab496fa3f70127fc4c6a6144468ab14` is pending. Phase 0 remains open.


## PostgreSQL dependency graph concurrency validation — 2026-11-24

- Added `backend/tests/test_asset_relationships_postgres.py`: concurrent opposing dependency edges are submitted through the API route using separate PostgreSQL sessions.
- Expected invariant: one edge succeeds, the opposite edge is rejected as a cycle, and only one edge is persisted.
- PostgreSQL CI now runs this test with the existing refresh-token concurrency test after applying Alembic migrations.
- Validation pending. Phase 0 remains open.


## Latest validated checkpoint — 2026-11-24

- HEAD: `306e966b72ff4c6b026fa130647a7c7282ca2ecb` on `chore/phase0-stabilization`.
- PR #1 remains open, Draft and unmerged.
- CI run `45457897057`: Backend **276 passed, 2 skipped**; frontend build success; PostgreSQL 16 migrations success; PostgreSQL integration **2 passed** (refresh-token rotation and concurrent opposing dependency edges).
- The PostgreSQL graph test initially failed because the test module had not registered the `ActionItem` mapper referenced by `Risk.actions`; an explicit model import fixed the test harness. The corrected run passed.
- Supplier database error correction was validated on preceding HEAD `459a8fb668e845b71a3663d9add2a50713ebf28a`: backend 276 passed / 1 skipped, frontend and PostgreSQL integration jobs succeeded.
- Phase 0 remains open: supplier-access concurrency, risk/asset deletion races, document/RAG ACL, audit durability, clean Docker stack and broader runtime validation remain under review.


## Asset-risk link/delete race — 2026-11-24

- Added row-level serialization on the Risk row in both asset-risk link creation and risk deletion.
- Added a PostgreSQL concurrency test exercising both real endpoints with independent sessions and checking that no orphaned association or deleted-but-linked risk can result.
- CI run `45458697575` passed on HEAD `1a022b8e9f4197d77d940804d3448862e087b42c`: backend 277 passed / 3 skipped, frontend build passed, Alembic upgrade passed, PostgreSQL integration 3 passed. Phase 0 remains open.


## Supplier-risk references in risk deletion — 2026-11-24

- Risk deletion now checks supplier-risk links and returns HTTP 409 instead of relying on a late FK violation.
- Supplier-risk link creation locks the same Risk row as deletion to serialize concurrent operations.
- Added a route-level regression test for the conflict response. Dedicated PostgreSQL supplier-link/delete concurrency coverage remains outstanding.


## Supplier access/link lifecycle concurrency — 2026-11-24

- Added row locks to access-request creation (Supplier → SupplierAssetLink → Asset), link termination (Supplier → SupplierAssetLink), and access approval (request → Supplier → SupplierAssetLink → Asset).
- Added PostgreSQL integration test for concurrent access-request creation versus supplier-asset link termination.
- Updated PostgreSQL CI to run this test alongside refresh-token and Cartography concurrency tests. Validation pending; Phase 0 remains open.


## Document/RAG index-delete serialization — 2026-11-24

- RAG indexing and document deletion now serialize on the source Document row using `SELECT ... FOR UPDATE`.
- Added a PostgreSQL concurrency integration test proving deletion waits for indexation, then removes the source and all chunks.
- Added the test to the PostgreSQL CI suite. Validation pending; Phase 0 remains open.


## AI prompt-injection hardening — 2026-11-24

- Executive risk-rewrite prompt now labels user-supplied risk fields as untrusted data and explicitly rejects embedded instructions.
- Added focused tests for prompt construction and factual-only constraints. CI validation pending; Phase 0 remains open.


## Document upload uniqueness and race prevention — 2026-11-24

- Added migration `0022_document_filename_unique` and matching model metadata index for case-insensitive trimmed filename uniqueness.
- Migration checks for pre-existing duplicates and stops with a remediation message rather than silently deleting or renaming data.
- Upload endpoint returns HTTP 409 for concurrent uniqueness conflicts after transaction rollback.
- Added static migration test and PostgreSQL concurrency test to CI. Validation pending; Phase 0 remains open.


## Verified CI checkpoint — 2026-11-24

- Branch: `chore/phase0-stabilization`; HEAD: `526193721d68af4edd9c1cc4128a80999b0c6394`.
- PR #1 remains open, Draft, unmerged.
- GitHub Actions runs `45463003965` and `45463014164` completed successfully on this HEAD.
- Backend: **280 passed, 6 skipped**, 9 warnings.
- PostgreSQL 16: **6 passed**. Alembic applied all revisions through `0022_document_filename_unique`.
- Frontend build: passed.
- Phase 0 remains open; this is not a production-readiness or full-security sign-off.


## Security audit log append-only guard — 2026-11-24

- Added Alembic migration `0023_security_logs_append_only`: PostgreSQL triggers reject UPDATE, DELETE and TRUNCATE on `security_logs`.
- Added PostgreSQL integration test for UPDATE/DELETE rejection and unchanged evidence.
- Scope limitation: privileged database owners can bypass/drop triggers; this is not cryptographic tamper-proofing. Audit writes remain best-effort because `log_action()` swallows failures; durable fail-closed/out-of-band audit delivery remains open.
- PostgreSQL and backend CI validation pending; Phase 0 remains open.


## Append-only audit guard validation — 2026-11-24

- HEAD `0073b1f261acef6409237db70ff60ba6aae865ba`; GitHub Actions runs `45463809824` and `45463820416` succeeded.
- Backend: **281 passed, 7 skipped**.
- PostgreSQL 16: **7 passed**, including Alembic revision `0023_security_logs_append_only` and UPDATE/DELETE rejection tests.
- Frontend build: passed.
- Audit log writes remain best-effort; append-only triggers do not protect against privileged database owners. Phase 0 remains open.


## Durable audit outbox — 2026-11-24

- Added migration `0024_audit_outbox`, JSONB outbox storage, unique log event IDs and a pending-delivery index.
- `log_action()` now commits the outbox event first; failed materialization remains pending for retry. The FastAPI lifespan starts a five-second retry worker.
- Outbox delivery is idempotent and transactionally couples the immutable log insert with marking the outbox event delivered. Failed delivery records attempt metadata.
- PostgreSQL integration test covers transient delivery failure and successful replay. CI validation pending.
- Remaining limitation: outbox persistence itself depends on PostgreSQL availability, and existing business transactions are not yet atomically coupled to outbox inserts. Phase 0 remains open.


## Durable audit outbox — CI verification — 2026-11-24

- HEAD: `15a95f136e7f3e42fcc75ad9313850f0d39ec74b`; GitHub Actions runs `45465933278` and `45465948124` completed successfully.
- Backend: **282 passed, 8 skipped**, 9 warnings.
- PostgreSQL 16: **8 passed**; Alembic applied revision `0024_audit_outbox`; the new failure/retry integration test passed.
- Frontend build: passed.
- Two initial static-test assertion mismatches were corrected; final CI is green.
- Limitation remains: business transactions and audit outbox enqueue are not yet atomic for all existing endpoints. Phase 0 remains open.


## Transactional audit enqueue — first business slice — 2026-11-24

- Added a caller-session audit enqueue helper without an internal commit.
- Risk create/update/delete now write the outbox event in the same transaction as the risk mutation.
- Added PostgreSQL test coverage asserting rollback removes the outbox row and commit preserves it.
- Other endpoint families have not yet been migrated; Phase 0 remains open.
- CI validation pending.


## Transactional audit integration — Asset Cartography — 2026-11-24

- Asset import/create/update/retire and asset relationship/asset-risk association writes now enqueue audit records using the same request database session before commit.
- Added flush-before-enqueue for newly generated identifiers.
- Added endpoint tests for enqueue ordering and deletion audit metadata.
- PostgreSQL concurrency coverage is present but must be revalidated on the new commit.
- Phase 0 remains open; supplier, document/RAG and authentication workflows are not yet migrated.



### Cartography CI regression analysis — 2026-11-24

- Reviewed complete failing logs for run 45470003937 (commit 40020d5): frontend build passed; backend failed 4 tests and PostgreSQL integration failed 2 tests; migrations succeeded.
- Backend test fixtures were not updated for the new asynchronous audit outbox flush (missing AsyncMock for session.flush); the relationship-ordering test also exhausted its mocked execute results because it invoked the endpoint twice.
- PostgreSQL concurrency fixtures supplied MagicMock Request objects; the real audit payload then contained non-JSON-serializable mock values for client IP/user-agent. Replaced these with concrete Starlette Request instances in the integration tests.
- Follow-up test-only commits: 1067a1f, d2b45bf, df9e3b4. Validation of the latest commit is required before treating these fixes as accepted.
- No production endpoint behavior was changed in these follow-up commits. Supplier audit migration remains pending.



## Supplier access audit — CI regression and correction — 2026-11-24

- Supplier access-request creation now flushes the request and enqueues its audit event through the same AsyncSession before the business commit; unexpected failures roll back and propagate.
- IntegrityError is mapped specifically to HTTP 409, while other exceptions are rolled back and re-raised unchanged.
- PostgreSQL concurrency fixture now uses a concrete Starlette Request so audit metadata is JSON-serializable.
- Run 45474317861: frontend passed; PostgreSQL integration passed (including migrations and supplier access concurrency); backend had one failing static AST assertion because the expected number of supplier IntegrityError/Exception handler pairs had not been updated for the new transactional handler.
- Updated the static test expectation from 7 to 8 matching handlers. Commit efc6d8b40631afeb0540a7f7c3133864d8ff2713.
- A new CI run for the latest commit has not yet been observed. Supplier decision/review/revocation operations remain to be migrated. Phase 0 remains open.


## Supplier access lifecycle transactionality — 2026-11-24

- The previous HEAD CI run 45476795405 passed: backend 283 passed / 9 skipped, PostgreSQL integration 9 passed after applying migrations through 0024, frontend build passed.
- CI logs exposed RuntimeWarnings for unawaited AsyncMock coroutines in asset relationship/audit tests and a SQLAlchemy document_chunks row-count warning. These warnings remain follow-up items; the green run does not establish that they are fixed.
- Migrated supplier access decision, periodic review, explicit revocation, and expiration endpoints to enqueue audit events in the same AsyncSession before commit; all branches roll back and re-raise unexpected failures, and IntegrityError maps to HTTP 409.
- Added a static source-order test covering the four lifecycle handlers. The test asserts audit enqueue precedes commit.
- Latest code/test commits: ee12644, 9947204, 55db138. A new CI run for the latest HEAD has not yet been observed.
- Supplier risk-link and supplier-asset link create/terminate operations still use post-commit log_action and remain to migrate. Phase 0 remains open.


## Supplier lifecycle follow-up and CI evidence — 2026-11-24

- Rechecked branch chore/phase0-stabilization; PR #1 remains open and unmerged.
- CI run 45479777408: PostgreSQL integration and frontend passed; backend failed one static assertion because the supplier error-handler count increased from 8 to 12 after migrating decision, review, revocation and expiration handlers.
- Updated the assertion to 12 in commit aa657c0f7fb438f3a3353bfb465cd5e488592832.
- Backend logs also exposed RuntimeWarnings from AsyncMock-backed synchronous Session.add calls in asset relationship tests. Updated test fixtures to use MagicMock for add and AsyncMock for flush in commits 0825e53 and 49cd29f. These warning fixes still require a fresh CI run.
- Supplier access decision, review (including reduction), revocation and expiration now enqueue audit events before commit in the same AsyncSession. Existing permission checks and row locks were retained.
- Supplier-asset and supplier-risk relationship create/terminate operations are still pending migration.
- Latest code/test changes are not yet CI-validated. Phase 0 remains open.


## Supplier relationship audit atomicity — 2026-11-24

- Latest verified workflow run 45480587724 on commit 4a7fd5d completed successfully for Backend checks. No other workflow runs were returned for that exact commit.
- Current branch head observed during this pass had advanced beyond 4a7fd5d (recent commit search returned 91d47a8fe29b391245449b99b55e651fa444ccb8, an unrelated README addition). The branch remains chore/phase0-stabilization and PR #1 remains open/unmerged; draft status is not exposed by the search response.
- Migrated supplier-risk association creation, supplier-asset association creation, and supplier-asset relationship termination to enqueue audit events in the same AsyncSession before commit. Existing supplier/asset lifecycle checks, access-open guard, and row locks were retained.
- IntegrityError remains the only exception mapped to HTTP 409; unexpected errors roll back and propagate.
- Extended the static audit-order test to cover all seven supplier access/relationship lifecycle handlers and updated the expected number of IntegrityError/generic exception handler pairs to 15.
- Latest implementation and test commits: 5c8b87575856dcdb84506004e5cf255a0b18cab8 and ab4927193e6434b78af9e7674f784ebc3f9e6fba. They require fresh CI validation.
- Supplier contract and supplier assessment create/update/submit/validate endpoints still use post-commit log_action and remain outside the completed transactional outbox scope. Phase 0 remains open.

## Supplier assessment transactional audit — 2026-11-24

- Assessment creation, answer updates, submission and independent validation now enqueue audit-outbox events in the same AsyncSession and before the business commit.
- Assessment answer edits, submission and validation lock the assessment row with `SELECT ... FOR UPDATE`; creation locks the active supplier row. This serializes concurrent state transitions and supplier archival/status changes for creation.
- Existing controls retained: only the designated assessor edits/submits; a different user validates; high/critical risk cannot be unconditionally approved; submitted answers are immutable.
- Unexpected failures roll back and propagate; only IntegrityError is translated to HTTP 409.
- Added AST regression assertions for all four assessment lifecycle handlers and updated the expected database-handler count. These are source-structure checks, not proof of PostgreSQL concurrency behavior.
- Commits: `a68e49a` (implementation), `ab0fccf` (focused test).
- CI for the latest commits has not yet been observed. PostgreSQL-backed concurrent submit-vs-validation and rollback-on-outbox-failure tests remain required. Phase 0 remains open.

## Supplier register, contracts and contacts — transactional audit — 2026-11-24

- Extended same-session audit-outbox writes to supplier creation, update and archive; contract creation/update; and contact creation/update.
- All supplier write handlers in `suppliers.py` now use `enqueue_audit_event` before commit; a source scan found no remaining post-commit `log_action()` calls in this endpoint module.
- Unexpected failures roll back and propagate; IntegrityError is the only database exception mapped to HTTP 409. Existing supplier row locks and lifecycle guards were preserved.
- Expanded the AST regression checks to cover these operations; the expected generic/specific database exception handler count is now 26. These checks verify source structure only.
- Commits: `6e37ee3` (contracts/contacts), `4afaef0` (tests), `fcec651` (supplier CRUD/archive), `539165c` (tests).
- Snapshot capture and its audit semantics still need explicit review. CI has not yet been observed for these commits; no runtime test result is claimed. Phase 0 remains open.

### Supplier risk snapshot audit — 2026-11-24

- Monthly TPRM snapshot capture now writes its audit-outbox event in the same transaction as the immutable snapshot.
- Added the capture handler to the source-level audit ordering test and updated the expected exception-handler count to 27.
- Commit: `09e5568` (implementation), `6c8847d` (test). PostgreSQL validation and CI for this sequence are still pending.

## CI follow-up — supplier module audit sequence — 2026-11-24

- Workflow run `45486687055` executed the PR merge ref containing commit `475b8fd` (merge SHA `c02193a2f8c2a845b1d44c9dc83ff127aac24d01`). Frontend passed; PostgreSQL integration passed (migrations and integration suite); backend had 283 passed, 9 skipped, and one failure.
- The sole failure was `test_supplier_conflict_handlers_only_map_integrity_errors_to_http_409`: its hard-coded expected AST count was 27 while the actual parser inventory returned 20. This is a test expectation defect; no application test failure was reported in that run.
- Corrected the expected count from 27 to the observed 20 in commit `1c86005`. Fresh CI for that correction is pending; no passing result is claimed.
- Note: this CI run's checked-out PR merge ref predates the latest supplier changes captured in `475b8fd` only insofar as the merge commit combines the then-current PR head and base; validation must be repeated after the correction and on the updated PR head.

## Documents and RAG — transactional audit hardening — 2026-11-24

- Document upload and deletion now enqueue audit-outbox rows in the same AsyncSession before committing the document/chunk mutation. Unexpected failures roll back and propagate; IntegrityError is mapped to HTTP 409.
- RAG indexing now accepts the authenticated actor/request context and enqueues the INDEX event in the same transaction that replaces chunks and sets `is_indexed`. The endpoint no longer performs a post-commit, independent `log_action` call.
- Added source-level regression tests for upload, delete, rollback and RAG audit ordering in `backend/tests/test_document_audit_transactionality.py`.
- Commits: `be532ff` (upload/delete), `83a3ae1` (RAG service), `7b0fe01` (endpoint integration), `420482f` (tests).
- These tests are AST/source-structure checks. PostgreSQL runtime tests for audit-outbox failure rollback, concurrent delete-vs-index, and concurrent duplicate upload are still required. Fresh CI after the supplier assertion correction and these document changes has not yet been observed.

### PostgreSQL regression coverage additions — 2026-11-24

- Updated the existing PostgreSQL index-vs-delete race test to pass an actor identity to the RAG indexer and assert that both INDEX and DELETE outbox events persist for the document.
- Updated the duplicate-upload PostgreSQL test to use a real Starlette Request and assert exactly one durable UPLOAD outbox event for the winning insert.
- Added PostgreSQL rollback tests: upload must not persist a document if outbox enqueue fails; RAG re-index must preserve the previous chunk set and leave `is_indexed` false if audit enqueue fails.
- The tests are committed but not yet executed by a fresh CI run. No runtime pass is claimed.
- Commits: `5d3b449`, `dc10508`, `c7b6c24`, `393e02f`, `883927c`, `1257106`.

## Authentication and migration documentation reconciliation — 2026-11-24

- Rewrote `docs/AUTH_SESSION_SECURITY_REVIEW.md` to reflect implemented persisted refresh sessions, hashed JTI, rotation/reuse revocation, logout and password-change revocation. Remaining gaps are explicitly listed: administrative lifecycle revocation, refresh audit events, HTTP-level PostgreSQL concurrency, distributed rate limiting, MFA-secret encryption and frontend token storage.
- Reconciled `docs/SECURITY_ENGINEERING_BACKLOG.md`: persisted refresh-session rotation and password-change/logout revocation are marked implemented; incomplete administrative revocation and refresh audit coverage remain open.
- Corrected `docs/PHASE0_DATABASE_VALIDATION_RUNBOOK.md` to target Alembic head `0024_audit_outbox` rather than the stale `0021` revision.
- Commits: `7cbb5ba` (auth review), `2e226c8` (backlog), `206dc53` (database runbook).
- The latest commit has no workflow run returned by the PR-triggered workflow lookup. The last observed run `45486687055` had frontend and PostgreSQL integration jobs passing, while backend had 283 passed, 9 skipped and one incorrect AST-count assertion (27 expected, 20 observed). That assertion was corrected in `1c86005`; fresh validation of the corrected supplier test and subsequent document/RAG changes remains outstanding.


## Refresh-session audit transaction — 2026-11-24

- Refresh rotation now writes REFRESH_TOKEN_ROTATED to audit_outbox before committing replacement session creation and old-session revocation.
- Reuse detection writes REFRESH_TOKEN_REUSE_DETECTED in the same transaction as revocation of all active sessions; eligibility denials write REFRESH_DENIED_SESSIONS_REVOKED with the reason.
- Logout now locks the persisted session row, revokes it and enqueues REFRESH_SESSION_LOGOUT in the same transaction. Invalid or already-revoked tokens remain idempotent.
- All three mutation paths explicitly roll back and re-raise if audit enqueue or commit fails.
- Added PostgreSQL integration tests invoking the actual refresh endpoint concurrently with one token, verifying exactly one successful response, replay revocation and both audit events; added audit-enqueue-failure rollback coverage. Updated logout unit tests to verify audit event enqueue.
- Commits: a5ff17b (refresh audit), b0adc25 (rollback), 9febb71 (logout audit), cd0f8db (PostgreSQL refresh tests), d0e51b9 and 801cb8a (logout tests), 44c12cf (backlog), 4ed8834 (auth review), defb67e (security findings).
- These latest authentication tests have not yet been executed by a fresh CI run. Administrative session revocation on account disable/role change/MFA reset remains open.


## RBAC authentication gate hardening — 2026-11-24

- Closed a defense-in-depth inconsistency: RBAC normalized role strings, but get_current_user previously compared privileged roles case-sensitively for MFA enforcement and did not reject missing/malformed role claims.
- Persisted roles are now normalized before admin/executive MFA enforcement. Access tokens must contain a non-empty string role claim matching the normalized persisted role.
- Added focused tests for privileged MFA enforcement and role-claim validation.
- Commits: 07c434f and 8149214. No CI result for these commits has yet been observed.


## CI follow-up — RBAC role-claim test correction — 2026-11-24

- Workflow run 45491802074 on the PR merge ref completed the frontend build successfully. Backend reported 292 passed, 13 skipped and one failing parametrized RBAC test.
- The failing parameter expected a denial for token role viewer while the persisted user role was also viewer. The test case was corrected to use admin as the mismatched token role in commit f42e108. This was a test-data correction; the implementation behavior was correct.
- PostgreSQL migration/integration job was still in progress at the time of this status update. Its final result must be checked separately.
- The run was created before commit f42e108, so it does not validate that correction. A fresh PR workflow run is required.


### Final PostgreSQL result for workflow 45491802074 — 2026-11-24

- PostgreSQL 16.16 clean database was initialized and Alembic upgraded successfully from 0001 through 0024_audit_outbox.
- PostgreSQL integration suite completed successfully: 13 passed. This includes refresh rotation, asset relationships, supplier access lifecycle, document/RAG index-vs-delete, duplicate upload, append-only audit log and durable outbox tests.
- Frontend build completed successfully.
- Backend unit job had 292 passed, 13 skipped and one failing test-data case (viewer token against viewer user); the parameter was corrected to admin in commit f42e108.
- Important: run 45491802074 checked out the PR merge ref before f42e108, so its backend failure does not validate the correction. A fresh backend CI result on the corrected branch head is still required.


### Fresh PostgreSQL migration evidence — workflow 45491802074

- On PR merge commit 2bd0c01 (PR head 677c299), CI initialized PostgreSQL 16.16 from an empty data directory and successfully applied every Alembic revision from 0001_initial through 0024_audit_outbox.
- The configured PostgreSQL integration suite passed: 13 passed. It included actual endpoint refresh concurrency/replay and rollback, asset graph, supplier access lifecycle, document/RAG delete/index race, duplicate upload uniqueness, append-only security logs and durable outbox tests.
- This closes the clean-database Alembic upgrade-to-head check for that PR head. It does not prove upgrade from an existing supported production revision, downgrade symmetry, schema drift comparison, backup/restore, or a full Docker Compose stack build/start.
- The same run's frontend job passed. Backend unit job failed only the RBAC test-data case documented above; its corrected case is not yet covered by a new backend run.


## Authentication follow-up — 2026-11-25

- Commit e045baf couples password-change state, prior refresh-session revocation, replacement session issuance and PASSWORD_CHANGED outbox event in one transaction.
- Commit 523b7d1 couples MFA completion audit events with their state/session transaction.
- Commit 7b90394 locks the user row and audits MFA enrollment-start secret persistence transactionally.
- Commit e914e90 adds tests for enrollment audit ordering and rollback. Commit 1f40707 adds tests for password-change audit ordering and rollback.
- The latest head has not yet returned a PR workflow run; these tests are committed but not claimed as executed.
- The account/role/MFA administration API is not present in the reviewed route tree, so proactive revocation on those administrative changes cannot yet be integrated into an existing handler. This is an explicit Phase 0 gap, not marked complete.

## CI validation — workflow 45568463812 — 2026-11-25

- All three jobs completed successfully on the PR merge ref: backend, PostgreSQL integration and frontend.
- Backend unit tests: 297 passed, 13 skipped, 8 warnings.
- PostgreSQL integration: 13 passed, 6 warnings. Fresh PostgreSQL 16 migration job and integration tests succeeded.
- Frontend: npm ci and npm run build succeeded.
- This run includes the latest auth transaction additions, password-change/MFA enrollment audit tests and the RBAC test-data correction.
- Warnings remain for review; CI success is not equivalent to a production security sign-off.

## Follow-up after green CI — warning cleanup and browser auth gate — 2026-11-25

- Workflow 45568463812 was fully green before this follow-up: backend 297 passed/13 skipped; PostgreSQL 13 passed; frontend build passed.
- The backend warning trace identified an unawaited AsyncMock from `session.add` in the initial-MFA enrollment unit test. The mock now models SQLAlchemy's synchronous `AsyncSession.add` as a MagicMock and `flush` as AsyncMock.
- The PostgreSQL SAWarning came from ORM-deleting child chunks and then the parent while the FK also uses ON DELETE CASCADE. Document deletion now bulk-deletes child chunks before deleting the parent.
- Added root pytest.ini to make asyncio fixture loop scope explicit.
- These warning fixes are committed after workflow 45568463812 and await a fresh CI run; do not count them as validated yet.
- The frontend review confirmed refresh and access tokens are persisted in localStorage. GitHub issue #4 tracks the required coordinated HttpOnly-cookie/CSRF/CORS migration. This remains a Phase 0 security blocker.

## HttpOnly refresh-cookie migration and Compose smoke gate — 2026-11-25

- Backend now issues the refresh token only as an HttpOnly cookie (Secure outside development, SameSite=Strict, host-only, path `/api/v1/auth`, bounded max-age). TokenPairResponse no longer serializes refresh_token.
- Refresh and logout accept cookie-based transport, require a trusted Origin against the explicit CORS allowlist when the cookie is used, rotate/clear the cookie and preserve audit-outbox transaction semantics. Legacy JSON token input has been removed from both refresh and logout endpoints; cookie transport is now mandatory.
- Frontend keeps the short-lived access token in memory, sends credentialed requests, restores session through cookie refresh after reload, and single-flights concurrent bootstrap calls to prevent refresh-token replay.
- Added backend tests for cookie flags, absence of refresh_token in response schema, untrusted Origin rejection, cookie logout clearing and PostgreSQL cookie rotation/replay.
- Compose review found Vite proxy was targeting localhost inside the frontend container. It now targets backend service DNS via VITE_API_PROXY_TARGET; Compose pins pgvector to pg16 and uses npm ci. A clean Compose smoke job now validates config, builds backend, starts all services and verifies API health plus frontend-to-backend proxy.
- CI for these latest cookie/Compose changes is pending; do not mark the issue closed until it passes and same-site production topology is confirmed.

## CI follow-up — cookie test harness correction — 2026-11-25

- Workflow 45569880462 tested the initial cookie migration: frontend build passed; backend 303 passed, 13 skipped, one failed; PostgreSQL integration 12 passed, one failed. Both failures had the same cause: direct Python calls saw FastAPI's Cookie(...) marker object as the default instead of `None`, so body-fallback tests were incorrectly treated as cookie-authenticated and failed Origin validation.
- Corrected endpoint signatures to use `Annotated[str | None, Cookie(...)] = None`, preserving FastAPI cookie injection while making direct-call defaults genuinely optional.
- Added Compose smoke job, Vite proxy service DNS fix and pgvector pg16 pin. The workflow 45569880462 predates the final correction and Compose smoke job; a fresh run is required.

## CI final validation — workflow 45572713404 — 2026-11-25

- All four jobs passed on the PR merge commit for branch head b08c70f: backend, PostgreSQL integration, frontend and Docker Compose smoke.
- Backend: 303 passed, 13 skipped; no Python/Pydantic/SQLAlchemy/AsyncMock warnings in the test summary.
- PostgreSQL: 13 passed; clean PostgreSQL 16 migration reached 0024_audit_outbox. Expected error logs from duplicate-upload and append-only enforcement tests are assertions, not job failures.
- Frontend: `npm ci` succeeded using committed lockfile; `npm audit` reported 0 vulnerabilities; Vite 6.4.6 production build succeeded.
- Docker Compose: config validation, backend image build, PostgreSQL/backend/frontend startup, API health and frontend-to-backend proxy all passed; stack cleanup passed.
- Remaining frontend warning: one production JS chunk is 534 kB (gzip 177 kB); this is a performance/code-splitting improvement, not a failed build.
- Remaining Phase 0 gates: document classification/ACL design, administrative session revocation integration, MFA secret encryption/key management, distributed rate limiting, legacy migration/downgrade/backup-restore review, and human security review.

## Document ACL hardening — 2026-11-25

- Implemented doc_type-derived INTERNAL/RESTRICTED classification and server-side viewer filtering for list, preview and download.
- Unknown legacy document types default to RESTRICTED (fail closed). Privileged roles admin/executive/auditor retain access; viewer sees PSSI, PROCEDURE and REGLEMENT_INTERIEUR only.
- API response and document library UI now display classification. Unit and PostgreSQL tests added; fresh CI pending.
- RAG indexing remains admin-only; there is no semantic retrieval route today. Future RAG search must apply the same ACL before chunk retrieval.

## MFA secret encryption implementation — 2026-11-25

- New MFA secrets are stored as Fernet ciphertext; TOTP verification decrypts in memory. Legacy plaintext is migrated lazily on verification.
- Production/staging require a valid `MFA_ENCRYPTION_KEYS` key ring. Startup blocks if plaintext secrets remain. An operator script supports dry-run migration and key rotation.
- Runbook: `docs/MFA_SECRET_ENCRYPTION_RUNBOOK.md`. Unit tests added; CI pending.

## MFA secret encryption code and test coverage — 2026-11-25

- Added Fernet encryption at rest for TOTP secrets, managed key-ring configuration, legacy plaintext migration script, key rotation and non-development startup integrity gate.
- Added unit and PostgreSQL tests. Latest CI workflow 45574715908 is pending.

## CI validation — MFA encryption and document ACL — workflow 45574537534

- All four jobs passed on the PR head containing document classification ACL and MFA encryption: backend, PostgreSQL integration, frontend and Compose smoke.
- Backend: 341 passed, 14 skipped; no Python deprecation, SQLAlchemy or AsyncMock warnings in the test summary.
- PostgreSQL: 14 passed, including document classification list/preview/download ACL and MFA ciphertext persistence/startup verification. Fresh PostgreSQL migrations through 0024_audit_outbox remain green.
- Frontend: npm ci and npm audit zero-vulnerability gate passed; Vite production build passed.
- Docker Compose: full stack and frontend-to-backend proxy smoke passed.
- MFA code is validated, but before production deployment the operator must run the documented migration script against the target database, back up the Fernet key, and confirm the actual key custody/rotation procedure.

## Latest green CI — workflow 45574715908 — 2026-11-25

- 4/4 jobs passed on the PR head containing MFA Fernet encryption and document classification ACL.
- Backend: 342 passed, 15 skipped.
- PostgreSQL integration: 15 passed; clean PostgreSQL 16 migration chain through 0024_audit_outbox and real DB checks for document ACL and MFA encrypted persistence/startup validation.
- Frontend: `npm ci`, `npm audit` (0 vulnerabilities) and Vite 6.4.6 production build passed.
- Docker Compose: configuration, backend image build, full stack startup, API health, frontend proxy and cleanup passed.
- Non-blocking observations: Node `url.parse()` deprecation comes from the Actions toolchain; Vite reports one JS chunk above 500 kB. Neither failed the build.
- Remaining production gates are operational: run the MFA legacy migration on the target DB, back up/assign ownership for the Fernet key ring, confirm production same-site cookie topology, implement administrative session revocation/rate limiting, and rehearse legacy DB upgrade/restore.

## Access-token revocation enforcement — 2026-11-25

- Confirmed a gap in `get_current_user()`: the User model and JWT issuance already maintained `auth_version`, and migration `0025_user_auth_version` existed, but authenticated requests checked only the role claim and did not compare the token version to the current database value.
- Enforced strict integer `auth_version` equality on every access-token authentication. Missing, boolean, malformed or stale claims are rejected with HTTP 401, forcing re-authentication after security-sensitive account changes.
- Added RBAC dependency tests for missing/malformed/stale versions and matching versions. Existing fixtures were updated to provide the version claim.
- Commits: `2a5f014` (enforcement), `796b3da` and `e8c0bb1` (tests/fixture correction).
- No CI run has yet been returned for this latest HEAD. The change and tests are committed but not yet runtime-validated.
- This closes immediate access-token invalidation at the authentication dependency layer. It does not replace the remaining work on administrative account-management endpoints, distributed rate limiting, or operational session/key management.

## JWT issuance ordering after auth-version enforcement — 2026-11-25

- A follow-up review found that the SQLAlchemy `User.before_update` listener increments `auth_version` during flush. MFA enrollment completion and forced password change previously minted replacement JWTs before that flush, which could make the newly issued tokens immediately stale once the transaction committed.
- Added an explicit flush before minting access/refresh tokens after MFA state changes and after forced password change. The version claim now reflects the persisted security state.
- Added focused tests that simulate the version bump during flush and assert the replacement access token receives the incremented version for both MFA enrollment and password change.
- Commits: `635fde4`, `8cca49c` (ordering correction), `e6a8ab3`, `0e556da` (tests).
- These changes have not yet been run in CI; the latest workflow and PostgreSQL integration evidence remains the earlier green workflow `45574715908`, which predates this auth-version enforcement/fix series.

- Tracking issue created: [#5 — administrative account lifecycle, distributed rate limiting and database recovery rehearsal](https://github.com/cherifmeh-ui/pgcc-platform/issues/5). It captures remaining controls that cannot be honestly marked complete from the current API surface or CI evidence.

## Refresh-token auth-version enforcement — 2026-11-25

- Extended the refresh-token account-state snapshot check to require a strict integer `auth_version` claim matching the current `users.auth_version`. Missing, boolean, malformed or stale claims follow the existing policy-change path: all active refresh sessions are revoked, an audit-outbox event is enqueued in the same transaction, the cookie is cleared and the request is rejected with HTTP 401.
- Extended the PostgreSQL refresh policy-change integration cases with an explicit auth-version mismatch scenario. Updated the refresh-token factory in the endpoint integration test to accept and persist the `auth_version` claim.
- Commits: `d64535b` (endpoint enforcement), `ac83e33` and `47574c9` (PostgreSQL test coverage and fixture correction).
- Runtime validation remains pending: the latest commit has not yet produced a CI workflow result. The PostgreSQL test requires `PGCC_INTEGRATION_DATABASE_URL` and was not run manually in this session.

## Backend CI failure triage and fixture corrections — 2026-11-25

- Inspected the complete backend job log for workflow run `45577665026`. Python compilation passed. PostgreSQL integration, frontend build and Docker Compose smoke jobs passed. Backend unit tests reported 347 passed, 18 skipped and 3 failures.
- Failure 1: `test_get_current_user_accepts_normalized_matching_role` used a user mock without `auth_version`; corrected the fixture to model the persisted account version.
- Failures 2–3: two JWT reserved-claim tests expected the old exception text. The implementation now rejects both JWT protocol claims and account-state claims; relaxed the assertion to match the shared reserved-claim wording without weakening the expected `ValueError`.
- Also corrected the refresh audit-rollback PostgreSQL fixture to include `auth_version` in its legacy refresh payload, so it tests rollback semantics with the current token contract.
- Commits: `b724837`, `1bafc11`, `32c803f`.
- These corrections have been committed to `chore/phase0-stabilization`; a new CI run is required to establish whether the backend suite is green. No Phase 0 closure claim is made.


## Point de contrôle — 2026-11-25 (correction du test JWT)

- HEAD de la branche et de la PR #1 : `3466e35bf2c327c0f9665d10abcf03728da37837`.
- PR #1 : ouverte, en brouillon, non fusionnée ; base `main`.
- Analyse du run GitHub Actions `45578235822` : intégration PostgreSQL, frontend et smoke test Docker réussis ; backend en échec avec **349 réussites, 18 tests ignorés et 1 échec**.
- L'unique échec backend provenait d'une assertion de test obsolète dans `backend/tests/test_security.py` : elle attendait le texte `reserved JWT claims`, alors que le code refuse désormais la surcharge des revendications de sécurité du compte avec le message `reserved account-state claims`.
- Correction appliquée dans le commit `3466e35` : les deux assertions vérifient maintenant la formulation stable `reserved .* claims`.
- Le contrôle CI du HEAD `3466e35` n'est pas encore disponible dans les résultats consultés. La correction est donc **en attente de validation CI** ; les résultats du run précédent ne sont pas transposés au nouveau HEAD.
- La validation PostgreSQL du schéma et des migrations, les tests de concurrence de rotation des refresh tokens et la clôture globale de Phase 0 restent requis.
- La gestion administrative du cycle de vie des comptes demeure une spécification ; aucune API correspondante n'est déclarée implémentée.


## Point de contrôle — 2026-11-25 (gestion administrative initiale des comptes)

- Le dernier contrôle CI complet précédemment observé sur le HEAD `bbfbb44` est entièrement vert : backend, intégration PostgreSQL, frontend et smoke test Docker Compose.
- Une première tranche de gestion administrative des comptes est maintenant ajoutée sur la branche : permission RBAC `users:manage` (admin uniquement), routeur `/admin/users`, liste/détail, modification de profil/role/activation, réinitialisation MFA et révocation des sessions.
- Les opérations sensibles écrivent l'événement dans l'audit outbox au sein de la transaction métier et révoquent les refresh sessions concernées. Le reset MFA supprime secret et hashes des codes de secours ; les réponses n'exposent pas ces valeurs.
- Les opérations qui pourraient retirer le dernier administrateur actif avec MFA verrouillent les comptes concernés et refusent cette transition.
- Tests unitaires ajoutés pour la matrice RBAC, les rôles acceptés, le rejet des champs sensibles/inconnus et la minimisation des réponses.
- Le premier run CI sur le commit intermédiaire a révélé deux erreurs de syntaxe dues à des retours à la ligne mal encodés dans le routeur API et la matrice RBAC. Ces erreurs ont été corrigées ; le nouveau HEAD déclenche un nouveau run CI. Les tests PostgreSQL de concurrence, rollback d'audit et invalidation réelle des access/refresh tokens restent à ajouter/exécuter. Cette tranche n'est donc pas encore déclarée validée.
- Le provisionnement/création des comptes n'est pas implémenté ; il reste séparé pour éviter de définir un flux d'identité/invitation sans décision métier.
