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
- **Validation follow-up (27 Nov 2026):** the earlier open question is resolved in the current implementation. Access requests require an approved supplier; approvals re-check supplier eligibility; new asset links reject `Suspendu` and `Terminé`; status transitions to those states require active links to be terminated and open requests/approvals to be closed first. These checks use supplier/link/asset row locks. The PostgreSQL concurrency test `test_access_request_creation_and_link_termination_are_serialized` verifies that request creation and link termination cannot leave an inconsistent active authorization. The backend and PostgreSQL suites passed in workflow `45957879528` on code HEAD `a1d94d1`. Human review of the supplier policy and production authorization remains required.

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


### Impact analysis retirement consistency — follow-up
- Impact analysis previously filtered graph endpoints only by `retired_at IS NULL` and checked the source only by the marker. A lifecycle status of Retiré/Décommissionné without a marker (possible on creation/import or legacy rows) could therefore appear active.
- Introduced a shared retirement predicate treating lifecycle status and `retired_at` as authoritative, and applied both conditions to the source and graph query.
- Added a focused regression test for inconsistent lifecycle/marker states and risk-link eligibility.
- CI pending; runtime validation not yet claimed.


### Asset relationship error handling — follow-up
- The asset relationship creation endpoint previously converted every database exception into HTTP 409, masking operational failures (connection errors, timeouts, programming errors) as duplicate/conflict responses.
- Narrowed handling to SQLAlchemy `IntegrityError`, retaining rollback and conflict response for constraint violations. Unexpected exceptions now propagate to normal error handling rather than being misreported.
- CI validation pending.


### Relationship creation uses unified retirement predicate
- Relationship creation validation previously duplicated lifecycle and retirement-marker checks, rather than using the shared retirement predicate. It was functionally similar but could drift from other endpoints.
- Updated the helper to call `_asset_is_retired`, making lifecycle status and `retired_at` consistent across impact analysis, risk linking, supplier linking, and relationship creation.
- Added focused tests for missing endpoints, retired lifecycle states, and marker-only retirement.
- CI pending.


### Database error semantics — 2026-11-24

- Static review found broad `except Exception` handlers around asset create, update and CSV import commits. They converted infrastructure/programming failures into HTTP 409 business conflicts, hiding the real failure class from API clients and observability.
- The handlers now translate only SQLAlchemy `IntegrityError` into HTTP 409 and continue to roll back the failed transaction. Other exceptions propagate to normal server error handling.
- Added regression tests for create/update: integrity conflicts remain 409 while unexpected database errors are not misclassified.
- Validation evidence for the pre-fix HEAD `70e2bbf6bb57c462f8d320ed824bf8edd98bdacb`: Backend checks green (268 passed, 1 skipped), frontend build green, PostgreSQL migrations and refresh rotation integration test green. The corrective commit itself still requires CI validation.


### Asset relationship transaction safety — 2026-11-24

- Review confirmed that dependency-cycle detection is serialized with a PostgreSQL transaction advisory lock, endpoint asset rows are locked in deterministic order, and retired/missing endpoints are rejected. The database also enforces non-self relationships, allowed relationship types, uniqueness and RESTRICT foreign keys.
- Existing cycle tests exercised the graph helper, but not the route's transaction behavior. The create and delete relationship endpoints also lacked an explicit rollback/re-raise path for unexpected commit failures.
- Added explicit rollback/re-raise handling for unexpected exceptions in relationship create/delete, while retaining HTTP 409 mapping for create-time `IntegrityError`.
- Added API-level regression tests for create rollback, integrity conflict mapping, cycle rejection before insert, and delete rollback.
- These are mock-backed route tests. A concurrent PostgreSQL test that attempts two opposing dependency edges remains a required runtime proof; the advisory lock implementation is source-reviewed but not yet concurrency-tested at the relationship API level.


### Supplier API database error semantics — 2026-11-24

- Static review found seven supplier endpoint commit handlers (supplier-risk link, supplier-asset link, supplier create/update, monthly risk snapshot, and supplier contract create/update) that mapped every database exception to HTTP 409.
- Narrowed the conflict mapping to SQLAlchemy `IntegrityError`; unexpected database/runtime errors now roll back and propagate unchanged.
- Added an AST-based regression test that checks all seven handlers retain a specific integrity branch and that generic exception branches roll back and re-raise rather than returning HTTP 409.
- This is a source-level regression guard. Backend CI and PostgreSQL integration on the new HEAD are required before considering it validated.


### PostgreSQL concurrency test for dependency graph — 2026-11-24

- Added a real PostgreSQL integration test that concurrently submits opposite `depends_on` edges through the actual asset relationship endpoint.
- The expected outcome is exactly one successful edge and one HTTP 422 cycle rejection, with exactly one persisted relationship. This exercises the transaction-scoped advisory lock and cycle query together, rather than only testing the pure graph helper.
- Updated the PostgreSQL CI job to run this test alongside refresh-token rotation after Alembic upgrade.
- Validation is pending on the new HEAD; no concurrency result is claimed until the PostgreSQL job completes.


### CI evidence — supplier error handling and asset graph concurrency — 2026-11-24

- Supplier database error-handling regression suite passed in Backend checks run `45457457094`: **276 passed, 1 skipped**; frontend build and PostgreSQL migration/refresh-token job also passed.
- The first PostgreSQL graph-concurrency run exposed a test harness mapper-registration issue (`Risk.actions` referenced `ActionItem` before that model was imported). The integration test now explicitly imports the model before ORM use.
- Corrected PostgreSQL run on HEAD `306e966b72ff4c6b026fa130647a7c7282ca2ecb`, run `45457897057`: backend **276 passed, 2 skipped**, frontend build passed, Alembic upgrade passed, and PostgreSQL integration tests **2 passed** (refresh-token rotation plus concurrent opposing asset dependency edges).
- The concurrency scenario is now runtime-verified on PostgreSQL 16: exactly one of the two opposing dependency edges is persisted; the other request is rejected as a cycle.


### Asset-risk association versus risk deletion concurrency — 2026-11-24

- Static review identified a race: asset-risk linking checked that the risk existed without locking its row, while risk deletion checked association counts without locking the risk row. A concurrent link could pass its existence check while deletion passed its association count.
- Both paths now lock the same risk row with `SELECT ... FOR UPDATE` before eligibility/count checks and mutation. The existing `ON DELETE RESTRICT` foreign key remains the final database safeguard.
- Added a PostgreSQL integration test that races the real asset-risk link endpoint against the real risk-delete endpoint. The only valid outcomes are: link succeeds and delete returns 409, or delete succeeds and link returns 404.
- PostgreSQL CI run `45458697575` on HEAD `1a022b8e9f4197d77d940804d3448862e087b42c` passed: backend **277 passed, 3 skipped**, frontend build passed, Alembic upgrade passed, PostgreSQL integration **3 passed** (refresh rotation, dependency-edge concurrency, asset-risk link/delete concurrency).


### Supplier-risk references in risk deletion — 2026-11-24

- Further review found that `risks.delete_risk` checked action items and asset-risk links but omitted supplier-risk links, despite `supplier_risk_links.risk_id` having an `ON DELETE RESTRICT` foreign key.
- Risk deletion now returns an explicit HTTP 409 when supplier-risk links exist. Supplier-risk link creation also locks the Risk row, serializing it with risk deletion's row lock.
- Added a route regression test for the supplier-risk deletion conflict. The PostgreSQL FK remains a final safeguard; dedicated supplier-link/delete concurrency coverage remains a follow-up.


### Latest verified checkpoint — 2026-11-24

- HEAD `1a022b8e9f4197d77d940804d3448862e087b42c` has a fully successful CI run `45458697575`.
- PostgreSQL 16 migrations succeeded and all three integration tests passed: refresh-token rotation, opposing asset dependency-edge concurrency, and asset-risk link versus risk deletion.
- Backend suite: 277 passed, 3 skipped. Frontend build passed.


### Supplier access request versus link termination concurrency — 2026-11-24

- Review found a lifecycle race: access-request creation checked supplier, supplier-asset link and asset eligibility without row locks, while link termination checked for open access requests without locking the supplier/link rows. Concurrent requests could leave an active authorization attached to a terminated supplier-asset relationship.
- Access-request creation now locks Supplier, SupplierAssetLink and Asset rows before eligibility checks and insert. Link termination locks Supplier then SupplierAssetLink before checking open requests and changing status. Access decisions also lock Supplier, SupplierAssetLink and Asset after locking the request, serializing approval with supplier/link/asset lifecycle changes.
- Added a PostgreSQL concurrency test racing real access-request creation against real link termination. Only two outcomes are accepted: request created and termination rejected (409), or link terminated and request rejected (404).
- PostgreSQL CI validation is pending on the new HEAD.


### Document indexing versus source deletion — 2026-11-24

- Review found that RAG indexing read and later replaced document chunks without locking the source Document row, while document deletion read and deleted the source without coordinating with indexation. Concurrent operations could commit chunks for a deleted source or return a misleading successful index result after deletion.
- RAG indexing now locks the Document row for the full embedding/persistence transaction. Document deletion locks the same row before checking evidence references and removing chunks/source.
- Added a PostgreSQL integration test with a controlled embedding pause: deletion must block while indexation holds the row lock, then remove the document and its newly persisted chunks after indexation commits.
- CI validation is pending on the new HEAD.


### AI prompt injection — risk context submitted for executive rewrite — 2026-11-24

- Review of `AIService.rewrite_risk_for_executive` found that user-controlled risk fields were interpolated into the instruction prompt without an explicit untrusted-data boundary. A malicious description could attempt to override the system's requested behavior.
- The prompt now explicitly identifies risk JSON as untrusted data, instructs the model to ignore embedded directives and to retain the factual-only constraint. This is defense-in-depth; prompt wording is not a substitute for output validation or human review.
- Added focused unit tests verifying the untrusted-data boundary, preservation of the original risk content, and factual-only instructions. CI validation is pending on the new HEAD.


### Concurrent duplicate document uploads — 2026-11-24

- Review found a TOCTOU race in upload: the endpoint checked for an existing filename, then inserted without a database uniqueness guarantee. Two concurrent uploads could both pass the pre-check and create duplicate records.
- Added PostgreSQL partial unique expression index `uq_documents_filename_ci` on `lower(btrim(filename))`, with a migration preflight that fails explicitly if legacy duplicates exist. The model metadata declares the same index for schema consistency.
- Upload now performs a normalized pre-check and translates the database uniqueness conflict into HTTP 409 after rollback.
- Added migration integrity coverage and a PostgreSQL concurrency test that synchronizes two uploads after their pre-checks and expects exactly one 201 and one 409.
- CI validation pending on the new HEAD.


### CI validation addendum — 2026-11-24 — HEAD `526193721d68af4edd9c1cc4128a80999b0c6394`

- Backend: **280 passed, 6 skipped**, 9 warnings.
- PostgreSQL 16: **6 passed**, including Alembic upgrade through `0022_document_filename_unique`, supplier access/link lifecycle concurrency, document index/delete serialization and concurrent duplicate uploads.
- Frontend: build passed.
- The database log records the expected losing insert's unique-index violation during the duplicate-upload race; the endpoint translated it into HTTP 409, and the test confirmed one document persisted.
- These checks validate the listed CI paths only; document-level ACL policy, malware scanning/parser sandboxing, full deployment and audit durability remain open.


### Security audit log append-only protection — 2026-11-24

- Source review confirmed `log_action()` is best-effort and swallows persistence errors; the `security_logs` table had no SQL-level protection against UPDATE, DELETE or TRUNCATE.
- Added migration `0023_security_logs_append_only` with PostgreSQL triggers rejecting those mutation operations using SQLSTATE 55000. Inserts remain permitted.
- Added PostgreSQL integration coverage proving UPDATE and DELETE are rejected and the original row remains unchanged. The test rolls back its outer transaction and leaves no test record.
- Boundary: a database owner/superuser can still disable/drop triggers or alter the schema. This is append-only protection against ordinary application SQL, not cryptographic tamper-proof storage.
- Remaining control gap: `log_action()` still fails open; mutation handlers may succeed when audit persistence fails. A durable out-of-band sink or an explicitly designed transactional/fail-closed audit policy is still required before claiming audit completeness.
- CI validation pending on the new HEAD.


### Append-only audit guard CI result — 2026-11-24

- HEAD `0073b1f261acef6409237db70ff60ba6aae865ba`: backend **281 passed / 7 skipped**; PostgreSQL 16 **7 passed**; frontend build passed.
- Alembic successfully applied revision `0023_security_logs_append_only`.
- PostgreSQL integration confirmed UPDATE and DELETE against `security_logs` fail with SQLSTATE 55000 and the original row remains unchanged. The test rolls back its outer transaction.
- The trigger protects against ordinary SQL mutation; database owners/superusers remain privileged and can bypass it. Audit-write failure handling remains fail-open and is not considered resolved.


### Durable audit outbox — 2026-11-24

- Replaced the logger's swallow-and-return behavior with a durable PostgreSQL outbox. Each event is committed to `audit_outbox` before delivery to `security_logs`.
- Added a unique `security_logs.event_id` to make delivery idempotent. Outbox-to-log insertion and setting `delivered_at` occur in one transaction; row locking with `SKIP LOCKED` supports multiple application workers.
- Added an application lifespan worker that retries pending events every five seconds. A delivery failure leaves the outbox row pending and records the exception class/attempt count. An outbox persistence failure is surfaced to the caller rather than silently discarded.
- Added PostgreSQL coverage simulating a transient delivery failure, asserting the outbox remains durable, then replaying the event and verifying exactly one immutable log row.
- Boundary: if PostgreSQL is unavailable before the outbox commit, the application cannot durably queue the event; the error is surfaced. Because many business handlers currently call `log_action()` after their business commit, this is durable retry, not atomic coupling of the business mutation and audit record. That stronger invariant still requires targeted transaction-boundary refactoring.
- CI validation pending on the new HEAD.


### Durable audit outbox — CI verification on 2026-11-24

- Verified HEAD `15a95f136e7f3e42fcc75ad9313850f0d39ec74b`.
- Backend: **282 passed, 8 skipped**, 9 warnings.
- PostgreSQL 16: **8 passed**, including Alembic migration `0024_audit_outbox` and transient outbox delivery failure/replay. The test confirms the event remains pending after sink failure, then produces exactly one immutable log on retry.
- Frontend build passed.
- The first CI attempts exposed two overly literal static-test assertions (`CREATE TABLE` / `DROP TABLE` rather than SQLAlchemy Alembic operation calls). Both assertions were corrected to check `op.create_table(` and `op.drop_table(`; the final HEAD is green.
- Outbox delivery is durable after enqueue and idempotent. Existing business operations still commit before calling `log_action()`; this does not yet guarantee atomic coupling of business writes and audit outbox records.


### Transactional audit enqueue — first business slice — 2026-11-24

- Added `enqueue_audit_event(session, ...)`, which flushes an outbox row into a caller-owned SQLAlchemy transaction without committing.
- Refactored risk create, update and delete so their audit outbox rows are added before the business transaction commits. A rollback now removes both the business mutation and the audit event; a successful commit persists both.
- The existing `log_action()` API remains backward-compatible for call sites not yet migrated.
- Added PostgreSQL integration coverage for same-transaction commit and rollback behavior. The test is included in the existing outbox integration suite.
- Scope is intentionally limited to the risk CRUD vertical slice. Actions, documents, suppliers, assets and authentication still require migration to the same transaction boundary.
- CI validation pending.


### Transactional audit integration — Asset Cartography — 2026-11-24

- Migrated asset CSV import, asset create/update/retirement, asset relationship create/delete, and asset-risk link/unlink to enqueue audit events through the caller-owned SQLAlchemy session before the business commit.
- Added explicit `flush()` before enqueue where a newly generated asset/relationship/link identifier is included in the audit payload.
- Added/updated endpoint tests to verify audit enqueue receives the same session and is ordered between business flush and commit; relationship deletion verifies the audit metadata.
- Existing PostgreSQL concurrency tests still cover opposing dependency-edge creation and asset-risk link versus risk deletion. Their CI result after this change is pending.
- Export remains a separate read-side audit event; preview/list/graph endpoints do not mutate state.
- Supplier workflows, document/RAG workflows and authentication still need the same transactional migration.



### Cartography CI regression analysis — 2026-11-24

- Reviewed complete failing logs for run 45470003937 (commit 40020d5): frontend build passed; backend failed 4 tests and PostgreSQL integration failed 2 tests; migrations succeeded.
- Backend test fixtures were not updated for the new asynchronous audit outbox flush (missing AsyncMock for session.flush); the relationship-ordering test also exhausted its mocked execute results because it invoked the endpoint twice.
- PostgreSQL concurrency fixtures supplied MagicMock Request objects; the real audit payload then contained non-JSON-serializable mock values for client IP/user-agent. Replaced these with concrete Starlette Request instances in the integration tests.
- Follow-up test-only commits: 1067a1f, d2b45bf, df9e3b4. Validation of the latest commit is required before treating these fixes as accepted.
- No production endpoint behavior was changed in these follow-up commits. Supplier audit migration remains pending.


### Audit transaction-boundary recheck — 26 novembre 2026

- Revue statique du code courant : les opérations de mutation des fournisseurs utilisent désormais `enqueue_audit_event(db, ...)` après le `flush()` métier et avant le `commit()`. Le module `suppliers.py` n'appelle plus `log_action()` pour ces mutations ; l'événement d'audit et la modification fournisseur partagent la transaction SQLAlchemy.
- Documents : dépôt et suppression ajoutent leur événement d'audit avant le commit. L'indexation RAG ajoute également l'événement dans la transaction qui remplace les chunks et marque le document indexé.
- Authentification : la rotation des refresh tokens, la révocation des sessions sur changement de politique, la détection de rejeu, le logout et le changement de mot de passe utilisent un événement d'audit dans la transaction de session correspondante. Des appels de télémétrie d'authentification utilisent encore `log_action()` avec une transaction outbox séparée ; l'atomicité de ces événements avec les mises à jour d'état de connexion/échec doit être évaluée séparément.
- Preuve CI du HEAD précédent `c067628` : workflow `45840592943`, 4/4 jobs réussis (backend, PostgreSQL, frontend, Compose). Les tests PostgreSQL incluent la rotation concurrente, la détection de rejeu et le rollback si l'enqueue d'audit échoue.
- Cette revue corrige les notes historiques précédentes qui indiquaient encore que les workflows fournisseurs et certains flux documentaires n'étaient pas migrés. Elle ne clôt pas la revue complète de l'audit transactionnel.


### Cartographie — cohérence des relations et concurrence PostgreSQL — 26 novembre 2026

- Le modèle applique des clés étrangères `ON DELETE RESTRICT` pour les relations actif↔actif, actif↔risque et actif↔application ; les références de relations ne disparaissent donc pas silencieusement lors d'une suppression.
- La création des dépendances `depends_on` prend un verrou transactionnel PostgreSQL `pg_advisory_xact_lock` commun, puis verrouille les deux actifs dans l'ordre déterministe de leur identifiant avant de vérifier le cycle et d'insérer l'arête.
- Les tests PostgreSQL `test_asset_relationships_postgres.py` couvrent les deux créations simultanées de dépendances opposées (une seule direction acceptée) ainsi que la course entre création d'un lien actif-risque et suppression du risque. Les tests de cycle et d'état de retrait complètent ces contrôles.
- Le workflow `45840592943` sur le HEAD `c067628` a validé le job PostgreSQL et l'ensemble des 4 jobs. Le contrôle de parité modèle/migrations a également réussi.
- **Contrôle restant :** vérifier la couverture de concurrence pour toutes les autres mutations de relations et réaliser une revue opérationnelle de la stratégie de verrouillage sous charge. Les contraintes FK et les tests actuels ne valent pas preuve de charge en production.


### Authentification — invalidation des jetons de parcours et audit des échecs — 26 novembre 2026

- Les jetons temporaires de pré-authentification et de changement obligatoire du mot de passe portent maintenant le rôle normalisé et `auth_version`.
- Les endpoints de démarrage d'enrôlement MFA, de confirmation MFA et de changement obligatoire du mot de passe comparent ces claims à l'état utilisateur verrouillé en base. Un jeton ancien, un rôle divergent ou un claim de version absent est refusé en HTTP 401.
- Après activation initiale du MFA, le flush qui incrémente `auth_version` précède l'émission du jeton de changement de mot de passe. Le jeton est donc lié à la nouvelle version de sécurité.
- Les échecs de mot de passe et de MFA enregistrent désormais l'événement d'audit dans la même transaction que l'incrément du compteur d'échecs et, le cas échéant, le verrouillage du compte. Si l'outbox échoue, l'état d'échec est annulé plutôt que conservé sans audit.
- Tests ajoutés : claims de jetons normalisés/versionnés ; jetons périmés par version, rôle ou absence de claim sur les trois parcours ; ordre audit/commit et rollback en cas d'échec de l'outbox pour login et MFA.
- **Validation CI de cette révision en cours** au moment de la rédaction. La revue humaine du déploiement, du reverse-proxy et des paramètres de production reste requise.


### Validation CI des derniers contrôles d'authentification — 26 novembre 2026

- HEAD de code validé : `deb6ef52480e21672aa95a5981da040ef96cb8e4`.
- Workflow `45852812889` : **4/4 jobs réussis** (backend, PostgreSQL, frontend et Docker Compose).
- Backend : tests unitaires réussis, incluant les contrôles de claims des jetons temporaires et les rollbacks lorsque l'outbox échoue.
- PostgreSQL : **38 tests réussis**. Le nouveau test de concurrence MFA prouve qu'un code de récupération présenté simultanément par deux sessions ne peut être consommé qu'une seule fois ; une seule session de renouvellement active est créée et les deux tentatives sont auditées.
- PostgreSQL : migrations, contrôle de dérive, chemin de migration historique, downgrade/upgrade et restauration CI réussis.
- Docker Compose : extraction réelle via le parseur isolé, réseau interne, authentification, refus fermé à l'indisponibilité du parseur et verdicts ClamAV sain/EICAR réussis.
- Cette CI ne remplace pas l'exercice de restauration chiffrée dans l'environnement cible, la validation RPO/RTO, la revue du proxy et des seuils de rate limiting, ni la revue humaine finale.


### Déploiement de production et exploitation du rate limiting — 26 novembre 2026

- Ajout d'un profil distinct `docker-compose.production.yaml` : base PostgreSQL non publiée sur l'hôte, réseaux internes séparés pour DB, parseur et antivirus, backend sans port public ni montage de code, parseur durci, ClamAV seul autorisé à sortir pour ses mises à jour, frontend Vue compilé servi par Nginx non privilégié en TLS.
- Ajout de l'image frontend multi-stage, de la configuration Nginx TLS et des en-têtes de sécurité, du modèle `.env.production.example` et du guide `docs/PRODUCTION_DEPLOYMENT.md`.
- L'image backend embarque maintenant `alembic.ini` et les migrations pour permettre une migration explicite avant démarrage.
- Le proxy Nginx remplace `X-Forwarded-For` par l'adresse source observée ; le backend ne fait confiance qu'à son IP statique. Le backend n'est pas directement publié.
- Le CI valide la syntaxe du profil de production, construit l'image frontend et valide la configuration Nginx avec un certificat de test. **Le profil de production n'a pas encore été démarré avec des certificats et secrets réels dans l'environnement cible.**
- Les placeholders JWT et HMAC du rate limiter sont maintenant refusés hors développement. Les dépassements de seuil produisent un événement de journal structuré sans IP, compte ni clé HMAC ; les seuils et le fonctionnement sont documentés dans `docs/AUTH_RATE_LIMIT_OPERATIONS.md`.
- Workflow `45855717102` sur le HEAD `d52d5e637874671a9044adf903ca14fe953f566d` : **4/4 jobs réussis**. Backend, PostgreSQL, frontend et Compose sont verts ; le job Compose a aussi validé le profil de production, le build frontend et `nginx -t` avec certificat de test.
- Restent obligatoires : recette de déploiement réel, validation pare-feu/DNS/certificats, supervision et alertes, calibration des seuils, sauvegarde chiffrée/WAL, exercice de restauration RPO/RTO et revue humaine.


### Intégrité documentaire avant contexte IA — 26 novembre 2026

- Le filtre central `readable_context_documents` applique maintenant deux contrôles avant toute insertion de contenu dans le prompt : ACL documentaire existante et validation SHA-256 du binaire stocké.
- Un document dont le binaire manque, dont le condensat manque ou dont le binaire ne correspond plus au condensat est exclu du contexte IA, y compris pour les rôles privilégiés. Cette mesure évite de traiter un contenu documentaire altéré comme une source fiable.
- Tests ajoutés dans `backend/tests/test_ai_advanced_document_acl.py` : intégrité valide, binaire modifié et condensat absent ; les cas de classification et la limite de trois sources sont conservés.
- Validation CI de ce dernier changement en attente au moment de cette note. Vérifier aussi le comportement sur les documents historiques avant déploiement ; les documents sans binaire/condensat seront exclus du contexte jusqu'à régularisation contrôlée.


### Cohérence des autorisations fournisseurs et récupération RAG bornée — 26 novembre 2026

- Migration `0029_supplier_access_link_scope` : ajout d'une clé étrangère composite entre `supplier_access_requests(supplier_asset_link_id, supplier_id, asset_id)` et `supplier_asset_links(id, supplier_id, asset_id)`. La base interdit désormais toute demande qui associerait un lien à un autre fournisseur ou actif.
- Avant ajout de la contrainte, la migration détecte les lignes historiques orphelines ou incohérentes et interrompt l'opération avec un diagnostic explicite ; aucune correction automatique de données historiques n'est tentée.
- Test PostgreSQL dédié : les discordances fournisseur et actif sont refusées par la base ; une demande dont les trois identifiants correspondent est acceptée.
- Le contexte IA applique maintenant la portée ACL au niveau SQL avant la limite de résultats, puis conserve la vérification ACL et SHA-256 en défense en profondeur. La récupération est limitée à trois documents afin de borner le chargement des fichiers originaux nécessaires à la vérification d'intégrité.
- Tests unitaires : portée SQL des lecteurs, refus des rôles non autorisés, intégrité binaire altérée ou empreinte absente, classifications et plafond de trois sources.
- Workflow `45882921445` sur le HEAD `a6753c81dbdf1cb4b3c2fb4b8f24cef9dbb70a10` : **4/4 jobs réussis** (Backend, PostgreSQL, Frontend, Compose). Le job PostgreSQL valide le nouveau schéma, la migration historique, le downgrade/upgrade, la sauvegarde/restauration et **38 tests PostgreSQL réussis**. Le job Compose valide le profil de production, le frontend TLS, le backend, le parseur isolé, l'authentification du parseur, le mode fermé en cas d'indisponibilité et les verdicts ClamAV propre/EICAR.
- Cette validation est automatisée sur CI. Elle ne remplace pas une recette de production avec vrais secrets/certificats, une revue réseau/pare-feu, une sauvegarde chiffrée avec WAL, un exercice de restauration RPO/RTO en environnement cible et la revue humaine finale.


### Intégrité du score de risque et cohérence des références — 26 novembre 2026

- Migration 0030_risk_integrity_constraints ajoutée : contraintes PostgreSQL sur les bornes impact/vraisemblance, la formule du score, les références non vides et l'unicité insensible à la casse.
- Le précontrôle refuse les scores historiques incohérents, les références vides et les doublons normalisés ; aucune correction automatique.
- Test PostgreSQL dédié ajouté et explicitement intégré à la commande CI, avec le test de cohérence fournisseur-actif 0029.
- Workflow 45883850756 sur le HEAD exact 5ec9173335eb4c9292002436bfd73669c32dfe02 : 4/4 jobs réussis. Backend, PostgreSQL, Frontend et Compose sont verts ; PostgreSQL : 40 tests réussis, migrations, contrôle de dérive, downgrade/upgrade et sauvegarde/restauration validés.
- La Phase 0 reste ouverte : recette de production avec vrais secrets/certificats, revue réseau et proxy, supervision/alertes, sauvegarde chiffrée/WAL et exercice RPO/RTO en environnement cible, revue humaine et acceptation des risques résiduels.


### Conservation des plans d'action et intégrité du registre des risques — 26 novembre 2026

- Migration 0031_risk_action_restrict : le lien ActionItem.risk_id utilise désormais ON DELETE RESTRICT ; le cascade delete-orphan ORM est supprimé. Les actions correctives ne peuvent plus disparaître lors d'une suppression directe du risque.
- La CI simule l'ancien schéma ON DELETE CASCADE, vérifie la migration vers RESTRICT, le downgrade/upgrade et la conservation des lignes. Un test PostgreSQL confirme que le risque et son action restent présents après une tentative de suppression refusée.
- L'API de création des risques détecte les références normalisées en doublon et retourne HTTP 409 en cas de collision, y compris concurrente. Les mises à jour d'un risque verrouillent la ligne.
- Workflow 45885458640 sur le HEAD exact daf4296aef817e7812d55e23cbc55d90547736eb : 4/4 jobs réussis (Backend, PostgreSQL, Frontend, Compose), 41 tests PostgreSQL réussis.
- PR #1 reste ouverte, Draft et non fusionnée. La Phase 0 reste ouverte jusqu'à la recette de production avec vrais secrets/certificats, la validation réseau/pare-feu et supervision, la sauvegarde chiffrée/WAL et un exercice RPO/RTO en environnement cible, ainsi que la revue humaine et l'acceptation des risques résiduels.


### Bornage et robustesse de l'import CSV des actifs — 26 novembre 2026

- Limites d'entrée : 1 Mio et 5 000 lignes de données, lecture bornée à la taille maximale + 1 octet.
- Rejet des en-têtes vides ou dupliqués, des colonnes inconnues et des lignes contenant plus de cellules que l'en-tête.
- Validation groupée des identifiants d'applications : une seule requête SQL pour l'ensemble du fichier, au lieu d'une requête par ligne.
- Tests Backend ajoutés pour les limites de taille/lignes, les en-têtes ambigus, les colonnes supplémentaires et le traitement groupé.
- Workflow 45886912425 sur le HEAD 4e61f518b20cc82f4a3e6a6b85f59afb0cba8076 : 4/4 jobs réussis ; les 41 tests PostgreSQL restent verts.


### 27 November 2026 — consolidated asset/supplier lifecycle follow-up

- Asset retirement is now consistently represented by both `lifecycle_status` and `retired_at` on API creation, CSV import, PATCH and DELETE. Creation/import tests were added and validated by workflow `45957879528` on code HEAD `a1d94d1646dde266b5533d22a128c83e51a6c3b0` (Backend 460 passed/43 skipped; PostgreSQL 42 passed).
- Supplier access eligibility was re-read end-to-end: request creation requires an approved supplier and active link; approval revalidates supplier, link and asset; terminated/suspended suppliers cannot gain new asset scope; status changes and archival refuse unresolved active links or open access requests. Row locks serialize the lifecycle operations, and the PostgreSQL race test covers request creation versus link termination.
- The previous review note suggesting terminated supplier status was not checked is superseded by the implementation and test evidence above.
- The CI evidence does not replace a human policy review or production authorization review.

### 27 November 2026 — administrative account lifecycle and RBAC route review

- The account-management router exposes only list, detail, update, MFA reset and session-revocation operations; all five route dependencies require the backend `users:manage` permission, granted only to the normalized `admin` role.
- Mutating operations revalidate the acting administrator under row locks and compare the previously observed `auth_version`, preventing a stale administrator session from continuing after a concurrent demotion, deactivation or security-state change.
- The active MFA administrator set is locked in stable user-ID order before mutations that can reduce that set. The implementation prevents self-demotion/self-deactivation and prevents removing the final active MFA-enabled administrator.
- Role change, deactivation, MFA reset and explicit session revocation invalidate access tokens through `auth_version`, revoke refresh sessions transactionally and write an audit-outbox event in the same transaction. MFA reset also clears the MFA secret, confirmation timestamp and recovery-code hashes.
- Response models exclude password hashes, MFA secrets and recovery-code hashes. Update input rejects extra/sensitive fields and unknown roles.
- PostgreSQL integration coverage includes audit-failure rollback, stale-admin rejection, concurrent administrator demotion, access/refresh-token invalidation and session-revocation auditing. These tests passed in workflow `45957879528` (42 PostgreSQL tests).
- A route-signature inventory across the business API endpoint modules found authentication/authorization dependencies on every inspected route. The six auth endpoints are intentionally unauthenticated at the bearer layer and instead implement their own pre-authentication token, refresh-cookie, MFA and trusted-origin checks; those flows remain covered by the backend security suite.
- No new code defect was confirmed in this review pass. The review is static plus existing CI evidence; it is not a penetration test or a production authorization acceptance.


### 27 novembre 2026 — clôture des preuves automatisées Cartographie et environnement

- Revue des migrations `0007`, `0008`, `0010`, `0015`, `0029`, `0030` et `0031` : association Asset–Risk, cardinalité Asset–Application, restriction de suppression, relations fournisseur-actif, cohérence composite des demandes d'accès, invariants des scores de risque et conservation des plans d'action.
- Revue des endpoints : la création d'un lien Asset–Risk verrouille l'actif puis le risque ; la suppression d'un risque verrouille le risque avant de contrôler les actions et liens associés. Les contraintes FK restent la dernière défense d'intégrité. Les tests PostgreSQL couvrent les courses lien/suppression et les dépendances opposées.
- Workflow `45961991384` sur `ed0e273` : **5/5 jobs réussis** ; Backend 460 passed/43 skipped, PostgreSQL 42 passed, Frontend, Compose smoke et Production runtime smoke réussis.
- Compose a validé le parser isolé, l'authentification et le mode fail-closed, ainsi que ClamAV propre/EICAR. Le smoke de production a validé le démarrage avec secrets/certificat éphémères, migrations, TLS, proxy et isolation réseau.
- Workflow documentaire `45962009531` sur `e442ba4` : terminé avec succès. La note de validation a ensuite été mise à jour sur cette branche ; vérifier le workflow déclenché par cette dernière modification avant d'affirmer qu'elle est elle-même couverte.
- Les preuves restent des tests automatisés CI. La Phase 0 reste ouverte pour les sauvegardes chiffrées/WAL et immutables/offsite, l'exercice de restauration et RPO/RTO sur environnement cible, supervision/alertes, validation des secrets/certificats réels, revue humaine et acceptation formelle des risques résiduels.


## Mise à jour de maturité — 27 novembre 2026

Les constats historiques des sections initiales ci-dessus décrivent le code observé au 21 novembre et ne doivent plus être lus comme l'état actuel des modules concernés. Les revues ciblées ultérieures et les tests CI apportent les éléments suivants :

- **Authentification / sessions / MFA :** refresh token transporté par cookie HttpOnly, rotation persistée, détection de rejeu, révocation, invalidation par `auth_version`, MFA chiffré et contrôle d'origine ; tests unitaires et PostgreSQL. Les validations d'exploitation des secrets et de la topologie proxy restent à réaliser.
- **RBAC / administration :** les cinq routes d'administration des comptes exigent `users:manage`, réservé à admin ; revalidation de l'acteur sous verrou, protection du dernier administrateur MFA, révocation des sessions et audit transactionnel. Les tests PostgreSQL couvrent les mutations administratives et l'invalidation des tokens.
- **Rate limiting :** compteurs PostgreSQL partagés entre instances, identifiants HMAC, IP client issue du pair immédiat sauf proxy explicitement approuvé, mode fail-closed si persistance indisponible, Retry-After et nettoyage après 48 h. Les tests PostgreSQL couvrent 25 requêtes concurrentes depuis une IP et 12 IP distinctes ciblant un même compte. Les seuils, métriques, alertes et CIDR proxy restent à approuver par l'exploitation.
- **Documents / RAG :** ACL de classification et de portée propriétaire/département/role appliquée à la récupération SQL, contrôle d'empreinte SHA-256, parser isolé et antivirus ClamAV. Compose et production smoke valident l'extraction, le fail-closed parser et la détection EICAR. Les règles métier d'accès et la gestion opérationnelle des signatures antivirus restent à faire accepter.
- **Cartographie / risques / fournisseurs :** relations Asset–Risk, Asset–Application, Asset–Asset et Supplier–Asset revues ; contraintes de base, verrous et tests de concurrence/suppression ; retrait d'actifs cohérent avec `retired_at`. Les revues ciblées n'ont pas identifié de défaut applicatif nouveau confirmé dans le dernier passage.
- **Migrations PostgreSQL :** tête Alembic actuelle `0031_risk_action_restrict`. CI valide base neuve, upgrade depuis un schéma hérité représentatif, contrôle de dérive, downgrade/upgrade ciblé et dump/restore sur base jetable. Ne pas confondre cette preuve avec une restauration de sauvegarde de production ou un test WAL/PITR.
- **Environnement :** workflow `45962418271` sur le HEAD `1e93f80e3a31da782f2eac1865797ec25063dc88` terminé avec 5/5 jobs réussis : Backend 460 passed/43 skipped, PostgreSQL 42 passed, Frontend, Compose smoke et Production runtime smoke.

### Statut global

La maturité automatisée du socle s'est nettement améliorée, mais **Phase 0 reste ouverte**. Restent notamment : revue humaine exhaustive de la PR #1 (219 fichiers modifiés), exercice de restauration chiffrée/offsite avec WAL/PITR sur l'environnement cible, RPO/RTO mesurés et approuvés, validation des vrais secrets/certificats, revue de la topologie proxy/réseau, supervision/alertes et acceptation formelle des risques résiduels. Les phases fonctionnelles suivantes ne sont pas considérées comme démarrées dans ce jalon.


## Revue de maturité actualisée — 27 novembre 2026

Les tests ciblés les plus récents ajoutent des preuves d'exécution réelle
pour les modules Fournisseurs et Cartographie :

- **Fournisseurs / TPRM** : le cycle de vie des autorisations est exercé par
  HTTP avec JWT et PostgreSQL : création, approbation par un administrateur
  distinct, revue périodique, révocation, expiration et terminaison du lien.
  Les identités, états et événements d'audit sont relus après commit.
  Les tests HTTP vérifient aussi le refus des opérations de mutation par
  l'auditeur et l'absence d'écriture après refus RBAC.
- **Import CSV des actifs** : tests PostgreSQL d'import concurrent, de conflit
  entre prévalidation et insertion, et de rollback intégral d'un lot
  multi-lignes. La contrainte unique PostgreSQL reste la dernière défense
  contre les références concurrentes. Le workflow PostgreSQL inclut
  explicitement le fichier `test_asset_csv_import_postgres.py`.
- **Inventaire** : un parcours HTTP/JWT avec PostgreSQL compare les pages
  successives à l'export CSV pour des filtres multicritères et vérifie la
  stabilité de l'ordre et l'exclusion des actifs retirés.
- **Preuve CI** : workflow `46016290040` sur le code testé
  `e40286a02b3799793133732fa75d9721aa59a0d9`, **5/5 jobs réussis** ;
  Backend **542 passed / 61 skipped**, PostgreSQL **60 passed**, Frontend,
  Compose Smoke et Production Runtime Smoke réussis.

Cette maturité est démontrée par la CI sur base jetable et secrets/certificats
éphémères. Elle ne valide pas encore les règles d'unicité globale des
hostnames/numéros de série (à confirmer par la règle métier), la recette
d'exploitation réelle, les sauvegardes WAL/PITR hors site, les RPO/RTO, la
supervision, la revue humaine complète ni l'acceptation des risques résiduels.

**Statut : Phase 0 reste ouverte.** Aucun passage aux phases fonctionnelles
suivantes n'est déclaré par cette mise à jour.


### 28 novembre 2026 — checkpoint CI du HEAD 28de85a

- Les workflows Push `46139190920` et Pull Request `46139194452` ont terminé avec **5/5 jobs réussis chacun** sur `28de85a9f468b7e3f4408d159ef624eff906eba5`.
- Backend : **562 passed, 63 skipped, 1 warning** ; PostgreSQL Integration : **62 passed, 1 warning**. Frontend, Compose Smoke et Production Runtime Smoke sont réussis.
- Le parcours de confirmation CSV HTTP négatif vérifie désormais qu'une erreur de validation renvoie HTTP 422 sans révéler la valeur fournie et sans effectuer d'écriture.
- Les migrations de production sont exécutées jusqu'à `0031_risk_action_restrict` dans le smoke runtime CI ; le démarrage, health checks, TLS/proxy et parcours parser sont validés dans cet environnement éphémère.
- Cette preuve renforce la maturité automatisée. Elle ne remplace pas la revue humaine de sécurité, la recette avec secrets/certificats et réseau réels, la restauration d'une sauvegarde chiffrée/offsite avec RPO/RTO approuvés, ni l'acceptation des risques résiduels.

**Statut : Phase 0 reste ouverte pour les gates opérationnels et humains.**

### 28 novembre 2026 — correction initiale de la concurrence refresh

- Ajout d'un verrou Web Locks exclusif partagé entre les onglets pour sérialiser les appels de rotation du cookie refresh ; la détection backend des rejeux n'a pas été modifiée.
- Ajout de trois tests Node du composant de verrou et exécution de `npm test` dans le job Frontend.
- Le comportement est fail-closed sans Web Locks ; le support navigateur et la récupération après perte de réponse réseau restent à valider.
- Aucun test Playwright multi-pages ni test end-to-end du cookie HttpOnly n'est encore présent : maturité Auth améliorée mais non clôturée. Voir issue #7.
### Complément — restauration initiale de session

La revue du store Pinia a révélé un second point d'entrée : `restoreSession()` appelait directement `/auth/refresh`, en dehors de l'intercepteur de renouvellement. Cet appel est maintenant lui aussi enveloppé dans le même verrou Web Locks. Ainsi, les rotations automatiques après 401 et la restauration au chargement de l'application partagent le même verrou inter-onglets. Cette correction est incluse dans le commit `af88df5` ; sa CI doit être vérifiée séparément.


### Actualisation — authentification inter-onglets (28 novembre 2026)

- Un test Playwright Chromium a été ajouté : deux pages réelles du même contexte partagent un cookie HttpOnly et invoquent le module Web Locks de production simultanément.
- Le serveur HTTP est simulé par interception Playwright ; la preuve couvre la sérialisation inter-pages et la propagation du cookie tourné, pas l'intégration complète avec FastAPI/PostgreSQL.
- Le job CI installe Playwright/Chromium de façon éphémère, sans ajout au package.json/package-lock.
- Maturité Auth : contrôle navigateur en cours de validation CI ; gate toujours ouvert pour intégration avec backend réel, réponse réseau perdue après commit, fermeture/suspension d'onglet, compatibilité navigateurs et revue humaine. Voir issue #7.


### Validation CI — coordination refresh inter-onglets (28 novembre 2026)

Workflow PR `46148021953` sur le commit `48acdb2` : **5/5 jobs réussis**. Frontend : 3 tests Node + 1 test Playwright Chromium réussis, build Vite réussi, npm audit 0 vulnérabilité. Backend : 562 passed / 63 skipped. PostgreSQL : 62 passed. Compose et Production Runtime Smoke réussis.

Le test navigateur est multi-pages avec cookie HttpOnly partagé, mais le endpoint HTTP est simulé. Maturité Auth améliorée ; elle ne suffit pas à clôturer le module : intégration réelle FastAPI/PostgreSQL, réponse perdue après commit, cycle de vie des onglets, compatibilité navigateur et revue humaine restent à faire. Issue #7 reste ouverte.


### Auth — décision de conception sur le refresh ambigu (28/11/2026)

Le cas commit DB / réponse HTTP perdue est documenté. Un grace period sur ancien token seul est rejeté ; le protocole candidat exige un identifiant d'opération, un stockage chiffré temporaire du successeur et une coordination inter-onglets. Pas de modification backend sans revue sécurité/clé et tests end-to-end. Voir docs/REFRESH_ROTATION_RECOVERY_DESIGN.md. Maturité Auth non clôturée.


### Auth — extension de la matrice navigateurs (28 novembre 2026)

Le test Playwright de coordination inter-onglets est étendu à Chromium, Firefox et WebKit. Un scénario additionnel vérifie qu'un onglet en attente acquiert le verrou lorsque l'onglet propriétaire est fermé. Cette preuve reste circonscrite à l'API Web Locks avec endpoint HTTP simulé ; elle ne remplace pas l'intégration réelle FastAPI/PostgreSQL ni le scénario de réponse perdue après commit. Les résultats sont en attente du workflow déclenché sur le nouveau HEAD.


### Auth — intégration navigateur vers FastAPI/PostgreSQL (28 novembre 2026)

Un scénario Playwright réel a été ajouté : le job lance PostgreSQL, applique les migrations, prépare un compte/session jetable, démarre FastAPI et fait transiter les appels depuis le navigateur via le proxy Vite. Deux onglets doivent réussir deux rotations successives avec cookie HttpOnly partagé ; un second contexte rejoue ensuite l'ancien cookie et doit obtenir HTTP 401. La matrice est Chromium, Firefox et WebKit. Le token d'intégration est éphémère et masqué par GitHub Actions.

Cette preuve ne sera acquise qu'après réussite du workflow sur le HEAD exact. Le scénario commit réussi / réponse HTTP perdue reste non résolu volontairement : la détection de rejeu est conservée, sans grace period ni stockage du successeur avant revue de menace.

### Validation Auth bout-en-bout — 28 novembre 2026

Le workflow `46157868116` sur le commit `51667cf35c6189dec9db7adb8bd5ec4ccb06f8bd` est vert **5/5**. Les tests Playwright réels (6/6) tournent sur Chromium, Firefox et WebKit avec un backend FastAPI et une base PostgreSQL éphémère. Ils valident deux rotations inter-onglets avec cookie HttpOnly, la fermeture du détenteur du verrou, et le cas commit réussi / réponse perdue : le cookie périmé reste côté navigateur et sa répétition reçoit HTTP 401. Backend : 562 passed / 63 skipped ; PostgreSQL : 62 passed.

Décision de conception Phase 0 proposée : rester fail-closed et exiger une réauthentification après résultat ambigu plutôt que d'ajouter un store de refresh tokens de récupération chiffrés. La décision technique est couverte par test, mais attend la confirmation du propriétaire du service. La maturité automatisée Auth progresse ; la recette sur l'environnement cible et la revue humaine restent ouvertes.


### Refresh lock — timeout de requête (28 novembre 2026)

Le chemin de refresh automatique a été aligné sur le client Axios commun afin d'hériter de son timeout de 15 secondes. Le chemin de restauration initiale utilisait déjà ce client. Le timeout permet de terminer une requête réseau bloquée et de libérer le Web Lock lorsque l'event loop du navigateur fonctionne. Il ne constitue pas un TTL du verrou et ne garantit pas le déblocage pendant un gel complet du document par le système ; le test de suspension longue et la validation sur le parc réel restent ouverts.

CI sur le commit b351a243 : 5/5 jobs réussis ; le test navigateur réel contre FastAPI/PostgreSQL reste vert sur Chromium, Firefox et WebKit.


## Organisation du cycle de livraison — 28 novembre 2026

La validation humaine et la recette locale sont reportées à la fin du projet,
après clôture de tous les développements fonctionnels et techniques. Elles ne
sont pas des points d'attente pour les phases de développement.

Les équipes de développement poursuivent les tests automatisés (unitaires,
HTTP/JWT, PostgreSQL, navigateurs E2E, sécurité, migrations, build et smoke
tests) sur chaque HEAD candidat. Les preuves sont documentées avec leur SHA
exact et ne sont pas extrapolées à l'environnement CTF.

Les gates propres à la production (réseau/proxy/DNS/TLS, secrets/certificats,
supervision/alertes, sauvegardes chiffrées hors hôte, restauration, RPO/RTO,
acceptation des risques et revue humaine) seront regroupés dans la phase finale
d'installation locale et de recette. Le statut « non testé sur l'environnement
cible » reste explicite jusque-là. Le développement des phases fonctionnelles
peut avancer sans déclarer ces gates validés.


## État de progression actualisé — 28 novembre 2026

- Phase 0 : les gates techniques automatisés continuent d'être renforcés ; la recette humaine et les contrôles d'infrastructure CTF sont reportés à l'étape finale d'installation/acceptation.
- Phase 1 Cartographie : forte couverture backend/PostgreSQL et Playwright (24 tests sur trois moteurs) ; les derniers travaux portent sur le benchmark de volumétrie, la sémantique métier des relations, la matrice formelle des transitions et la revue finale de non-régression.
- Phase 2 Risques : le backlog détaillé est créé dans l'issue #8. Il porte sur les évaluations inhérentes/résiduelles, la version de méthodologie, les décisions de traitement, l'acceptation explicite et l'historique append-only.
- PR #1 reste Draft et non fusionnée ; main demeure inchangée.

Les phases suivantes seront développées dans l'ordre de la roadmap : Risques, TPRM, Conformité, Audits, Gouvernance/workflows, Pilotage/reporting, puis Automatisation/IA/production. L'installation locale et la recette humaine seront réalisées après la clôture de tous ces développements.