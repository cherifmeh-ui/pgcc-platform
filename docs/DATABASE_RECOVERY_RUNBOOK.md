# Runbook de validation des migrations et de récupération PostgreSQL

Statut : procédure de validation CI et aide opératoire ; ne remplace pas le plan de sauvegarde/continuité validé de la CTF.

## Objectifs

1. Vérifier le chemin de mise à niveau depuis la dernière révision historique supportée avant les nouvelles migrations Phase 0.
2. Vérifier le downgrade global de la tête courante vers 0025_user_auth_version, puis la remise à niveau jusqu'à la dernière révision ; ce parcours couvre aussi les migrations documentaires, fournisseur et risques.
3. Vérifier qu'un dump PostgreSQL complet peut être restauré dans une base neuve et que le numéro Alembic ainsi qu'une donnée témoin sont conservés.

## Contrôle de la migration initiale

La migration `0001_initial` utilise encore SQLAlchemy metadata pour créer les tables historiques, mais sa liste de tables est maintenant explicitement figée. Elle ne doit pas créer à l'avance les tables ajoutées par les révisions ultérieures (ISO evidence, vérifications d'actions, inventaire, fournisseurs, sessions, outbox ou limitation d'authentification). Les nouveaux modèles restent importés par `migrations/env.py` pour permettre à Alembic de comparer l'ensemble du schéma.

## Validation automatisée GitHub Actions

Le job PostgreSQL doit :

- appliquer `alembic upgrade head` sur une base vide ;
- créer une base séparée et exécuter `alembic upgrade 0024_audit_outbox`, puis `alembic upgrade head` ;
- vérifier `alembic downgrade 0025_user_auth_version`, puis `alembic upgrade head` ;
- vérifier les précontrôles de cohérence des migrations 0029_supplier_access_link_scope et 0031_risk_action_restrict ;
- insérer une ligne témoin non sensible dans `auth_rate_limit_buckets` ;
- créer un dump au format custom avec `pg_dump -Fc` ;
- restaurer avec `pg_restore --exit-on-error --no-owner --no-privileges` dans une base neuve ;
- vérifier la révision 0030_risk_integrity_constraints et la présence de la ligne témoin.

Le job journalise la durée de restauration. Cette validation prouve la procédure sur le PostgreSQL éphémère de CI ; elle ne prouve pas la restauration des sauvegardes de production, les permissions de stockage, le chiffrement, la rétention ni les RPO/RTO de l'entreprise.

## Procédure opératoire de référence

À exécuter uniquement sur un environnement de restauration isolé, jamais sur la base de production active :

1. Obtenir une sauvegarde chiffrée récente et vérifier son empreinte SHA-256 ainsi que sa provenance.
2. Créer une instance/base isolée avec une version PostgreSQL compatible et les extensions requises (dont pgvector).
3. Restaurer le dump avec `pg_restore --exit-on-error`, sans réattribuer les rôles de production.
4. Vérifier `alembic_version`, les contraintes/index essentiels, les tables critiques et un échantillon de données métier.
5. Exécuter les tests de cohérence et un contrôle applicatif en lecture seule.
6. Mesurer le temps total et consigner les écarts, erreurs et actions correctives.
7. Ne jamais rediriger l'application de production vers la base restaurée sans autorisation formelle et plan de bascule/retour arrière.

## Informations à compléter par l'exploitation

- Responsable de la sauvegarde et de la restauration.
- Emplacement, chiffrement, contrôle d'accès et rétention des sauvegardes.
- Fréquence des sauvegardes complètes/incrémentales et archivage WAL.
- RPO/RTO approuvés.
- Version PostgreSQL cible et procédure de mise à niveau majeure.
- Preuve de restauration périodique, horodatage, durée et validation métier.
- Procédure de rotation des secrets et clés MFA/JWT après incident.

## Critères de clôture

La Phase 0 ne peut pas considérer la récupération comme validée sur la seule base du smoke test CI. Une répétition sur l'environnement de préproduction ou de restauration de la CTF, avec sauvegarde chiffrée, preuve de restauration et RPO/RTO mesurés, reste obligatoire.


## Résultats de la validation CI — 2026-11-25

- Run `45586284593`, HEAD code `91ec0cc` : tous les jobs CI sont verts (backend 376 passed/26 skipped, PostgreSQL 26 passed, frontend et Compose réussis).
- Mise à niveau depuis `0024_audit_outbox`, downgrade `0026 -> 0025`, puis upgrade `head` réussis.
- `alembic check` : aucune opération de migration supplémentaire détectée.
- Dump custom et restauration dans une base neuve réussis ; la révision `0026_auth_rate_limit_buckets` et la donnée témoin sont présentes.
- Durée observée de restauration CI : 0 seconde à la précision de la mesure. Cette valeur ne doit pas être extrapolée à une base de production.
- La répétition sur une sauvegarde chiffrée réelle et la mesure RPO/RTO restent obligatoires.


## Validation étendue — migrations 0029 et 0030 — 26 novembre 2026

- 0029_supplier_access_link_scope ajoute une clé étrangère composite pour garantir que chaque demande d'accès fournisseur référence le même fournisseur et le même actif que son lien. Les lignes historiques incohérentes bloquent la migration avec un diagnostic.
- 0030_risk_integrity_constraints impose les bornes impact/vraisemblance 1–5, la cohérence score = impact × vraisemblance, une référence non vide et l'unicité de la référence sans distinction de casse ni espaces périphériques. Les données historiques incohérentes bloquent la migration ; aucune correction automatique n'est faite.
- Workflow 45883850756, HEAD 5ec9173335eb4c9292002436bfd73669c32dfe02 : 4/4 jobs réussis. Le job PostgreSQL a validé alembic upgrade head, alembic check, upgrade historique depuis 0024, downgrade vers 0025 puis upgrade head, sauvegarde/restauration et 40 tests PostgreSQL réussis.
- Durée observée de restauration CI : 0 seconde à la précision de la mesure. Ne pas extrapoler à une base de production.
- Le parcours de CI ne remplace toujours pas une restauration d'une sauvegarde chiffrée réelle avec archivage WAL et RPO/RTO approuvés.


## Conservation des actions liées aux risques — révision 0031

- La migration 0031 remplace la FK action_items.risk_id ON DELETE CASCADE par ON DELETE RESTRICT et supprime le cascade delete-orphan ORM.
- La CI simule une ancienne base avec CASCADE avant l'upgrade, vérifie le passage à RESTRICT, puis teste downgrade/upgrade.
- Un test PostgreSQL confirme qu'une suppression directe du risque avec une action liée est rejetée et que l'action est conservée.
- Workflow 45885458640 sur HEAD daf4296aef817e7812d55e23cbc55d90547736eb : 4/4 jobs réussis, 41 tests PostgreSQL réussis.
