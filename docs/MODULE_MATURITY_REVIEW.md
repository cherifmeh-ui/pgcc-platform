# PGCC — Revue initiale de maturité des modules

**Date:** 21 novembre 2026  
**Branche:** `chore/phase0-stabilization`  
**Statut:** Inventaire initial sur la base de la structure du dépôt et de la documentation. Les statuts ne constituent pas une validation fonctionnelle.

## Méthode

- **Présent dans le dépôt:** modèles, endpoints, services, vues ou tests repérés.
- **Partiel:** une base de code existe, mais la complétude ou les validations ne sont pas démontrées.
- **À vérifier:** une revue ciblée, des tests ou une validation runtime sont nécessaires.
- **Absent/non identifié:** aucun module dédié repéré lors de l'inventaire initial; cela ne prouve pas l'absence de toute fonctionnalité connexe.

## Inventaire initial

| Domaine | Éléments repérés | Statut initial | Revue nécessaire |
|---|---|---|---|
| Authentification / RBAC | endpoints auth/me, core security, RBAC, store auth, tests CI | Présent, à sécuriser | sessions, rotation/revocation, MFA, permissions par endpoint, scénarios négatifs |
| Risques | endpoint risks, modèle Risk, scoring service, vue Risks | Présent, maturité inconnue | lifecycle, scoring, résiduel, acceptation, historique, liens, audit |
| Actions | endpoint actions, ActionItem, verification, workflow/lifecycle services, panel UI | Présent, maturité inconnue | états, transitions, ownership, échéances, preuves, vérification, tests |
| Cartographie / actifs | endpoint assets, Asset, Applications, AssetsView, docs d'implémentation/revue | MVP, à valider | import, pagination, filtres, export, graph, dépendances, impact, intégrité et RBAC |
| Applications | endpoint apps, modèle Application, AppsView | Présent | relation avec Asset, source de vérité, lifecycle, imports |
| Conformité ISO | endpoint compliance, ISOControl, assessment/evidence models, ISO view | Partiel | dataset 93 contrôles, source/licence, applicability, assessment workflow, preuves, SoA |
| Documents / preuves | endpoint documents, Document/Chunk, extractor, RAG, DocumentsView | Partiel | ACL au retrieval, versioning, stockage, malware scanning, sandbox parsing, retention |
| IA / RAG | endpoints ai/ai_advanced, AI services, RAG, assistant UI | Présent, à valider | grounding, citations, permission filtering, prompt injection, modèles/config, tests |
| Fournisseurs / TPRM | endpoint suppliers, supplier models/services, view, docs, ADR | Développé en grande partie, à valider | workflows, validations, permissions, migrations, access expiry, snapshots/trends |
| Reporting | endpoint reports, dashboard, TPRM printable report | Partiel | KPI definitions, authorization, report scope, PDF/CSV/XLSX, audit exports |
| Journaux sécurité | endpoint security_logs, SecurityLog model/service | Présent | tamper resistance, retention, alerting, privileged access, export |
| Audits | aucun endpoint/model/view Audit dédié identifié dans l'inventaire | Non identifié | concevoir programme, missions, constats, recommandations, preuves, actions |
| Gouvernance | aucun domaine organisation/gouvernance dédié identifié | Non identifié/partiel | unités organisationnelles, politiques, objectifs, décisions, owners, approvals |
| Notifications/workflows transverses | services action/supplier présents; orchestration globale non identifiée | Partiel | échéances, email/in-app, retries, préférences, audit, règles de déclenchement |
| Administration | apps/auth/config existants | Partiel | gestion utilisateurs/rôles/périmètres, paramètres, configuration, audit |
| Infrastructure / production | Docker Compose, CI workflows, migrations | En cours | fresh install, existing DB upgrade, secrets, backups, restore, monitoring, reverse proxy, hardening |

## Risques transverses prioritaires à confirmer

1. Stratégie Alembic baseline et migration sur bases neuves/existantes.
2. Tests API d'intégration (auth, permissions, risks, actions, documents, suppliers).
3. Isolation des documents et du RAG selon permissions/classification.
4. Historique formel des risques et acceptation du risque résiduel.
5. Audit logs: intégrité, rétention et alertes.
6. Sécurité upload/parsing: antivirus et isolation/sandbox.
7. Ownership actions et entités organisationnelles: relations structurées plutôt que champs libres lorsque pertinent.
8. Données de conformité et preuves: validation et provenance.
9. Déploiement/backup/restore/monitoring et runbooks.

## Priorité de revue

- **P0:** Phase 0 — migration baseline, CI HEAD, Docker/runtime, auth/RBAC, documents/RAG ACL, revue PR.
- **P1:** Cartographie, risques et actions — intégrité des liens et workflows de bout en bout.
- **P1:** TPRM — lifecycle fournisseur, accès, contrats, assessments et indicateurs.
- **P2:** Conformité — dataset, assessments, evidence et SoA.
- **P2:** Reporting — définitions KPI et permissions.
- **P3:** Audits, gouvernance, notifications et industrialisation — cadrage et backlog détaillé.

## Prochaine mise à jour

Chaque module sera revu à partir de ses fichiers réels (models, schemas, endpoints, services, frontend, migrations et tests). Le statut sera remplacé par **Validé**, **Partiel**, **Bloquant** ou **Non commencé**, avec références aux tests et aux issues de backlog.

## Findings from first code-level sampling

These observations are directly visible in the current branch files and require follow-up tests or remediation; they are not exhaustive.

### 1. Reporting endpoint is narrow and uses hard-coded classification

- `backend/app/api/v1/endpoints/reports.py` exposes `GET /reports/dg-summary`.
- The endpoint aggregates risks, critical applications, PAC actions, and requests an AI-generated executive summary.
- Risk category classification is based on title/threat keyword matching; risk-level bands are hard-coded in the endpoint.
- The endpoint does not yet provide a consolidated GRC report covering assets, ISO assessments/evidence, supplier risk, audits, or governance.
- Follow-up: centralize KPI definitions, test the classification thresholds, establish report period/filters and data provenance, and separate deterministic data from AI narrative.

### 2. RBAC inventory

- Backend `backend/app/utils/rbac.py` is documented as the permission source of truth.
- Asset read is restricted to admin, executive and auditor; viewer does not receive `assets:read`.
- Supplier read is restricted to admin, executive and auditor; viewer does not receive `suppliers:read`.
- Risk, action, document, ISO, app and dashboard read permissions include viewer.
- Risk acceptance permission exists for admin/executive, but its actual endpoint/workflow must be verified against the current risk API.
- Follow-up: build a route-to-permission matrix and automated negative tests for each role, including dashboard visibility and report access.

### 3. Auth frontend storage and session lifecycle

- `frontend/src/stores/auth.js` persists access and refresh tokens, role, and permissions in browser localStorage.
- MFA confirmation stores the session and loads permissions.
- Logout clears local values and redirects, but the sampled frontend action does not itself call a server-side revocation endpoint.
- Follow-up: review refresh-token rotation, reuse detection, server-side revocation, expiration, logout semantics, and browser storage threat model. Do not mark session security complete based on unit tests alone.

### 4. Database migration strategy

- Migration series currently includes `0001_initial` through `0019_supplier_risk_snapshots`.
- `docs/DATABASE_MIGRATIONS.md` explicitly warns that existing databases created by `create_all()` must be inspected and backed up before stamping the baseline.
- The baseline is described as transitional metadata-based initialization, not a fully hand-authored migration history.
- Follow-up: verify fresh DB upgrade, legacy/dev DB baseline/stamp path, constraints/indexes and downgrade safety using disposable databases.

### 5. CI scope

- The backend workflow installs dev dependencies, compiles backend modules, and runs pytest.
- The frontend workflow runs `npm ci` and `npm run build`.
- These checks do not establish runtime integration with PostgreSQL, Docker deployment, migration execution, browser end-to-end behavior, or production readiness.
- Follow-up: add DB-backed API integration tests, migration CI, container build, and smoke tests in a controlled environment.

### 6. Audit module gap

- No dedicated Audit model, endpoint, or frontend view was identified in the initial repository tree.
- Existing risks, controls, documents, and actions can support parts of audit work, but do not replace a formal audit lifecycle.
- Follow-up: design the audit domain and its links to findings, risks, controls, assets, suppliers, evidence, and actions.

### 7. Evidence and RAG security

- Document upload, extraction, indexing, preview/download and RAG services exist.
- Security review documents already flag retrieval-time authorization, parsing isolation and malware scanning as open risks.
- Follow-up: validate access checks at every document operation and retrieval path; test unauthorized cross-document retrieval; implement or document malware scanning and parser isolation.

## Evidence and limits

The sampling used repository files on the current branch. No local runtime, fresh database, Docker deployment, browser E2E or penetration test was executed during this review. CI status is commit-specific and must be checked separately.

## Security review — targeted source inspection (Phase 0)

This section records source-level findings from a targeted inspection. It is not a penetration test and does not establish exploitability.

### S0 — Document access is role-wide, not document-scoped

- `GET /documents/`, `/{doc_id}/preview`, and `/{doc_id}/download` enforce the `documents:read` permission.
- The current permission matrix grants this permission to admin, executive, auditor and viewer.
- The sampled endpoints do not implement document classification, per-document access policy, department/owner scope, or a distinction between preview and binary download.
- **Decision:** keep the current RBAC enforcement, but treat document confidentiality scope as a Phase 0 security gap. Before production, define classification and access policy; add negative integration tests. Do not silently restrict roles without a business-approved matrix.

### S1 — Upload parsing is synchronous and only signature/size constrained

- Upload is capped at 10 MiB and checks the PDF or ZIP/DOCX signature before extraction.
- Extraction runs synchronously in the API process; no malware scanning or sandbox isolation was identified in the sampled route.
- **Decision:** retain the size cap and validation. Production gate: malware scanning and isolated parsing (or documented compensating controls), tests for malformed and adversarial files, and resource/time limits.

### S2 — MFA enrollment and token/session lifecycle need end-to-end review

- Login creates a short-lived pre-auth token after password validation.
- MFA enrollment uses that token to initialize an MFA secret; confirmation activates MFA and issues access/refresh tokens.
- Refresh checks account status, lockout, mandatory password change, MFA for sensitive roles, and password-change timestamp.
- Tokens include `jti`, but the sampled refresh flow does not persist a refresh-token family or revoke previous tokens on rotation. Server-side logout/revocation behavior requires verification.
- **Decision:** do not claim refresh-token rotation/revocation is complete. Design a persisted session/token model or an explicitly accepted revocation strategy before production.

### S3 — Login throttling is account-based

- Failed password and MFA attempts increment account-level counters and temporarily lock the account.
- No IP/network rate limiting or distributed throttle was identified in the inspected auth route.
- **Decision:** add rate limiting at application/reverse-proxy layer and tests for distributed abuse; ensure account-lockout behavior cannot be trivially used to deny service to target accounts.

### S4 — Production configuration is guarded, but deployment remains development-oriented

- Settings validate minimum HS256 secret length, production DEBUG/CORS and placeholder-secret restrictions.
- The sampled Compose file exposes database/backend/frontend development ports, mounts source, and starts frontend via dev server.
- **Decision:** this Compose configuration is a development stack, not a production deployment. Create a separate hardened production profile (non-root, immutable images, restricted ports, TLS reverse proxy, secrets, health checks, backup/restore and observability) in Phase 8.

### S5 — Migration baseline is an explicit release blocker for existing deployments

- Migration documentation warns that legacy `create_all` databases require inspection and a reviewed baseline before Alembic is applied.
- **Decision:** no production migration should be applied until fresh-install and legacy-baseline procedures are tested on disposable databases and documented with recovery/backup evidence.

### Verification boundaries

No Docker startup, database-backed integration test, live API test, penetration test, malware scan or migration run was performed during this source inspection. Findings must be validated by tests and deployment review.

## Corrective finding resolved during review

### DOCX extraction paragraph separators

The initial code-level review found that DOCX extraction joined paragraphs/table rows using the literal characters `\\n\\n`, rather than actual newline separators. This degraded extracted text and downstream RAG context readability.

- Corrected in `backend/app/services/document_extractor.py`.
- Added regression assertions in `backend/tests/test_document_extractor_security.py` for actual paragraph/table separation and truncation marker line breaks.
- GitHub Actions backend checks on the current review commit have passed; the frontend job is still running at the time of this update.

### M0 — pgvector extension prerequisite

- The initial baseline creates SQLAlchemy metadata containing the PostgreSQL `vector` column type used by `document_chunks.embedding`.
- The previous baseline did not explicitly create the `vector` extension before creating tables; development startup also called `create_all()` without enabling the extension.
- **Correction applied:** `0001_initial.py` and development startup now execute `CREATE EXTENSION IF NOT EXISTS vector` before metadata creation. A static regression assertion was added.
- **Remaining validation:** disposable PostgreSQL run must confirm the image contains pgvector and the DB role has extension-creation rights. Existing stamped databases require inspection; the baseline will not run again automatically.


## Asset inventory integrity review — correction applied

- The API normalizes asset references by trimming whitespace, but the previous database unique index only compared `lower(reference)`; legacy rows with leading/trailing whitespace could bypass normalized uniqueness.
- Asset type validation in the model included `cloud_resource`, but migration `0006` did not. This would create model/schema drift and reject this type on a migrated database.
- Migration `0020_asset_reference_and_type_constraints` now checks for normalized duplicate references, creates a unique index on `lower(btrim(reference))`, prohibits blank references at DB level, and aligns the allowed asset types.
- The SQLAlchemy model now matches these constraints and a schema test protects the normalized index and nonblank constraint.
- **Important:** migration 0020 fails safely if existing normalized duplicates are found. Resolve these records through a reviewed data-cleanup process before upgrading; do not automatically rewrite inventory references.

- Migration 0020 downgrade also fails safely if `cloud_resource` assets exist, because the previous check constraint did not permit that type. The records must be migrated deliberately before downgrade.


### 8. Asset relationship lifecycle validation

- Relationship creation now locks the source and target asset rows in deterministic order and rejects links involving retired assets.
- A pure helper and regression tests cover active, retired, and missing endpoint rows.
- Existing dependency-cycle detection remains in place.
- Limitation: row locking of endpoints reduces concurrent mutation races, but a database-level graph constraint is not available; high-concurrency cycle creation still requires integration tests or a serialized graph-mutation strategy.
- Follow-up: test relationship creation against PostgreSQL and review all relationship types for lifecycle semantics.

### 9. Asset lifecycle status and risk-link integrity

- Asset PATCH now synchronizes the lifecycle status with the retirement marker: explicit `Retiré`/`Décommissionné` sets `retired_at`, and an explicit active/non-retired lifecycle status clears it.
- The transition is isolated in a pure helper with regression tests for retirement, decommissioning, reactivation, status-omitted updates, and timestamp preservation.
- Asset-to-risk linking now rejects retired assets with HTTP 409; missing assets/risks remain 404, and duplicate association remains protected by the unique constraint.
- **Remaining validation:** route-level authorization/HTTP tests and PostgreSQL lifecycle/relationship integration tests are still required. Review whether lifecycle changes should automatically unlink, retain, or mark historical asset relationships; current decision is to preserve associations for audit history.

### 10. Application-to-asset referential integrity

- The `assets.application_id` foreign key uses `ON DELETE RESTRICT`, which correctly prevents deleting an application still referenced by assets.
- The application deletion endpoint previously allowed the database integrity error to escape as an unhandled server error.
- **Correction applied:** the endpoint now rolls back and returns HTTP 409 with an actionable message when linked assets prevent deletion.
- **Remaining validation:** add route-level tests for the conflict response and verify that successful deletion and audit logging still work.

### 11. Supplier archive and access lifecycle

- Supplier archival now refuses to proceed while supplier-asset links remain `Actif`.
- Archival also refuses while supplier access requests are in `Demandé`, `Approuvé`, or `Suspendu` states.
- The archive operation intentionally does not silently terminate links or revoke approvals: those actions require their own traceable workflows and actors.
- Regression tests cover both conflict conditions.
- **Remaining validation:** route-level role/permission tests and database integration tests are pending; review whether terminated supplier status should also block new link creation and access approvals (currently archived state is the explicit block).

- Additional safeguard: new supplier-asset relationships are blocked when the supplier is `Suspendu` or `Terminé` (HTTP 409). Existing relationships remain available for explicit termination and historical review.

- Supplier-asset link termination now refuses to close a relationship while any associated access request remains `Demandé`, `Approuvé`, or `Suspendu`; the access workflow must be explicitly revoked/closed first. Regression test added.

- Supplier status changes to `Suspendu` or `Terminé` now require active supplier-asset links to be terminated and open access requests/approvals to be revoked or closed first. This prevents status-only suspension from leaving access approvals active; a regression test covers the open-request case.

- Supplier access requests and approvals now reject retired assets using both lifecycle status and the `retired_at` marker, protecting against inconsistent historical rows. The eligibility rule is isolated and unit-tested with valid asset lifecycle values.

- Asset dependency relationship creation now checks both `retired_at` and lifecycle status (`Retiré`/`Décommissionné`), not only the timestamp. This blocks relationships against inconsistent legacy records; tests cover both conditions.

### 12. Asset-risk association integrity

- New asset-risk links now reject lifecycle statuses `Retiré` and `Décommissionné`, as well as a non-null `retired_at` marker.
- Duplicate/constraint errors are handled specifically as `IntegrityError`; unrelated application/database exceptions are no longer disguised as HTTP 409.
- Unlink now verifies that both the asset and risk exist before looking up/removing the association, avoiding ambiguous missing-link responses for orphan IDs.
- Unit and API-level mock tests cover eligibility and missing-entity paths.
- **Remaining validation:** PostgreSQL constraint behavior, transaction rollback and route permission tests still need integration validation.

- API regression tests now exercise both rejected asset-risk link creation cases: retired lifecycle status and a non-null retirement marker, including assertions that no association is persisted.

### 13. Migration review: PostgreSQL downgrade guard

- A syntax defect was found in migration `0020_asset_reference_and_type_constraints.py`: its PL/pgSQL anonymous block used an invalid dollar-quote delimiter.
- Corrected the block to standard `DO $$ ... END $$;` syntax.
- Added a static regression test to ensure the malformed delimiter does not return.
- This is a static verification only. A PostgreSQL-backed Alembic upgrade/downgrade run remains required before the migration chain is considered production validated.

### 14. Supplier model/migration parity

- Added static checks confirming the partial unique index for open supplier access requests (`uq_supplier_access_requests_open_link`) is declared consistently in the model and migration, including its status predicate.
- Added parity checks for the unique monthly supplier-risk snapshot constraint.
- These checks protect against ORM metadata drift; PostgreSQL migration tests are still required for actual database behavior.

- Supplier assessment validation safeguards are now covered by endpoint regression tests: an assessor cannot validate their own assessment, and a high/critical assessment cannot receive an unconditional `Approuvé` decision. Both cases assert that the database transaction is not committed.

### 15. CI correction: UUID fixtures

- The new assessment-validation regression tests initially failed due to malformed UUID fixture strings (four hyphen-separated groups instead of the canonical five).
- Corrected the fixtures. This was a test-data defect, not an application defect.
- A new CI run is required to verify the fix.

### 16. Concurrent TPRM decisions

- Assessment validation and supplier access-request decisions now lock the target row with `SELECT ... FOR UPDATE` before checking its current lifecycle state.
- This prevents concurrent validators/approvers from both acting on the same pending record based on stale state.
- PostgreSQL-backed concurrency tests remain required to prove transaction behavior under simultaneous requests.

### 17. RBAC endpoint/matrix consistency

- Added a regression test that scans backend endpoint source files for literal `require_permission(module, action)` declarations and verifies every pair exists in the centralized `PERMISSIONS` matrix.
- This catches endpoints using an undeclared module/action that would otherwise fail closed unexpectedly.
- This is a consistency check, not a complete authorization proof: role-level behavior and routes protected by other mechanisms still require separate tests.

- The RBAC audit test itself initially had a malformed regex literal; CI caught the collection-time syntax error. The regex was simplified using a triple-quoted raw string and the fix is on the branch. Validation of that latest test revision is pending.

### 18. JWT reserved claims

- `create_access_token` accepted caller-provided extra claims that could override `sub`, `type`, timestamps, `jti`, or `role`.
- Hardened token creation to reject extra-claim overrides of all reserved claims, including role.
- Regression tests cover reserved claims and attempted role elevation.

### 19. Refresh-token lifecycle — remaining security gap

- Refresh endpoint validates token type/signature/expiry and current account eligibility; password changes invalidate older refresh tokens via `password_changed_at`.
- **Gap:** refresh tokens are not currently tracked server-side and are not rotated/revoked on use. A stolen token can be reused until expiry unless another account-level revocation condition applies.
- Recommended future implementation: persist refresh-token `jti` or a token-family identifier, atomically rotate on refresh, revoke the previous token, and support logout/revoke-all. Add concurrency and replay tests before production deployment.

- JWT hardening was adjusted after CI showed the internal `role` claim is legitimately used by pre-auth and access-token constructors. Reserved standard claims are blocked in the shared builder; `create_access_token` separately rejects caller-supplied role overrides while preserving the trusted role parameter.

### 20. Forced password-change workflow after MFA

- Fixed the MFA confirmation endpoint to return a typed `change_password_token` instead of issuing ordinary access/refresh tokens when `must_change_password` is set.
- Added a frontend change-password step that submits the token and only stores a normal session after successful password change.
- Initial MFA enrollment recovery codes are now included in this one-time response and displayed for secure saving before the user continues.
- Added token-type regression coverage.
- CI validation of these backend/frontend changes is pending.

- CI caught two implementation/test defects in this workflow (missing test import and Vue form closing tag); both were corrected in follow-up commits. Final combined CI evidence is pending.

- Added endpoint-level unit tests for the forced password-change response after MFA, including the initial enrollment path and one-time recovery-code delivery.


### 4. RBAC input normalization

- The permission evaluator now normalizes role, module, and action strings (trim + lowercase) before lookup.
- Unknown roles/modules/actions remain denied by default.
- Added focused tests for normalization and explicit deny-by-default behavior.
- Remaining work: endpoint-level authorization tests for all sensitive routes and ensure no endpoint bypasses the shared dependency.


### 21. Endpoint authorization coverage (AST-based)

- Added a backend test that parses endpoint modules and verifies each router endpoint outside authentication/profile modules declares an explicit authorization dependency (`require_permission`, `require_role`, or `get_current_user`).
- This complements the permission-matrix consistency test and catches endpoints that omit a backend authorization dependency entirely.
- The test is a structural guard, not a complete proof: route-level tests must still validate role outcomes, object-level authorization, and authentication flows. Authentication endpoints and profile/permissions endpoints are intentionally excluded because they use dedicated authentication semantics.


### 22. Refresh-token rotation and revocation

- Current refresh endpoint validates JWT signature/type/expiry and checks current account eligibility, role-sensitive MFA, lock state, forced password change, and password-change timestamp.
- **Residual risk:** refresh JWTs are stateless and not persisted server-side; successful refresh does not invalidate the presented token. Replay remains possible until expiry.
- Production-grade remediation should introduce a persisted refresh-token/session record keyed by `jti` (store a hash, not the raw token), atomic one-time rotation, family revocation on replay, logout/revoke-all, and tests for concurrent refresh and reuse.
- This requires a dedicated migration, model, endpoint transaction design, and frontend logout/session handling. It is intentionally not patched as a superficial endpoint change.


### 23. Frontend session-token storage review

- Access and refresh JWTs are currently stored in browser `localStorage` (`pgcc_access_token`, `pgcc_refresh_token`).
- The Axios interceptor performs automatic refresh and replaces both tokens, but the backend does not persist refresh-token sessions; rotation therefore does not revoke prior tokens.
- `localStorage` is readable by JavaScript and increases token-exfiltration impact from an XSS. Production architecture should evaluate HttpOnly/Secure/SameSite cookies (with CSRF protections), short-lived access tokens, server-side session/refresh-token hashes, atomic rotation, reuse detection, logout and revoke-all.
- Frontend logout currently removes local tokens only; it cannot revoke server-side refresh sessions until the session model/API exists.
- This is an architectural security gap, not a cosmetic frontend change; keep it as a Phase 0 release gate.


### 24. Persisted refresh-session implementation (initial backend slice)

- Added `refresh_token_sessions` persistence with SHA-256 hashes of JWT `jti` values (raw refresh tokens are not stored), expiry, revocation timestamp, and replacement hash.
- Refresh now locks the matching session row, validates ownership/expiry/revocation, revokes the old session, and persists the replacement in one transaction.
- Reuse of a revoked token triggers revocation of the user's active refresh sessions.
- Added logout endpoint to revoke the presented refresh session.
- Initial login after MFA enrollment and mandatory-password-change completion persist refresh sessions.
- Remaining: PostgreSQL concurrency integration tests, frontend logout integration, cookie/CSRF architecture decision, revoke-all endpoint, migration runtime validation.


### 25. Refresh-session index review

- Removed the redundant standalone index on `token_jti_hash`; its unique constraint already creates an index supporting exact-token lookup.
- Retained the compound active-session index and user/expiry indexes.
- Added a static migration regression check to guard against reintroducing the duplicate index.


### 26. Session revocation on password/account policy changes

- Password-change endpoint revokes all active persisted refresh sessions before issuing a new session.
- Refresh-policy denial (inactive, locked, mandatory password change, etc.) revokes active sessions before returning the denial.
- Added static regression checks. Runtime transactional/concurrency behavior still requires PostgreSQL integration tests.


### 27. Frontend refresh-queue regression

- The Axios refresh queue had a `.catch(reject)` callback referring to an undefined identifier, which could produce a secondary ReferenceError when a queued request failed.
- Removed the redundant catch so queued promises correctly propagate the refresh failure.
- CI/build validation for the fix is pending.


### 28. Frontend logout store reset order

- Auth store previously reset Pinia state before clearing localStorage; its state initializer could therefore reload the stale tokens into memory.
- Logout now clears persisted credential keys first, then resets the store, preventing credential resurrection in memory.
- Current-head frontend CI/build validation remains pending.


### 29. Authorization header cleanup on logout

- Both explicit logout and forced logout after refresh failure now clear Axios' default Authorization header in addition to persisted tokens.
- This avoids stale bearer credentials remaining attached to subsequent API requests in the same page lifecycle.
- Current-head validation pending.


### 30. Refresh-token expiry claim validation

- Session persistence now validates that JWT `exp` is numeric before converting it to a timestamp.
- Boolean values are explicitly rejected (`bool` subclasses `int` in Python); malformed signed claims cannot cause a persistence-path TypeError/KeyError.
- Added tests for missing, string, and boolean expiry values.


### 31. Serialize refresh with password-change revocation

- Refresh and forced password-change paths now acquire a row lock on the user before evaluating policy or revoking/creating sessions.
- This serializes the two operations, preventing a refresh transaction from creating a new session concurrently with password-change session revocation.
- Added static regression coverage for both lock paths. PostgreSQL concurrency integration test remains required.


### 32. Frontend multi-tab refresh behavior — known residual

- Backend rotation is single-use and detects refresh-token replay. Two browser tabs attempting refresh with the same token can therefore cause replay detection and revoke active refresh sessions.
- Current frontend refresh queue only coordinates requests within one tab. It does not yet coordinate refresh across browser tabs.
- This is documented as a residual usability/security integration issue for Phase 0; recommended next implementation is cross-tab refresh coordination (BroadcastChannel or Web Locks with a fallback) plus frontend tests before declaring auth stabilization complete.


### 33. Refresh-session model registration in development

- The development `Base.metadata.create_all()` lifecycle did not import `RefreshTokenSession`, so the new table could be omitted from fresh development schemas.
- Registered the model in the development startup import and added a static regression check.
- Production schema remains migration-managed; this does not replace PostgreSQL/Alembic runtime validation.


### 34. Refresh-session expiry timestamp range

- Numeric JWT `exp` values can still be outside Python's datetime range. Persistence now maps `OverflowError`, `OSError`, and `ValueError` during timestamp conversion to an invalid-refresh-token response.
- Added regression tests for extreme positive and negative numeric expiry values.


## Phase 0 follow-up — PostgreSQL refresh rotation and asset lifecycle (2026-11-23)

### Validation evidence
- Commit `987ebc60604854baba379a270f3d431e5735b179` has a successful Backend checks workflow.
- Workflow jobs observed: backend compile + unit tests, frontend build, and PostgreSQL integration.
- PostgreSQL job completed both Alembic migration application and refresh-token rotation integration test successfully.
- This validates the current CI test path only; it does not yet prove a clean Docker application startup, full API integration, or production deployment.

### Asset lifecycle code-level observations
- `PATCH /assets/{asset_id}` synchronizes `retired_at` when lifecycle_status is explicitly changed to Retiré or Décommissionné, and clears it for other explicit lifecycle states.
- `DELETE /assets/{asset_id}` is a logical retirement: it sets `retired_at` and lifecycle_status=Retiré, preserving records.
- New asset-risk links reject retired/decommissioned assets and require both asset:update and risks:update.
- New asset relationships lock both endpoint rows in deterministic UUID order, reject missing/retired endpoints, reject self-relations, and check dependency cycles for depends_on. Integrity errors are translated to HTTP 409.
- Impact computation traverses reverse depends_on edges; its query excludes retired endpoints. Supplier details in impact are permission-gated by suppliers:read_assets.

### Remaining targeted validation
- Add/confirm API tests for retirement markers across PATCH and DELETE, reactivation semantics, retired assets in list/export/impact, and retained historical links.
- Add graph tests for direct and transitive impact, cycle rejection, and concurrent edge creation.
- Confirm access-control matrix for assets read/export/update/delete and cross-module risk/supplier permissions with negative-role tests.
- Review the post-commit audit logging pattern for mutation endpoints: database mutation and audit record are currently separate operations in sampled asset endpoints, so failure behavior should be explicitly tested/documented.
- Verify supplier access links and authorization lifecycle (request, approve, review, expiry, revoke) against retired assets and archived/suspended suppliers.

Status: targeted code review recorded; additional runtime/API tests remain required before marking Cartography validated.


### Supplier-to-asset link lifecycle consistency — follow-up
- The supplier asset-link endpoint previously rejected retired/decommissioned assets based only on `lifecycle_status`, while access-request validation already checked both lifecycle status and `retired_at`.
- Reused the existing `_asset_allows_supplier_access` predicate in link creation so inconsistent records with `retired_at` set but status still `Actif` cannot acquire a new supplier relationship.
- Added a regression test for this inconsistent-marker case and normal active assets.
- CI validation is pending for this change.
