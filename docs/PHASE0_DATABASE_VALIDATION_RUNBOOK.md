# Phase 0 — Runbook de validation des migrations PostgreSQL

**Statut:** procédure préparatoire; aucune exécution PostgreSQL n'est attestée par ce document.

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
| Commit SHA | |
| PostgreSQL version | |
| Source revision | |
| Target revision | |
| Fresh DB upgrade | Pass/Fail |
| Schema comparison | Pass/Fail |
| Legacy baseline/stamp | Pass/Fail/Not applicable |
| Upgrade from supported revision | Pass/Fail |
| Backup/restore rehearsal | Pass/Fail |
| Logs / artifact | |
| Reviewer | |
| Date | |

## 7. Limites actuelles

Le baseline `0001_initial` appelle `Base.metadata.create_all()` à partir d'un ensemble de modèles importés. Les migrations ultérieures actuelles vont jusqu'à `0024_audit_outbox`. Cette approche est transitoire et peut dépendre des imports et de la metadata au moment de l'exécution. La validation sur PostgreSQL est donc obligatoire; le test statique du graphe Alembic ne la remplace pas.
