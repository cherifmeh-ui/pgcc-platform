# Phase 0 — Security review findings (2026-11-21)

This review is based on source inspection of the stabilization branch. It is not a penetration test or runtime validation.

## Refresh-token rotation and concurrency

### Implemented
- Persisted refresh sessions keyed by SHA-256 of JWT `jti`; raw JWT is not stored.
- Refresh flow locks the user row, then the refresh-session row, validates eligibility and expiry, creates the replacement session, revokes the previous session, and commits.
- Reuse of a revoked refresh token revokes the user's active refresh sessions.
- Logout revokes the presented session.
- Password-change flow revokes active refresh sessions.

### Remaining validation / risks
- PostgreSQL integration tests are required to prove locking behavior and atomicity.
- Two legitimate clients (e.g. tabs) refreshing the same token concurrently can cause the second request to be treated as replay and revoke the newly-created session. Client-side single-flight coordination and cross-tab coordination should be implemented or documented before auth gate closure.
- Review whether MFA-confirmation and forced-password-change flows persist session rows consistently and whether audit events are emitted after the transaction without misleading success records.
- A failed refresh should not accidentally leave partial session state; verify with DB tests.

## PostgreSQL migrations

- Revision 0021 creates refresh_token_sessions with FK cascade, unique JTI hash, expiry and user indexes.
- Static revision-graph checks exist.
- **Not verified:** full upgrade on a clean PostgreSQL database, upgrade from an existing supported deployment, downgrade behavior, SQL generated/executed against the target PostgreSQL version, and post-upgrade schema drift.

## Documents and RAG

### Positive controls observed
- Upload reads at most 10 MiB plus one byte.
- Filename is normalized and bounded; PDF/DOCX extensions and signatures are checked.
- Extraction is bounded and parser exceptions are not exposed.
- RAG chunk count is capped; embeddings are generated before replacing chunks; DB rollback preserves prior chunks on failure.
- Document routes use explicit permission dependencies.
- Deletion refuses documents referenced as ISO evidence and explicitly removes chunks.

### Risks requiring closure
- File parsing is not sandboxed and antivirus scanning is not integrated.
- Signature checks are shallow (PDF magic prefix and ZIP prefix for DOCX); deeper structural validation and archive-bomb protection need tests/controls.
- Document model has no classification/ACL fields. AI context endpoint checks the global `documents:read` permission, then queries PSSI documents and control-reference matches. This means authorization is role-level only; document-level classification/access policy is not implemented. Define a classification model and enforce it in list, preview, download, AI context retrieval, and vector search before production use.
- Indexing is synchronous and may block API workers; production should use a bounded worker/job mechanism.
- AI context query logs only successful responses; denial, provider failures, and query metadata should be considered for security/audit event coverage without logging full prompts or sensitive content.
- RAG/index failure paths and concurrent re-index/delete need integration tests.

## Audit logging

- Security log values are bounded; forwarded client IP is not trusted by default.
- Logger uses a separate session and is best-effort; failures are logged but do not fail the business action.
- This is not tamper-resistant audit storage. Production requires retention policy, restricted write/delete access, integrity protection or external sink, monitoring/alerting for logging failures, and coverage of high-risk events.

## API authorization

- RBAC matrix normalizes role/module/action and denies unknown values; unit tests cover normalization and default deny.
- AST coverage test verifies that non-auth endpoints declare a dependency, but it does not prove correct permission, object-level authorization, tenant/scope enforcement, or authorization inside service functions.
- Asset-risk linking performs additional cross-module permission checks, with API tests for unauthorized linking and unlinking.
- Required: broad role matrix tests for read/write/delete/export, object-level access tests, document/RAG classification tests, and checks for IDOR.
- Source review found the assets impact endpoint selectively omits linked risks/supplier access details based on module permissions; continue testing response field-level authorization to avoid leakage.

## Phase 0 exit gates

Do not close Phase 0 until evidence is attached for:
1. Current-head CI (backend and frontend).
2. PostgreSQL clean install + migration upgrade from supported baseline.
3. Refresh rotation/replay/logout/password-change concurrency tests on PostgreSQL.
4. Docker compose fresh stack health.
5. Endpoint permission and object-level authorization tests.
6. Document upload/download/delete and RAG retrieval authorization tests.
7. Audit event coverage and operational integrity decisions.
8. Full PR diff review and human approval.



## RBAC source review — additional evidence

- `role_has_permission` normalizes role/module/action and denies unknown roles/modules/actions.
- Unit tests cover normalization and default-deny behavior.
- Asset-risk endpoints perform explicit cross-module permission checks and API tests verify denial before DB access.
- The endpoint dependency AST test is structural only; it is not a substitute for route-level permission and object-authorization tests.


## Docker deployment review — source inspection

- Compose waits for PostgreSQL health before backend start, which is good.
- PostgreSQL image uses the floating `ankane/pgvector:latest` tag; pin a tested version/digest for reproducibility.
- Backend and frontend are development-oriented: hot-reload mounts, `ENVIRONMENT: development`, frontend `npm install` on startup, and direct published ports. A production profile should use immutable builds, lockfile-driven install, non-root runtime, secrets management, reverse proxy/TLS, restrictive network exposure, and health checks for backend/frontend.
- No Docker Compose runtime test has been executed in this review.


## Refresh session schema alignment

- Migration 0021 defines a database-side default for `created_at` (`now()`). The ORM model previously only had a Python-side default; it has now been aligned with `server_default=func.now()` so direct SQL inserts and ORM metadata agree.
- Added a model test asserting the server default exists. PostgreSQL integration migration/test is pending CI.


## Migration review — revision 0020 downgrade index mismatch

- Found a mismatch in revision `0020`: upgrade creates a unique index on `lower(btrim(reference))`, while downgrade recreated the earlier index on `lower(reference)`. This would leave schema behavior different from the prior revision after downgrade.
- Corrected downgrade to restore the exact pre-0020 index expression `lower(reference)`, preserving upgrade/downgrade symmetry.
- Added a static regression test asserting both index expressions and the guarded downgrade for cloud_resource values.
- Runtime PostgreSQL migration/downgrade validation is still required.


## PostgreSQL migration CI failure — baseline dependency

- The first PostgreSQL clean-upgrade CI run failed in revision `0001_initial`: SQLAlchemy metadata creation could not resolve `action_items.iso_assessment_id` to `iso_control_assessments.id` because the baseline did not import the assessment model.
- Corrected baseline imports to register `iso_control_assessment` before metadata `create_all`.
- Revision `0002_iso_assessments` now checks whether the table already exists and creates missing indexes, avoiding duplicate-table failure when the initial metadata baseline creates the table. This supports clean DB upgrade and previously migrated databases where 0002 originally created the table.
- CI must confirm this migration path. Downgrade semantics remain to be exercised against disposable PostgreSQL.


## Alembic baseline architecture caveat

- Revision `0001_initial` uses `Base.metadata.create_all()` and imports only a subset of models; later revisions create other tables and add columns/constraints.
- This hybrid baseline can overlap later revisions when models imported by the baseline already contain fields added in later migrations (notably ActionItem ISO links). Conditional checks are being added to make clean upgrades resilient.
- Downgrade symmetry is not fully guaranteed: because baseline metadata can include schema introduced by later revisions, downgrading a later revision may remove columns that were also created by baseline metadata. The baseline is intentionally non-downgradable, but the intermediate downgrade path still needs disposable-DB validation and a documented support policy.
- Long-term recommendation: replace metadata-driven baseline with explicit schema DDL or a carefully generated frozen baseline, and keep later revisions strictly additive/differential. Do not perform this redesign in the stabilization branch without a dedicated migration strategy.


## Root cause confirmed: baseline metadata is globally loaded

- `backend/migrations/env.py` imports every current model into `Base.metadata` before migrations run.
- Revision `0001_initial` calls `Base.metadata.create_all()` without an explicit historical table list. Therefore the baseline may create tables introduced by later revisions, producing duplicate-table/column/index/constraint failures when later revisions run.
- Conditional guards added to revisions 0002/0004/0006 mitigate specific overlaps but are not a complete migration-chain strategy.
- Recommended stabilization strategy: determine the exact legacy baseline schema and make revision 0001 create only that frozen schema (explicit table list or explicit DDL); then validate upgrade from 0001 through head and downgrade on a disposable PostgreSQL instance. Avoid broadly adding `IF NOT EXISTS` to all migrations because that can conceal schema drift and missing constraints.
- This is a blocking Phase 0 migration issue until clean upgrade and downgrade are demonstrated.

## Follow-up — transactional document/RAG and refresh-session audit — 2026-11-24

- Document upload and deletion now enqueue durable audit events in the same transaction as the document/chunk changes. RAG chunk replacement and the is_indexed flag now share the INDEX audit event transaction.
- Added PostgreSQL test coverage for index-vs-delete serialization, duplicate-upload uniqueness with a durable UPLOAD event, upload rollback on audit enqueue failure, and RAG chunk rollback on audit enqueue failure. These additions are committed but await fresh CI execution.
- Refresh rotation, replay detection, account-eligibility denial/session revocation and logout now enqueue audit-outbox events before the same transaction commits. The refresh endpoint uses the request context for actor metadata.
- Added PostgreSQL tests that exercise concurrent calls to the actual refresh endpoint with one old token, assert replay revocation and both audit events, and verify the old session remains active if audit enqueue fails. These tests are committed but await fresh CI execution.
- Residual: proactively revoke persisted sessions from account disable, role change, MFA reset and administrator security-reset workflows; add retention/cleanup for expired refresh sessions; monitor outbox delivery and test logout audit rollback.

## Migration head correction

- The current migration head is 0024_audit_outbox, not 0021_refresh_token_sessions. The database validation runbook now reflects revision 0024 and includes audit_outbox/security_logs checks.


## RBAC normalization hardening — 2026-11-24

- Access-token authentication now normalizes the persisted role before privileged-role MFA enforcement, matching the RBAC matrix's case/whitespace normalization.
- Access-token role claims are now required, must be non-empty strings, and must match the normalized database role. Missing, malformed or mismatched claims are rejected with 403.
- Added unit tests for uppercase/whitespace privileged-role MFA enforcement, missing/malformed/mismatched claims and normalized matching roles.
- Commits: 07c434f (implementation), 8149214 (tests). Fresh CI execution remains pending.


## Authentication transaction follow-up — 2026-11-25

- Password change now updates password state, revokes old refresh sessions, persists a replacement session and enqueues PASSWORD_CHANGED in one transaction with rollback on failure.
- MFA enrollment start now locks the user row and enqueues MFA_ENROLLMENT_STARTED in the same transaction as writing the pending enrollment secret.
- MFA completion events (initial enrollment/login and mandatory-password-change path) are now enqueued before commit with rollback on audit failure.
- Added focused unit tests for password-change audit ordering/rollback and MFA enrollment audit ordering/rollback. Added separate MFA enrollment test module.
- Remaining: administrator lifecycle paths for account/role/MFA reset and session revocation; encrypted MFA secret storage; rate limiting; CI execution on latest head.

## Warning cleanup and browser token finding — 2026-11-25

- Confirmed CI warning sources: unawaited AsyncMock for synchronous session.add in MFA test, SQLAlchemy stale child-row count during document/chunk delete cascade, pytest-asyncio unset fixture loop scope.
- Corrected test mock semantics, changed document deletion to bulk-delete chunks before parent, and added pytest.ini with explicit asyncio fixture loop scope. These changes await CI verification.
- Browser auth review confirmed access and refresh tokens are both stored in localStorage. Open critical remediation tracked in issue #4: HttpOnly refresh cookie, CSRF/Origin controls, explicit credentialed CORS and frontend bootstrap without localStorage refresh token.

## Refresh cookie and Compose hardening — 2026-11-25

- Implemented HttpOnly refresh cookie issuance/rotation/clearing and Origin allowlist validation. Removed refresh token from response model; frontend no longer persists access or refresh bearer credentials in localStorage.
- Added cookie unit tests and PostgreSQL cookie rotation/replay test. Fresh CI still pending.
- Fixed Compose Vite proxy target to use the backend service hostname inside Docker; pinned pgvector major to pg16 and switched dev frontend install to npm ci.
- Added Compose CI smoke job for config validation, backend image build, full development stack startup, API health and frontend proxy.
- Remaining: verify new CI, production same-site topology, review remaining Pydantic deprecation warnings.

## CI cookie test correction — 2026-11-25

- Run 45569880462: frontend passed; backend 303 passed/13 skipped with one failed direct-call test; PostgreSQL 12 passed/one failed direct-call test. Both failed because direct calls inherited Cookie(...) marker instead of None.
- Fixed with Annotated Cookie injection and explicit None default in commit 12efce0. The next workflow must validate this correction and the new Compose smoke job.

## Dependency security remediation — 2026-11-25

- npm audit in workflow 45572713404 reported zero vulnerabilities after upgrading Vite 5.4.21 to 6.4.6, esbuild 0.21.5 to 0.25.12, and follow-redirects 1.16.1 to 1.16.2.
- The previous Vite version fell in published vulnerable ranges; Vite 6.4.6 includes the fix for the critical dev-server RCE advisory. follow-redirects 1.16.2 is the patched version for the cross-realm sensitiveHeaders advisory.
- The committed package-lock.json was regenerated from the pinned package manifest, and the workflow now validates it with npm ci plus a zero-vulnerability npm audit gate.
- The 4-job workflow 45572713404 passed, including Docker Compose stack/proxy smoke.

## Document classification / viewer ACL — 2026-11-25

- Confirmed the document library previously exposed all records to every role with documents.read, including supplier contracts and audit reports; preview/download did not enforce per-document access.
- Implemented fail-closed classification derived from existing doc_type values (no schema migration): PSSI, PROCEDURE and REGLEMENT_INTERIEUR are INTERNAL; CONTRAT, AUDIT_REPORT and unknown/legacy types are RESTRICTED.
- Viewer may list, preview and download INTERNAL documents only. Admin, executive and auditor may read all classifications. Restricted direct-ID requests return 404 to avoid disclosing document existence.
- Listing is filtered in SQL for viewer; classification is returned by API and shown in the UI.
- Added unit tests for mapping, role matrix, list filtering, preview/download denials and positive internal preview; added PostgreSQL integration test for real list/preview/download behavior.
- RAG index trigger remains admin-only and there is currently no user-facing semantic retrieval endpoint. Any future retrieval endpoint must apply the same document classification predicate before returning chunks.
- Fresh CI is pending for these changes.

## MFA secret encryption at rest — 2026-11-25

- New MFA enrollment secrets are encrypted with Fernet before persistence; TOTP verification decrypts only in memory. Legacy plaintext values are lazily encrypted on first MFA verification.
- `MFA_ENCRYPTION_KEYS` supports a comma-separated key ring (first key active, later keys for decryption/rotation). It is required and validated in staging/production; development derives a deterministic development-only key from JWT_SECRET.
- Non-development startup now refuses to serve if any non-null `users.mfa_secret` remains plaintext. Added `backend/scripts/encrypt_mfa_secrets.py` with dry-run and key-rotation behavior, plus `docs/MFA_SECRET_ENCRYPTION_RUNBOOK.md`.
- Added tests for encrypted-at-rest storage, legacy conversion, key rotation, invalid ciphertext, production key configuration and startup gate. Fresh CI validation pending.
- Dependency `cryptography==50.0.2` added (PyPI release 2026-09-30).

## MFA secret encryption validation status — 2026-11-25

- Implemented Fernet ciphertext storage for new enrollments and decryption only for TOTP verification. Legacy plaintext is encrypted on first use; the operator script supports bulk migration and key rotation.
- Non-development configuration requires a valid `MFA_ENCRYPTION_KEYS` key ring. Startup checks all non-null secrets: plaintext or undecryptable ciphertext prevents startup; previous-key ciphertext is rotated to the active key.
- Added unit tests for encryption, legacy migration, rotation, invalid ciphertext, config and startup gate; added PostgreSQL persistence/startup verification test. Workflow 45574715908 is running; no result claimed yet.
- Production rollout requires running the dry-run and migration script, safeguarding the key, and reviewing key custody/recovery.

## Latest security validation — workflow 45574537534

- Document classification ACL and Fernet MFA encryption passed all automated tests.
- Backend 341 passed / 14 skipped; PostgreSQL integration 14 passed; frontend build and npm audit zero findings passed; Docker Compose full stack smoke passed.
- Viewer access is restricted to PSSI/procedures/regulations; contracts, audit reports and unknown legacy types are hidden from viewer. MFA secrets are encrypted at rest, with a non-development startup gate for plaintext or undecryptable secrets.
- Production deployment still requires key generation/backup, dry-run and execution of the legacy secret migration script against the actual target database.

## Final automated evidence for MFA encryption and document ACL — workflow 45574715908

- Backend: 342 passed / 15 skipped; PostgreSQL: 15 passed; frontend npm audit: 0 vulnerabilities; Vite 6.4.6 build passed; Compose smoke passed.
- MFA ciphertext-at-rest, legacy conversion, key rotation, managed key validation, non-development startup gate and PostgreSQL persistence are validated in CI.
- Document INTERNAL/RESTRICTED viewer ACL is validated by unit and PostgreSQL tests.
- Production deployment remains conditional on key generation/backup, legacy MFA migration script execution, same-site cookie topology review and human security approval.

## Revue complémentaire — intégrité des fichiers et pipeline documentaire — 2026-11-25

- Revue statique de `documents.py`, `document.py`, `document_extractor.py` et `rag_service.py` sur le HEAD de la PR `a117d14`.
- Le fichier original est stocké en binaire dans `documents.file_data`, mais le modèle ne comporte actuellement ni empreinte cryptographique persistée ni mécanisme de vérification d'intégrité au téléchargement. L'ajout d'un SHA-256 doit être accompagné d'une migration Alembic, d'une stratégie pour les documents historiques et de tests PostgreSQL ; aucune modification de schéma n'est faite sans validation du dernier numéro de révision.
- L'extraction PDF/DOCX applique des limites de taille, de pages, d'entrées ZIP et de texte, mais elle s'exécute dans le processus API. Ces limites ne constituent pas une sandbox : un service isolé avec limites CPU/mémoire, système de fichiers temporaire non privilégié et délais stricts reste requis.
- Le DOCX est contrôlé comme archive ZIP et la présence de `word/document.xml` est vérifiée ; cela ne remplace ni une analyse antivirus ni une désinfection CDR.
- Le service RAG génère les embeddings avant de remplacer les chunks, puis commit les chunks, le drapeau `is_indexed` et l'événement d'audit ensemble. Cette atomicité est utile, mais ne fournit pas à elle seule un cloisonnement d'accès lors d'une future recherche sémantique.
- Le déclenchement d'indexation est protégé par la permission RBAC `documents:update`. Toute évolution de la matrice de rôles doit préserver une restriction aux opérateurs explicitement autorisés ; la recherche RAG devra filtrer les documents selon l'utilisateur et leur classification avant même de sélectionner les chunks.
- Validation CI observée sur le HEAD PR `a117d14`, workflow `45613134288` : jobs backend, PostgreSQL, frontend et Compose terminés avec succès. Cette preuve couvre les tests automatisés du workflow, pas une sandbox antivirus ni une restauration de production.
- Décision : ne pas déclarer l'intégrité SHA-256, l'antivirus, la sandbox ou les ACL RAG comme implémentés. Les conserver comme portes de sortie Phase 0.


## Intégrité des binaires documentaires — implémentation en validation — 2026-11-25

- Le modèle Document expose désormais `file_sha256`; la migration `0027_document_file_sha256` ajoute la colonne et calcule les empreintes des binaires historiques par lots bornés. Les lignes sans binaire restent sans empreinte.
- Les nouveaux uploads calculent SHA-256 avant persistance. Le téléchargement recalcule et compare l'empreinte en temps constant ; une absence ou altération bloque la livraison (HTTP 409).
- Tests unitaires couvrent digest valide, binaire modifié et métadonnées manquantes ; un test statique vérifie le chaînage de migration et le backfill.
- À confirmer par CI PostgreSQL : upgrade propre jusqu'à 0027, backfill d'une ligne historique, contrôle du digest, downgrade sur base jetable. Les contrôles antivirus et sandbox restent absents et distincts de SHA-256.

- Le job PostgreSQL CI crée maintenant un document historique sans empreinte avant la migration 0027, vérifie le SHA-256 backfillé par comparaison indépendante, puis répète le contrôle après downgrade/re-upgrade. Le test d'accès PostgreSQL modifie le binaire sans modifier son digest et vérifie le blocage HTTP 409. Ces contrôles attendent encore un workflow vert sur le HEAD courant.


## Cartographie — cohérence des relations fournisseur/actif — 2026-11-25

- La revue de concurrence a identifié une asymétrie : la création d'une relation fournisseur-actif verrouillait le fournisseur mais pas l'actif cible, tandis que le retrait d'un actif verrouille l'actif. La création verrouille maintenant aussi l'actif, ce qui sérialise les deux opérations sur la même ligne.
- Le retrait d'un actif est désormais refusé (HTTP 409) tant qu'une relation fournisseur-actif est au statut `Actif`. Les relations doivent être terminées explicitement avant le retrait, afin de préserver la traçabilité de la dépendance fournisseur.
- Un test PostgreSQL vérifie qu'un actif avec relation fournisseur active ne peut pas être retiré et que son état reste inchangé.
- Le workflow `45625707397` sur le HEAD précédent `6f1c4bb` a terminé avec succès sur les quatre jobs (backend, PostgreSQL, frontend, Compose). Les modifications de cohérence ci-dessus ont été ajoutées après ce workflow et attendent leur propre validation CI.


## Test de concurrence — création de relation fournisseur/actif et retrait — 2026-11-25

- Le retrait d'un actif verrouille sa ligne avant de vérifier les relations fournisseur-actif actives.
- La création d'une relation verrouille le fournisseur puis l'actif cible avant de vérifier son cycle de vie et d'insérer la relation.
- Le test PostgreSQL concurrent exécute les deux opérations avec des sessions distinctes. Deux résultats seulement sont acceptés : (1) le lien est créé et le retrait est refusé ; ou (2) le retrait est validé et la création du lien est refusée. L'état final ne doit jamais contenir un actif retiré avec une relation fournisseur active.
- Le contrôle attend une exécution CI PostgreSQL verte sur le HEAD courant.


## Antivirus avant extraction documentaire — 2026-11-25

- Le parcours d'upload PDF/DOCX appelle désormais un adaptateur ClamAV via le protocole clamd INSTREAM **avant** tout parsing, extraction, requête de persistance ou indexation.
- Verdict propre : le parcours peut continuer. Verdict malware : HTTP 422 et aucune extraction/persistance. Scanner non configuré, inaccessible, expiré ou réponse invalide : HTTP 503, refus par défaut.
- La configuration ajoute `CLAMAV_HOST`, `CLAMAV_PORT` et `CLAMAV_TIMEOUT_SECONDS`. Hors développement, `CLAMAV_HOST` est obligatoire. Compose expose ces variables pour un service ClamAV externe ; aucun moteur antivirus factice n'est embarqué.
- Tests ajoutés : protocole INSTREAM (verdict propre/détection/erreur), blocage de l'upload en cas d'indisponibilité, refus d'un fichier détecté avant extraction, adaptation des tests PostgreSQL.
- Limite explicite : l'isolation du parseur PDF/DOCX dans un processus/conteneur à privilèges réduits et l'exploitation du service ClamAV en production restent à déployer et à vérifier. Les tests du protocole simulé ne prouvent pas l'intégration à un daemon réel.


## Contrôle d'accès au contexte IA documentaire — 2026-11-25

- Le endpoint `/ai-advanced/query-context` vérifiait la permission globale `documents:read`, mais sa requête documentaire ne réappliquait pas la politique de classification utilisée par les endpoints de consultation/téléchargement.
- Le contexte envoyé au modèle applique maintenant la fonction canonique `can_read_document` avant toute construction du prompt. Les utilisateurs `viewer` ne reçoivent que les documents classés INTERNAL ; les rôles privilégiés conservent les accès prévus par la politique documentaire.
- La requête récupère un ensemble candidat borné puis filtre les documents autorisés et limite les sources injectées dans le prompt à trois.
- Tests unitaires ajoutés pour vérifier l'exclusion des contrats/rapports d'audit pour les viewers, l'accès auditeur et la limite de sources.
- La portée de la politique reste basée sur les classifications et rôles existants. Les ACL fines par propriétaire/département nécessitent encore un modèle d'appartenance documentaire, une migration et des tests PostgreSQL dédiés.


## ACL documentaire par propriétaire et département — 2026-11-25

- Le modèle `documents` porte désormais `owner_id` (FK restrictive vers `users.id`) et `department` (instantané du département à l'upload), avec index dédiés.
- La migration `0028_document_acl` ajoute ces colonnes de façon idempotente et conserve les lignes historiques sans propriétaire/département.
- À l'upload, le propriétaire et le département sont enregistrés dans la même transaction que le document et son événement d'audit.
- Politique de lecture : admin/executive/auditor conservent l'accès privilégié ; le propriétaire peut lire son document ; un viewer peut lire les documents INTERNAL de son département ; les documents INTERNAL historiques sans métadonnées restent lisibles selon la politique historique ; un viewer ne peut pas lire un document restreint appartenant à un autre utilisateur.
- La liste, l'aperçu, le téléchargement et le contexte IA utilisent la même fonction de décision d'accès. Une FK RESTRICT empêche la suppression d'un utilisateur propriétaire sans réaffectation préalable.
- Tests unitaires et PostgreSQL ajoutés pour les accès propriétaire, département, autre département et document restreint.
- La migration et les tests doivent encore être validés sur le HEAD final par CI ; aucun résultat n'est présumé.


## Résolutions confirmées et état courant — 26 novembre 2026

Les constats historiques ci-dessus décrivent l'état au moment de leur rédaction. Les contrôles suivants ont depuis été implémentés et validés sur la CI :

- Parseur PDF/DOCX isolé sur réseau interne dédié, authentification obligatoire, refus fermé en cas d'indisponibilité, extraction DOCX réelle et tests de séparation réseau.
- ClamAV exécuté en CI avec base de signatures à jour : un fichier sain est accepté et le fichier de test EICAR est détecté.
- ACL documentaire appliquée dans la requête SQL avant la limite de résultats ; vérification ACL et SHA-256 en défense en profondeur avant inclusion dans le contexte IA ; récupération limitée à trois documents.
- Cohérence propriétaire/département du document appliquée sur liste, aperçu, téléchargement et contexte IA.
- Cohérence des demandes d'accès fournisseur imposée par FK composite (migration 0029) ; les demandes incohérentes sont rejetées par PostgreSQL.
- Intégrité du score de risque imposée par contraintes (migration 0030) ; référence non vide et unicité insensible à la casse ; précontrôle bloquant des données historiques incohérentes.
- Conservation des actions correctives garantie par FK RESTRICT (migration 0031), sans cascade ORM. La CI simule l'ancien CASCADE et prouve sa conversion.
- Profil Compose de production distinct, frontend TLS testé, backend/parser/DB/ClamAV non publiés, réseaux internes séparés et configuration Nginx validée.
- Workflow 45885458640, HEAD daf4296aef817e7812d55e23cbc55d90547736eb : 4/4 jobs réussis ; 41 tests PostgreSQL réussis ; migration, schéma, downgrade/upgrade, sauvegarde/restauration CI et tests antivirus réels réussis.

Restent à réaliser hors CI : déploiement de recette avec secrets et certificats réels, revue pare-feu/DNS/proxy, supervision et alertes, calibration des seuils, sauvegarde chiffrée et archivage WAL, restauration mesurée RPO/RTO, tests de charge/épuisement de ressources et revue indépendante. Ces points bloquent toujours la clôture de Phase 0.


### Bornage et robustesse de l'import CSV des actifs — 26 novembre 2026

- Limites d'entrée : 1 Mio et 5 000 lignes de données, lecture bornée à la taille maximale + 1 octet.
- Rejet des en-têtes vides ou dupliqués, des colonnes inconnues et des lignes contenant plus de cellules que l'en-tête.
- Validation groupée des identifiants d'applications : une seule requête SQL pour l'ensemble du fichier, au lieu d'une requête par ligne.
- Tests Backend ajoutés pour les limites de taille/lignes, les en-têtes ambigus, les colonnes supplémentaires et le traitement groupé.
- Workflow 45886912425 sur le HEAD 4e61f518b20cc82f4a3e6a6b85f59afb0cba8076 : 4/4 jobs réussis ; les 41 tests PostgreSQL restent verts.


## Revue complémentaire — 28 novembre 2026 (HEAD 9194419)

### Résultats CI confirmés

- Workflow PR `46140116019` sur `9194419b8017d8b8154a7c29bc6322fbfc8e4d90` : 5/5 jobs réussis.
- Backend : 562 passed, 63 skipped, 1 warning ; PostgreSQL : 62 passed, 1 warning.
- Compose et Production Runtime : parseur isolé et ClamAV opérationnels dans les environnements éphémères ; fichier sain accepté, EICAR détecté.
- PostgreSQL : migrations jusqu'à `0031_risk_action_restrict`, vérification de dérive, tests d'intégration et dump/restore CI réussis.

### Point de sécurité encore ouvert — renouvellement concurrent entre onglets

La file d'attente `isRefreshing/failedQueue` de `frontend/src/services/api.js` empêche plusieurs refresh concurrents dans une même instance JavaScript, mais ne coordonne pas les onglets du navigateur. Comme le refresh token est porté par un cookie HttpOnly partagé, deux onglets peuvent présenter le même token à quelques millisecondes d'intervalle. Le verrouillage PostgreSQL sérialise les requêtes ; la seconde peut alors être traitée comme une réutilisation/rejeu et révoquer la session nouvellement créée par la première.

**Action requise avant fermeture du gate Auth :** coordination inter-onglets (par exemple Web Locks avec stratégie de relecture de session/attente robuste) et tests multi-onglets automatisés ; vérifier aussi le comportement si un onglet est suspendu, si le détenteur du verrou disparaît ou si la réponse réseau est perdue après rotation. Ne pas affaiblir le mécanisme serveur de détection de rejeu.

Cette observation est une revue statique de source, pas une reproduction runtime. Elle doit être transformée en test navigateur reproductible avant toute affirmation de correction.

### Rappels d'exploitation

Le fichier `docker-compose.production.yaml` exige les secrets et clés nécessaires, mais la recette doit encore confirmer les valeurs réelles, les CIDR de proxy, les certificats montés, les règles réseau, les alertes ClamAV/rate-limit et les seuils sur le trafic réel. Les tests CI utilisent des secrets et ressources éphémères.


### Suivi dédié — concurrence de refresh entre onglets

Le point de revue statique est désormais suivi dans l'issue [#7 — Coordination du renouvellement de session entre onglets navigateur](https://github.com/cherifmeh-ui/pgcc-platform/issues/7). Cette issue est un gate Auth Phase 0 : elle reste ouverte jusqu'à l'implémentation, aux tests navigateur multi-onglets et à la preuve que le rejeu réel reste détecté.

### 28 novembre 2026 — mesure corrective initiale Web Locks

Une première correction a été ajoutée dans `frontend/src/services/refreshLock.js` et branchée dans `frontend/src/services/api.js` : toutes les rotations de refresh passent sous un verrou Web Locks exclusif nommé `pgcc-auth-refresh`, partagé par les onglets de même origine. La réponse HTTP est attendue à l'intérieur du verrou, de sorte que le cookie rafraîchi soit traité par le navigateur avant que l'onglet suivant n'entre dans la section critique.

Le verrou est fail-closed si `navigator.locks` n'est pas disponible. Cette stratégie évite de prétendre qu'un fallback localStorage à bail/expiration serait sûr face à un onglet suspendu ou à un détenteur disparu. Une erreur réseau dans la section critique remonte au traitement d'échec existant et provoque la reconnexion ; aucun retry automatique du même cookie n'est ajouté. Si le serveur a commité la rotation mais que la réponse n'a pas été reçue, l'état du cookie doit être vérifié par un test navigateur dédié : la présente correction ne prétend pas résoudre ce cas de manière démontrée.

Trois tests Node couvrent le verrou (sérialisation, API absente, libération après erreur) et `npm test` est ajouté à la CI frontend. **Limite importante :** pas encore de preuve Playwright multi-pages, ni de reproduction navigateur avec le vrai endpoint et cookie HttpOnly. Le risque est réduit par la sérialisation mais le gate reste ouvert jusqu'aux tests d'intégration multi-onglets et à la validation de la politique navigateurs supportés.
### Complément — restauration initiale de session

La revue du store Pinia a révélé un second point d'entrée : `restoreSession()` appelait directement `/auth/refresh`, en dehors de l'intercepteur de renouvellement. Cet appel est maintenant lui aussi enveloppé dans le même verrou Web Locks. Ainsi, les rotations automatiques après 401 et la restauration au chargement de l'application partagent le même verrou inter-onglets. Cette correction est incluse dans le commit `af88df5` ; sa CI doit être vérifiée séparément.


### Complément — test navigateur Chromium (28 novembre 2026)

Un test Playwright multi-pages a été ajouté sur le module de verrou de production. Deux pages Chromium partagent le même contexte/cookie HttpOnly et tentent simultanément une rotation ; l'endpoint HTTP est intercepté et simulé. Le test contrôle que la deuxième rotation reçoit le cookie mis à jour après libération du verrou.

Cette preuve est plus forte que le test unitaire du gestionnaire, mais elle reste **un test navigateur avec endpoint simulé**. Elle ne démontre pas encore l'intégration bout-en-bout avec le backend FastAPI/PostgreSQL. Les tests PostgreSQL du backend couvrent indépendamment la rotation concurrente et le rejeu. La CI du nouveau test doit être observée avant de qualifier ce contrôle de validé. Les scénarios réseau après commit et cycle de vie d'onglet restent ouverts.


### Résultat du test Chromium et CI — 28 novembre 2026

Le workflow PR `46148021953` sur `48acdb2` est vert **5/5**. Le job Frontend rapporte 3 tests Node réussis, 1 test Playwright Chromium multi-onglets réussi, build Vite réussi et npm audit à 0 vulnérabilité. Le backend rapporte 562 tests réussis / 63 ignorés ; PostgreSQL 62 tests réussis. Compose et Production Runtime Smoke sont réussis.

Le test Chromium utilise deux pages du même contexte et un cookie HttpOnly partagé ; l'endpoint est simulé. Il valide la sérialisation navigateur et la transmission du cookie renouvelé, mais ne prouve pas le parcours navigateur contre le vrai backend. Les tests PostgreSQL serveur couvrent indépendamment rotation concurrente et détection de rejeu.

**Risque résiduel à traiter :** si le backend commit la rotation mais que la réponse réseau et son Set-Cookie sont perdus, le client conserve l'ancien cookie. Le verrou inter-onglets ne peut pas, à lui seul, rendre cette opération idempotente. Ne pas désactiver la détection de rejeu pour contourner ce cas ; concevoir et tester explicitement le comportement serveur/client avant clôture du gate. Issue #7 reste ouverte.


### Analyse approfondie — perte de réponse après commit (28/11/2026)

Le serveur ne peut pas distinguer une répétition légitime après perte de Set-Cookie d'un rejeu malveillant sur la seule base de l'ancien refresh JWT. Un simple délai de grâce affaiblirait la détection de rejeu. Le stockage du successeur en clair est exclu ; une récupération idempotente impliquerait une réponse chiffrée temporaire, une clé dédiée gérée, un identifiant d'opération lié à l'ancien token et une coordination multi-onglets. Aucune modification backend n'a été faite avant revue de menace et de gestion des clés. Voir docs/REFRESH_ROTATION_RECOVERY_DESIGN.md.
