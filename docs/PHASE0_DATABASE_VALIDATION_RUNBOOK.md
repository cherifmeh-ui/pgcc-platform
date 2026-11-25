# Phase 0 — Runbook de validation des migrations PostgreSQL

**Statut:** exécution CI attestée pour une base neuve PostgreSQL 16.16 jusqu'à Alembic head 0024; les scénarios d'upgrade legacy, downgrade et restauration restent à exécuter.

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

## 6. Evidence à consigner

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