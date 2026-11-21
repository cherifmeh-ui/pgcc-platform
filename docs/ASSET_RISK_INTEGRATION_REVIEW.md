# Cartographie — Revue approfondie et intégration aux risques

**Date :** 21 novembre 2026  
**Branche revue :** `chore/phase0-stabilization`  
**Nature :** revue statique du dépôt — ne constitue pas une validation runtime/production.

## Résumé

Le socle Cartographie est présent : modèles `Asset` et `AssetRelationship`, migration `0006_asset_inventory`, API REST, RBAC, journalisation et interface Vue. La validation doit être poursuivie de manière incrémentale.

## Points validés par inspection

- Référence d'actif unique et identifiant UUID.
- Types, criticité, cycle de vie et niveaux CIA encadrés par contraintes.
- Champs d'inventaire technique (hostname, IP, FQDN, OS, version, constructeur, modèle, série).
- Association facultative au catalogue Applications via FK.
- Relations entre actifs avec FK, contrainte anti-auto-relation et unicité source/cible/type.
- Retrait logique au lieu de suppression physique via `retired_at`.
- Permissions backend `assets` et journalisation des opérations.
- API de listing filtré/paginé, CRUD et relations.

## Écarts et risques identifiés

### A-01 — Association Actif ↔ Risque manquante (priorité élevée)

Le modèle Asset ne possède aucune association explicite vers Risk. Il n'existe pas de table de liaison dédiée. L'intégration aux risques est donc un objectif documenté mais pas encore réalisé.

**Correction initiale implémentée :** association many-to-many explicite `asset_risk_links` avec FK, contexte de relation, date et auteur. API de liaison/déliaison et consultation depuis l'actif; endpoint inverse de consultation depuis le risque. RBAC et audit log appliqués aux mutations. Les risques et actifs restent propriétaires de leurs données. Tests de schéma ajoutés; tests d'intégration runtime encore requis.

### A-02 — Cardinalité Asset ↔ Application à revalider (priorité élevée)

La contrainte unique sur `assets.application_id` impose une cardinalité 1:1 lorsque ce champ est renseigné. Cela peut empêcher de cartographier plusieurs composants techniques d'une même application.

**Correction cible :** retirer la contrainte unique par migration additive; conserver la FK et l'association facultative. Aucun enregistrement existant ne doit être supprimé ou réécrit.

### A-03 — Validation runtime / CI à confirmer

Les tests présents couvrent des schémas et les permissions, mais la revue statique ne confirme pas les scénarios API PostgreSQL, les migrations upgrade/downgrade, les erreurs concurrentes ou la non-régression de l'ensemble des workflows.

**Actions :** tests d'intégration pour création/listing/liaison/déliaison, FK invalide, doublon, RBAC, journalisation, retrait logique et migration.

### A-04 — Relations de dépendance

La structure de relation est orientée et l'API permet de consulter les relations incidentes. Le MVP n'offre pas encore une analyse d'impact récursive, un graphe visuel ou une détection de cycles métier.

**Actions :** définir la sémantique de direction, ajouter tests, puis implémenter visualisation et analyse d'impact séparément.

### A-05 — Interface et inventaire

L'interface affiche un inventaire et des relations sous forme de liste. Elle ne fournit pas encore un graphe visuel, une pagination utilisateur complète ni les liens vers les risques.

## Stratégie de non-régression

1. Ne pas remplacer le catalogue Applications ni le registre Risques.
2. Ajouter les liaisons via tables d'association dédiées et migrations Alembic.
3. Préserver les routes existantes et leurs contrats de réponse.
4. Préserver les identifiants et données existants.
5. Toute nouvelle route doit appliquer les permissions serveur et journaliser les mutations.
6. Tester le comportement existant de CRUD actif, relations, risques et plans d'action.
7. Ne considérer la validation comme complète qu'après CI sur le HEAD courant et tests runtime de migration.

## Ordre de remédiation

1. Ajouter le modèle et la migration Asset ↔ Risk.
2. Ajouter API de consultation/liaison/déliaison et tests.
3. Retirer la cardinalité restrictive Asset ↔ Application via migration additive.
4. Renforcer les tests d'intégration.
5. Améliorer l'UI pour visualiser risques liés et dépendances.
6. Graphe visuel et analyse d'impact, en lot distinct.



## Interface d'intégration — implémentation initiale

- `AssetsView.vue` : panneau Relations affiche désormais les risques associés, contexte, liaison et dissociation (si permission update); le chargement est conditionné à la permission de lecture Risques.
- `RisksView.vue` : action dédiée permet d'afficher les actifs associés à un risque via l'endpoint inverse; affichage des caractéristiques essentielles et du contexte.
- Les fonctions existantes de CRUD actifs/risques, matrice, export CSV, assistant IA et plan d'action sont conservées.
- Les validations frontend build et CI sur le commit UI sont en cours.


## Revalidation — 21/11/2026

- CI sur commit `8e8c6fd` : backend job passed, frontend build failed due to a literal escaped newline inserted in `RisksView.vue`.
- Corrected the malformed sequence in commit `f7fffe5`; new CI was triggered.
- Security review identified that asset-side risk-link listing must require both `assets:read` and `risks:read`; this additional backend check was added in commit `74abe1d`.
- The inverse risk endpoint already requires `risks:read` and `assets:read`.
- Latest CI results for commits after these fixes are pending; no full non-regression claim until green.

- CI on `f7fffe5` exposed a second escaped-newline syntax error in `AssetsView.vue`; normalized the handler boundaries in `2b27479`. CI for this latest commit is pending.
