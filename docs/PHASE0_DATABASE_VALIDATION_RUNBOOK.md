# Phase 0 — Runbook de validation des migrations PostgreSQL

**Statut au 27/11/2026 :** la validation CI actuelle couvre la tête Alembic `0031_risk_action_restrict`, la base neuve, un upgrade hérité représentatif, le contrôle de dérive, un downgrade/upgrade ciblé et un dump/restore sur base jetable. Les sections historiques ci-dessous sont conservées comme journal de preuves datées ; elles ne décrivent pas toutes l'état courant. L'exercice de restauration sur infrastructure cible, WAL/PITR, RPO/RTO et sauvegardes chiffrées/offsite restent à exécuter.

## 1. Conditions de sécurité

- Utiliser une instance PostgreSQL jetable, isolée du SI et sans données réelles.
- Ne jamais tester baseline/stamp ou downgrade sur une base de production.
- Conserver les logs des commandes et la version du commit testée.
- Sauvegarder toute base de test avant les essais de baseline.
- Vérifier la configuration de connexion avant toute commande Alembic.

## 2. Validation d'une base neuve

Depuis `backend/`, avec un environnement Python configuré et `DATABASE_URL` pointant sur la base jetable:

```bash
alembic heads
alembic history --verbose
alembic upgrade head
alembic current
```

Résultat attendu:
- une seule tête de migration;
- historique sans révision manquante;
- upgrade terminé sans erreur;
- `alembic current` indique `0024_audit_outbox` (tête actuelle du dépôt).

Inspecter ensuite le schéma réel:
- tables et colonnes;
- PK/FK, contraintes CHECK, uniques;
- index;
- extension pgvector et types vectoriels;
- table `refresh_token_sessions`, unique JTI hash, FK utilisateur, index utilisateur/expiration et index de sessions actives;
- tables `audit_outbox` et `security_logs`, contrainte d'append-only et index des événements en attente;
- table `alembic_version`;
- concordance avec les modèles SQLAlchemy.

## 3. Vérification de baseline existante

La procédure `alembic stamp 0001_initial` ne crée ni ne corrige le schéma. Elle est réservée à une base dont l'équivalence avec le schéma attendu par le baseline a été vérifiée.

Avant de stamper:
1. identifier précisément la version applicative et l'origine de la base;
2. faire un backup et vérifier que sa restauration est possible;
3. comparer schema, indexes, contraintes, extensions et types avec une base neuve;
4. résoudre et documenter tout écart;
5. approuver la procédure par un responsable DB/application.

Après le stamp:
```bash
alembic upgrade head
alembic current
```

Ne pas exécuter cette procédure sur une base inconnue ou sans sauvegarde vérifiée.

## 4. Test de montée de version

Pour une révision antérieure représentative:
```bash
alembic upgrade <revision_cible>
alembic current
alembic upgrade head
alembic current
```

La révision source doit correspondre à un état de schéma réellement supporté. Les migrations de données, les contraintes et les éventuels verrouillages doivent être vérifiés.

## 5. Downgrade et récupération

Le downgrade de `0001_initial` est volontairement interdit car il pourrait supprimer toutes les tables. Les migrations ultérieures disposent de downgrades individuels, mais ceux-ci doivent être testés sur une base jetable et évalués pour les pertes de données.

La stratégie de récupération privilégiée en environnement réel est backup + restauration contrôlée, pas un downgrade improvisé.

## 6. Evidence historique à consigner (état au 24/11/2026, supersédé par les preuves plus récentes ci-dessous)

| Champ | Valeur |
|---|---|
| Commit SHA | PR merge commit 2bd0c01 (PR head 677c299) |
| PostgreSQL version | 16.16 (CI pgvector/pgvector:pg16) |
| Source revision | Empty database / baseline 0001_initial |
| Target revision | 0024_audit_outbox |
| Fresh DB upgrade | Pass — Alembic applied 0001 through 0024 |
| Schema comparison | Not run independently |
| Legacy baseline/stamp | Not applicable to this clean-database run |
| Upgrade from supported revision | Not run |
| Backup/restore rehearsal | Not run |
| Logs / artifact | GitHub Actions run 45491802074; PostgreSQL integration job 138791791724; 13 passed |
| Reviewer | Automated CI only; human review pending |
| Date | 2026-11-24 |

## 7. Limites actuelles

Le baseline `0001_initial` appelle `Base.metadata.create_all()` à partir d'un ensemble de modèles importés. Les migrations ultérieures actuelles vont jusqu'à `0024_audit_outbox`. Cette approche est transitoire et peut dépendre des imports et de la metadata au moment de l'exécution. La validation sur PostgreSQL est donc obligatoire; le test statique du graphe Alembic ne la remplace pas.

## Latest CI evidence — 2026-11-25

- Workflow 45568463812: PostgreSQL integration job passed (13 passed, 6 warnings) after Alembic migration to head; backend job passed (297 passed, 13 skipped, 8 warnings); frontend build passed.
- This run supersedes the prior RBAC test failure recorded for workflow 45491802074. The corrected test is now covered by a green backend job.
- Legacy-upgrade, downgrade, schema-drift and backup/restore rehearsals remain open.

## Compose smoke validation target — 2026-11-25

- Compose now uses the same PostgreSQL pgvector major version as CI (`pgvector/pgvector:pg16`).
- Vite proxy target is configurable; Docker Compose sets it to `http://backend:8000` so container-to-container requests do not resolve localhost to the frontend container.
- Frontend development container uses `npm ci` against the committed lockfile.
- GitHub Actions now has a Compose smoke job to validate configuration, build backend image, start PostgreSQL/backend/frontend, verify API health and assert the Vite `/api` proxy reaches the backend.
- The smoke job's actual result is pending; no stack startup success is claimed yet.

## Latest clean validation — workflow 45572713404 — 2026-11-25

- Backend: 303 passed, 13 skipped.
- PostgreSQL 16 clean database: migrations 0001 through 0024_audit_outbox applied; PostgreSQL integration suite 13 passed.
- Frontend: committed package lock installed with npm ci; npm audit reported 0 vulnerabilities; Vite 6.4.6 build passed.
- Docker Compose: full development stack startup, API health and frontend proxy smoke all passed.
- This validates a clean database upgrade to head, but does not replace legacy-upgrade, downgrade, schema-drift, backup/restore or production data migration rehearsal.

## Latest PostgreSQL evidence — workflow 45574715908 — 2026-11-25

- PostgreSQL integration suite: 15 passed.
- Fresh PostgreSQL 16 database migrated from baseline through Alembic head 0024_audit_outbox.
- Includes refresh-cookie rotation/replay, supplier lifecycle, asset relationship integrity, document/RAG delete/index race, document classification ACL, encrypted MFA secret persistence/startup validation, upload uniqueness, append-only security log and audit outbox.
- Legacy production revision upgrade, downgrade, schema drift comparison and backup/restore remain untested against the target environment.

## Intégrité SHA-256 des originaux — 2026-11-25

- Ajout du champ nullable `documents.file_sha256` et de la révision Alembic `0027_document_file_sha256`, chaînée après `0026_auth_rate_limit_buckets`.
- La migration calcule le SHA-256 des binaires historiques par lots bornés de 100 lignes et vérifie qu'aucun binaire existant ne reste sans empreinte de 64 caractères. Les lignes sans fichier original conservent une empreinte NULL.
- Les nouveaux uploads calculent et enregistrent l'empreinte SHA-256 au moment de la persistance.
- Le téléchargement recalcule l'empreinte et compare en temps constant ; il refuse le fichier avec HTTP 409 si l'empreinte manque ou ne correspond pas.
- Tests unitaires ajoutés pour empreinte correcte, altération du binaire et données manquantes ; test statique ajouté pour le chaînage et le backfill de migration.
- À valider en CI : upgrade PostgreSQL propre jusqu'à 0027, backfill sur documents historiques, rollback, et comportement HTTP du téléchargement en cas d'altération. Aucun résultat de test n'est présumé avant le workflow.


### Vérification PostgreSQL du backfill SHA-256

Le job d'intégration crée désormais, sur une base migrée jusqu'à `0024_audit_outbox`, un document historique contenant un binaire sans empreinte. Après migration vers `head`, il compare le SHA-256 persisté à l'empreinte calculée indépendamment par `sha256sum`. Il répète ensuite le contrôle après downgrade vers `0025_user_auth_version` puis nouvel upgrade vers `head`. Le test d'accès documentaire PostgreSQL altère aussi le binaire tout en conservant l'empreinte d'origine et attend HTTP 409 au téléchargement.


## Evidence consolidée — 27 novembre 2026

Les sections historiques ci-dessus décrivent les états observés à leurs dates respectives. Elles sont supersédées pour l'état actuel par les preuves suivantes :

- Workflow `45961991384`, commit code `ed0e2739d026c2b8192b9e7d9f529bfc06ef28ca`, PostgreSQL 16 : migration base neuve jusqu'à la tête Alembic, contrôle de dérive SQLAlchemy/PostgreSQL, upgrade depuis un schéma hérité, downgrade/upgrade de la contrainte de conservation des actions et sauvegarde/restauration PostgreSQL réussis.
- Suite PostgreSQL : **42 passed**. Elle couvre notamment sessions, graphe d'actifs, liens fournisseurs, intégrité des risques, conservation des actions, cycle de vie documentaire/RAG, ACL, unicité des uploads, journal append-only et outbox.
- Le scénario backup/restore est un test CI automatisé avec base jetable et dump restauré dans une base de test. Il ne constitue pas un exercice de restauration sur l'infrastructure cible ni une preuve de sauvegarde offsite/immutable.
- La tête Alembic effective doit être confirmée par `alembic heads` sur le commit testé avant toute exécution opérationnelle. Ne pas reprendre les références historiques `0024_audit_outbox` comme tête actuelle : les migrations `0025` à `0031` existent désormais.
- Restent à réaliser et consigner avec responsables : sauvegardes chiffrées et WAL/PITR, rétention et immutabilité/offsite, restauration sur environnement cible, mesures RPO/RTO, supervision/alertes et validation humaine de la procédure.


## État courant et limites opérationnelles — 27 novembre 2026

- Tête Alembic confirmée dans la CI sur le HEAD applicatif `1e93f80e3a31da782f2eac1865797ec25063dc88` : `0031_risk_action_restrict`.
- Workflow `45962418271` : 5/5 jobs réussis ; PostgreSQL 42 tests passés ; migration neuve, upgrade hérité représentatif, contrôle de dérive, downgrade/upgrade ciblé et dump/restore sur base jetable.
- Le temps de restauration CI affiché est de 0 seconde après arrondi à la seconde ; cette mesure n'est pas une estimation RTO exploitable.
- L'environnement CI utilise des données et secrets éphémères. Il ne démontre ni la protection des sauvegardes réelles, ni le transfert offsite, ni l'immutabilité, ni la continuité du WAL/PITR.
- Avant la mise en production : identifier la sauvegarde chiffrée de référence, confirmer rétention et clés, restaurer sur un environnement isolé représentatif, mesurer le RPO/RTO, vérifier l'intégrité applicative et faire approuver le procès-verbal par les responsables DBA, exploitation et sécurité.
