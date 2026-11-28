# Phase 1 — Cartographie du SI : état initial et plan d'exécution

**Date du checkpoint :** 27 novembre 2026  
**Branche de travail :** `chore/phase0-stabilization`  
**HEAD de départ Phase 1 :** `f4cce2ac69ee4f8f9beb58ab93fc089517a64459`  
**Statut :** Phase 1 en cours — intégrité PostgreSQL, RBAC HTTP, impact risques et parcours Playwright renforcés ; critères de sortie restants explicités ci-dessous.  
**Organisation de la recette :** aucune validation humaine n'est présumée ni attendue pendant le développement. La recette locale et les tests humains seront réalisés après clôture de tous les développements PGCC ; les gates propres à l'infrastructure CTF restent explicitement non validés jusque-là.

## 1. Validation du point de départ

- PR #1 : ouverte, Draft, non fusionnée ; base `main`, branche `chore/phase0-stabilization`.
- HEAD observé : `f4cce2a`.
- Workflow GitHub Actions `45963978294` : 5 jobs terminés avec succès :
  - backend ;
  - frontend ;
  - PostgreSQL integration ;
  - Compose smoke ;
  - production runtime smoke.
- Le job PostgreSQL exécute les migrations, contrôle le drift SQLAlchemy/PostgreSQL, vérifie upgrade/downgrade et backup/restore sur l'environnement CI jetable, puis lance les tests d'intégration.
- Le job runtime production vérifie le build, les migrations, le healthcheck, TLS/proxy/réseau, parser et ClamAV.
- Ces validations CI ne remplacent pas les revues et essais métier sur environnement cible.

## 2. État réel du module Cartographie constaté dans le dépôt

Le module est plus avancé qu'un simple MVP CRUD. Le code existant comprend déjà :

| Capacité | Éléments repérés | État de cette revue initiale |
|---|---|---|
| Référentiel Asset | modèle SQLAlchemy, schémas Pydantic dans le module API, API CRUD | Présent |
| Cycle de vie | statut, `retired_at`, retrait logique, contrôles de relations fournisseurs | Présent, transitions métier à tester exhaustivement |
| Applications | `application_id`, FK restrictive et vérification d'existence | Présent |
| Relations Asset↔Asset | types contrôlés, unicité, auto-lien interdit, prévention de cycles `depends_on` | Présent |
| Asset↔Risk | association dédiée, endpoints et contrôles de permissions | Présent |
| Analyse d'impact | parcours transitif `depends_on`, distances, risques et contexte fournisseur selon permissions | Présent |
| Graphe | endpoint de nœuds/arêtes et vue SVG | Présent |
| Qualité inventaire | complétude et dates de support | Présent |
| Import CSV | preview, validation, détection de doublons, confirmation transactionnelle | Présent |
| Pagination et filtres | endpoint serveur avec total et tri stable | Présent |
| Export CSV | filtres, permission dédiée, protection contre formules tableur et journalisation | Présent |
| Frontend | liste, formulaires, relations, impact, graphe, import/export, filtres et pagination | Présent |

Sources principales examinées :
- `backend/app/models/asset.py`
- `backend/app/api/v1/endpoints/assets.py`
- `backend/app/utils/rbac.py`
- `frontend/src/views/AssetsView.vue`
- `docs/ASSET_INVENTORY_IMPLEMENTATION.md`
- `docs/ARCHITECTURE_TARGET.md`
- `docs/TARGET_DATA_MODEL.md`
- `docs/MODULE_INTERACTIONS.md`

Cette présence fonctionnelle ne vaut pas encore validation complète de chaque scénario.

## 3. Écarts et points de contrôle prioritaires identifiés

### P1-CARTO-001 — Documentation du lien Application/Asset contradictoire

**Statut : résolu par revue documentaire — 28/11/2026.**

- La vérification de `docs/TARGET_DATA_MODEL.md` confirme désormais explicitement la relation Application 1:N Asset (une application peut référencer plusieurs actifs ; chaque actif référence au plus une application).
- `docs/ASSET_INVENTORY_IMPLEMENTATION.md`, `docs/ASSET_DATA_MODEL_REVIEW.md` et la migration `0008_asset_application_cardinality` concordent : la contrainte unique historique sur `assets.application_id` est supprimée, tandis que la FK restrictive est conservée.
- Le modèle SQLAlchemy actuel ne déclare aucune unicité sur `application_id`.
- Le test PostgreSQL existant `test_application_supports_multiple_assets_reassignment_and_restrictive_delete` dans `backend/tests/test_asset_lifecycle_postgres.py` couvre deux actifs liés à une même application, la réaffectation et la FK restrictive. Il est exécuté dans le job PostgreSQL Integration ; les workflows sur les HEAD e31b502 et suivants ont passé ce job.
- **Décision :** aucune migration supplémentaire ni conversion de données n'est requise pour cette cardinalité. La contradiction documentaire est résolue et le test de régression PostgreSQL est exécuté.

### P1-CARTO-002 — Responsabilités d'actifs encore textuelles

- Le modèle actuel stocke `owner`, `custodian` et `direction` comme chaînes de caractères.
- Le modèle cible mentionne `owner_user_id`, `owner_unit_id`, `custodian_user_id`.
- Les valeurs textuelles facilitent l'import initial, mais fragilisent la qualité, les affectations, les filtres et la traçabilité des changements de responsable.
- **Action :** inventorier les modèles User et organisation existants, les règles de périmètre et les données réelles avant toute migration. Étudier une transition additive avec références structurées, sans supprimer les champs historiques prématurément. Ne pas inventer de module OrganizationUnit s'il n'existe pas.

### P1-CARTO-003 — Endpoints graphe et qualité à évaluer en charge

- `GET /assets/graph` charge désormais uniquement les colonnes affichées pour les actifs et relations, avec un tri déterministe ; la réponse conserve son contrat JSON.
- `GET /assets/quality` utilise des agrégations SQL ; l'impact charge encore les relations de dépendance nécessaires au parcours transitif.
- **Action restante :** mesurer plans SQL, mémoire et latence avec une volumétrie synthétique représentative avant toute décision de pagination, plafond ou stratégie de graphe. L'optimisation de projection seule ne constitue pas un benchmark.

### P1-CARTO-004 — Cohérence des filtres entre liste, pagination et export

- `/assets/page` et `/assets/export.csv` reproduisent une logique de filtres similaire.
- La route historique `GET /assets/` conserve une sélection plus limitée de filtres pour compatibilité.
- **Action :** tester que les mêmes filtres produisent le même périmètre entre page et export ; centraliser les prédicats seulement si cela réduit réellement le risque de divergence, sans casser les paramètres historiques.

### P1-CARTO-005 — Validation de sécurité des données techniques

- Les actifs peuvent contenir IP, hostname, FQDN, numéro de série, localisation et informations de support.
- RBAC actuel : lecture Admin/Executive/Auditor ; écriture Admin ; export Admin/Auditor.
- **Action :** confirmer les audiences métier et les exigences de confidentialité, puis tester les refus API pour chaque rôle et les exports. Ne pas élargir les permissions par simple commodité.

### P1-CARTO-006 — Contrats de cycle de vie et intégrité inter-modules

- Le code protège le retrait contre certaines relations et demandes d'accès fournisseurs actives, et vérifie les applications associées.
- Les relations Asset↔Risk et Asset↔Asset ont des règles de retrait et des contraintes restrictives.
- **Action :** établir une matrice de scénarios pour actif actif/retiré/réactivé, risque lié, relation active, application associée, lien fournisseur, demande d'accès ouverte, import et opérations concurrentes. Vérifier les réponses API, les transactions, les audits et les FK PostgreSQL.

## 4. Séquence d'exécution Phase 1

### Jalon 1 — Audit fonctionnel et contrats (en cours)
- [x] Inventaire initial des fichiers et capacités.
- [x] Vérification du HEAD et de la CI sur le commit de démarrage.
- [ ] Revue complète des routes, schémas, tests et migrations du domaine.
- [ ] Matrice route × rôle × opération × résultat attendu.
- [ ] Matrice des transitions de cycle de vie et des dépendances inter-modules.
- [x] Réconciliation des documents de modèle et d'implémentation (Application 1:N Asset).

### Jalon 2 — Intégrité métier et responsabilités
- [ ] Tester et corriger les transitions de cycle de vie.
- [x] Valider Asset↔Application et Asset↔Risk sur PostgreSQL.
- [x] Valider Asset↔Asset, cycle, doublons et concurrence.
- [x] Valider les interactions fournisseurs et demandes d'accès par tests PostgreSQL de cycle de vie et de périmètre.
- [ ] Décider le modèle de responsabilité (User/Unité) sur la base des entités existantes.

### Jalon 3 — Inventaire et opérations de masse
- [x] Tests API/PostgreSQL pagination, filtres et équivalence export.
- [x] Tests d'import CSV : encodage, limites, doublons, concurrence, atomicité et audit.
- [ ] Vérification de l'absence de fuite de données dans les exports.
- [ ] Vérification de la performance sur volumétrie représentative.

### Jalon 4 — Graphe et analyse d'impact
- [x] Tests de parcours multi-niveaux, chemins multiples, actifs retirés et cycles (tests unitaires et PostgreSQL).
- [ ] Définir précisément la sémantique des relations orientées.
- [x] Valider la déduplication des risques et les agrégats sur l'actif source et les dépendants (test PostgreSQL ajouté).
- [x] Vérifier l'accès aux informations fournisseurs et risques selon permissions.
- [ ] Tester les limites de volumétrie et la stabilité de l'interface.

### Jalon 5 — Validation et clôture
- [ ] Tests unitaires, API et PostgreSQL sur les scénarios pertinents.
- [x] Tests frontend et parcours navigateur Playwright sur Chromium, Firefox et WebKit (15 tests sur le SHA 617e83f).
- [ ] Migrations fraîches et upgrade depuis schéma existant si changement DB.
- [ ] CI complète verte sur le HEAD candidat.
- [ ] Revue non-régression, documentation et critères de sortie Phase 1.

## 5. Principes non négociables

- Ne pas remplacer le module Applications existant par Asset.
- Ne pas créer de doublons applicatifs lors d'une conversion ou d'un import.
- Ne pas changer le schéma avant d'avoir examiné les migrations et les données.
- Conserver les références historiques et les FK restrictives appropriées.
- Ne pas calculer ou modifier automatiquement un score de risque à partir de la criticité d'un actif sans méthodologie approuvée.
- Appliquer les permissions côté backend, auditer les mutations sensibles et protéger les exports.
- Chaque correction doit avoir des tests de non-régression.
- Travailler uniquement sur `chore/phase0-stabilization` ; ne pas modifier `main`, ne pas fusionner ni fermer la PR #1 pendant ces travaux.

## 6. État du jalon

Phase 1 est **démarrée**, mais aucun sous-jalon fonctionnel n'est déclaré terminé sur la seule base de la présence de code. La première tranche est l'audit complet des contrats, des tests et des migrations, puis la correction des écarts confirmés.


## 7. Journal d'exécution — 27 novembre 2026

### Tranche RBAC — matrice Asset

- HEAD précédent contrôlé : `824cd9b38f76bca200ee56cb701ff12b76bb6c57`.
- Les deux workflows associés à ce HEAD sont terminés : 5/5 jobs réussis chacun (backend, frontend, PostgreSQL integration, Compose smoke et production runtime smoke).
- Constat : le test `test_assets_permissions.py` vérifiait quelques permissions via `role_has_permission`, mais ne vérifiait pas directement la dépendance FastAPI `require_permission` pour la matrice complète des rôles et actions.
- Correction : ajout d'un test paramétré appelant la dépendance réellement utilisée par les routes. Il couvre Admin, Executive, Auditor, Viewer et rôle inconnu, pour read/create/update/delete/export (22 combinaisons).
- Résultat attendu : les refus sont vérifiés au niveau de la dépendance FastAPI (HTTP 403), les accès autorisés retournent l'utilisateur courant.
- Limite : ce test vérifie la dépendance de sécurité, pas encore le parcours HTTP complet avec JWT, base PostgreSQL et routes montées. Une matrice d'intégration HTTP reste à réaliser.
- Commit : `549cf20a135862ae95c40a96306053f003b7f639` — `test(cartography): enforce asset API permission matrix`.
- Au moment de ce checkpoint, aucun workflow n'était encore publié pour ce nouveau SHA ; la validation CI de ce commit reste donc en attente.

### Prochaine tranche

1. Compléter les tests HTTP authentifiés des routes Asset, en couvrant au minimum lecture, mutation et export par rôle.
2. Revoir les routes de relation Asset↔Risk et les permissions croisées avec le module Risques.
3. Continuer la matrice cycle de vie et intégrité PostgreSQL avant toute évolution du schéma.


### Tranche import CSV — atomicité et cohérence audit

- HEAD précédent : `02920bb24df11e4fa7a2032b5ca06deb8c342a10`.
- Validation CI observée sur ce HEAD : les deux workflows (Push et PR) sont terminés avec succès, chacun avec 5/5 jobs réussis : backend, PostgreSQL integration, Compose smoke, frontend et production runtime smoke.
- Constat : les tests CSV couvraient la prévalidation, les limites, les doublons et le chemin nominal, mais ne verrouillaient pas explicitement les garanties de non-écriture en cas de prévalidation invalide, de conflit d'intégrité au flush, ni d'échec de l'audit outbox.
- Correction de couverture : ajout de trois tests dans `backend/tests/test_asset_csv_import_api.py` :
  - confirmation refusée si la prévalidation contient des erreurs, sans écriture ni commit ;
  - conflit d'intégrité pendant le flush : rollback et réponse HTTP 409 garantissant qu'aucun actif n'est importé ;
  - échec d'enqueue de l'événement d'audit : rollback et absence de commit.
- Aucun changement du comportement applicatif ni du schéma de base n'a été nécessaire : l'implémentation existante présente déjà un bloc transactionnel et un rollback explicite.
- Commit de tests : `c7971ac35d75258758d09a9cc6e6a136fb9c4764`.
- État CI au moment de cette note : workflow déclenché mais encore en attente. Ne pas considérer cette tranche validée avant examen des jobs du HEAD final.
- Portée : ces tests unitaires mockés verrouillent les branches de gestion d'erreur ; ils ne remplacent pas encore un test d'import CSV concurrent sur PostgreSQL réel.

### Prochaine tranche

1. Vérifier la CI complète sur le HEAD contenant les tests d'atomicité CSV.
2. Ajouter/renforcer la validation PostgreSQL d'import et de rollback si le pipeline d'intégration permet un test isolé sans pollution des données.
3. Construire une matrice de tests HTTP authentifiés pour les routes Asset (lecture, mutation, export) et les permissions croisées Asset/Risk.
4. Poursuivre les scénarios de cycle de vie et de concurrence.


### Tranche RBAC HTTP — routes Cartographie réellement exposées

- HEAD précédent contrôlé : `a8e2d69953512ee9862f18b980ba0f65810b90a0`.
- Les deux workflows associés à ce HEAD sont désormais terminés avec succès, chacun avec 5/5 jobs réussis : backend, frontend, PostgreSQL integration, Compose smoke et production runtime smoke.
- Le job backend a exécuté `486 passed, 43 skipped`. Le job PostgreSQL d'une exécution a exécuté `42 passed`, avec upgrade/downgrade des migrations et sauvegarde/restauration vérifiés.
- Constat : la matrice de permission testait directement la dépendance `require_permission`, mais pas les réponses HTTP des routes montées.
- Correction de couverture : ajout de `backend/tests/test_asset_http_authorization.py`, qui monte le routeur Asset dans une application FastAPI isolée et vérifie :
  - Viewer refusé sur le graphe, sans requête métier ;
  - Auditor autorisé sur le graphe ;
  - Auditor autorisé à exporter le CSV et événement d'audit déclenché ;
  - Executive et Viewer refusés sur l'export ;
  - Auditor refusé sur la création d'actif, sans écriture.
- Les tests injectent un utilisateur de test via la surcharge de dépendance `get_current_user` : ils valident le chemin HTTP et la politique RBAC des routes, mais ne constituent pas un test JWT réel bout en bout. L'authentification JWT, la cohérence du rôle et `auth_version` restent couvertes par les tests d'authentification dédiés.
- Commit : `4673d9d2c84bb21a1476012ce8d1bfe59ec4ba1f`.
- CI de ce commit : workflow Push déclenché ; résultat complet encore en attente au moment de la rédaction.

### Prochaine tranche

1. Vérifier les cinq jobs CI du commit HTTP RBAC.
2. Ajouter des tests HTTP authentifiés avec JWT si les fixtures d'intégration existantes permettent de réutiliser proprement le cycle de vie DB/test ; ne pas dupliquer un faux système d'authentification.
3. Auditer les filtres communs pagination/export, notamment la cohérence des champs et la protection des attributs sensibles dans les exports.
4. Compléter la matrice de cycle de vie et de concurrence PostgreSQL.


### Tranche filtres inventaire — pagination et export CSV

- Constat confirmé : `GET /assets/page` et `GET /assets/export.csv` maintenaient deux copies de la même logique de filtrage. Une évolution d'un endpoint pouvait donc créer une divergence entre les actifs affichés et les actifs exportés.
- Correction : centralisation dans `_build_asset_inventory_filters`, réutilisée par les deux endpoints. Les filtres partagés restent inchangés : recherche sur nom/référence/hostname/FQDN, type, criticité, cycle de vie, direction, responsable, classification, localisation et inclusion explicite des actifs retirés.
- Le tri stable, la pagination, le comptage, les colonnes CSV, la protection contre l'injection de formules et l'audit de l'export sont conservés.
- Tests ajoutés dans `backend/tests/test_asset_inventory_pagination_api.py` pour vérifier les prédicats SQL compilés, le nettoyage des paramètres textuels et le comportement explicite de `include_retired`.
- Commits : `fa948bea840f9a5ff1cbe6eb6e9e4aae1f7d317f` (centralisation), `8a1602449431581d690aef4e3317daea078d8fe9` (restauration/validation de la route paginée après revue du diff), `40c97afa3826ff1751a7605324a9dc40ffaa9af9` (tests).
- Revue statique du HEAD `40c97afa3826ff1751a7605324a9dc40ffaa9af9` : une seule définition du helper, une seule définition de chaque endpoint pagination/export ; l'export et la pagination appellent le helper commun.
- CI : deux workflows ont été déclenchés pour le HEAD de tests ; ils sont en cours au moment de cette note. Aucun résultat de test n'est déclaré avant la fin des jobs.
- Limite conservée : les tests de pagination restent en partie mockés ; ils ne remplacent pas une validation de cohérence sur une base PostgreSQL avec jeu de données réel et filtres combinés.

### Contrôle de confidentialité de l'export — décision

- Le CSV actuel contient notamment hostname, IP, FQDN, numéro de série et informations d'exploitation.
- Ces champs sont des données d'inventaire sensibles, mais nécessaires à certains usages d'audit technique. Les retirer sans validation métier réduirait la valeur opérationnelle de l'export ; les conserver ne doit pas être interprété comme une autorisation générale de diffusion.
- Décision provisoire : ne pas modifier les colonnes dans cette tranche. Conserver le contrôle RBAC `assets:export`, la journalisation de chaque export et le traitement anti-formule. Ajouter comme gate métier une validation formelle des profils autorisés, des destinataires, du stockage et de la durée de conservation des fichiers exportés. Une éventuelle séparation entre export standard et export technique sensible doit être décidée avec les responsables métier/sécurité avant migration de permissions.


### Correction CI — helper de filtres et tests SQL

- Échec CI observé sur le commit `40c97afa3826ff1751a7605324a9dc40ffaa9af9` : 2 tests échouaient, 492 passaient et 43 étaient ignorés.
- Cause 1 : le dialecte PostgreSQL SQLAlchemy échappe les caractères `%` dans les chaînes compilées avec `literal_binds`. Le prédicat exécuté utilisait bien le motif `%valeur%`; l'assertion de test attendait une représentation non échappée. Le test normalise désormais les doubles `%%` de la représentation compilée avant comparaison.
- Cause 2 : le contrôle AST des endpoints considère les fonctions d'un module `endpoints` comme des routes candidates. Le helper de requête a donc été déplacé dans `app/services/asset_inventory.py`, puis importé par les deux endpoints. Cela sépare la construction des prédicats SQL de la couche HTTP et évite de fausser le contrôle d'autorisation.
- Correctifs : `ffd22a6e2edac348f37ea7f785efe7760488c487` (service), `9b7f51fc8a8fb76f29bd295e418ac1dd101f5718` (endpoints), `8e129f68fb0449ec603e2f31562131b02c5d4d85` (tests).
- Ces corrections ne modifient pas les règles de filtrage attendues. Le nouveau HEAD doit repasser les workflows complets avant validation de la tranche.


- Revue complémentaire avant relance CI : suppression d'un décorateur `GET /page` dupliqué introduit lors de l'extraction, et correction du second test `include_retired` pour importer le helper depuis le service dédié.
- Commits de correction supplémentaires : `4868e7823623eff326ea936714654a254ceda382` et `ad29b3646cd9dcbc2cd6b9b53c0951c67f9f33a6`.
- Revue statique du HEAD : un seul décorateur et une seule fonction `list_assets_page`, deux appels au service partagé (pagination et export), aucun import résiduel de l'ancien helper dans les tests.
- Les nouveaux workflows du HEAD sont en file d'attente GitHub Actions ; la validation reste ouverte.


### Tranche cycle de vie — invariants métier et PostgreSQL

- Lecture des tests PostgreSQL existants : le pipeline d'intégration sur le HEAD `29570c68925498f3a9e905f2e63b75d89fd02312` exécute les tests de cycle de vie et de relations ; le job PostgreSQL a terminé avec `42 passed`.
- Les scénarios déjà couverts incluent retrait et audit atomiques, rollback si l'audit échoue, réactivation et rollback, blocage du retrait en présence d'autorisations/demandes fournisseur ou de relations fournisseur actives, concurrence création de relation fournisseur/retrait, et concurrence de deux arêtes de dépendance opposées.
- Nouvelle couverture unitaire indépendante de PostgreSQL : `backend/tests/test_asset_lifecycle_rules.py`. Elle formalise la cohérence entre `lifecycle_status` et `retired_at`, la génération/préservation/effacement du marqueur, le caractère autoritatif de chacun des deux champs et l'éligibilité des deux extrémités d'une relation.
- Commit : `e5f80b2ee19c8cc472bdc6652a46a736e902fcce`.
- Revue du code : les opérations de retrait et de modification verrouillent la ligne Asset avec `FOR UPDATE`; la création de relations Asset↔Asset verrouille les deux actifs dans l'ordre déterministe; la création de liens fournisseur-actif verrouille aussi la ligne Asset. Ces verrous constituent le mécanisme de sérialisation partagé par les scénarios concurrents.
- Limite : le scénario de concurrence fournisseur/retrait vérifie les états finaux mais ne constitue pas un test de charge ou de stress. La tranche ne revendique pas une validation sous forte contention.
- Validation du nouveau test unitaire et du dernier HEAD : CI à attendre ; les 42 tests PostgreSQL mentionnés ci-dessus concernent le HEAD précédent, pas le commit de cette tranche.

### Tranche cycle de vie Asset↔Risk — conservation de l'historique

- Revue du code : la création d'un lien Asset↔Risk verrouille la ligne Asset (SELECT ... FOR UPDATE) et refuse un actif retiré/décommissionné ; le retrait verrouille également l'actif. La suppression d'un risque est déjà protégée lorsqu'un lien Asset↔Risk existe.
- Décision métier retenue pour les tests : un lien vers un risque existant constitue une trace historique et ne doit pas être effacé automatiquement au retrait de l'actif. Le retrait d'un actif ne doit donc pas être bloqué par le seul lien Asset↔Risk ; en revanche, aucune nouvelle association ne doit être créée après le retrait.
- Test PostgreSQL ajouté dans backend/tests/test_asset_lifecycle_postgres.py : création d'un lien, retrait de l'actif, vérification de la conservation du lien, tentative de nouvelle association rejetée en HTTP 409, puis vérification qu'aucun doublon n'a été créé.
- Nettoyage du test : suppression explicite de l'événement d'audit lié, du lien, de l'actif et du risque afin de ne pas laisser de données dans la base d'intégration.
- Commit de test : c6cb952797444b88029da8183b21e30c5cdb4081.
- **État de validation au moment de cette note :** test ajouté au dépôt ; exécution PostgreSQL CI sur ce nouveau HEAD à vérifier. Aucun résultat de test local n'est revendiqué.

### Prochaine tranche

1. Vérifier la CI complète sur le HEAD contenant le test PostgreSQL Asset↔Risk.
2. Compléter la matrice PostgreSQL Application↔Asset (cardinalité 1:N, réaffectation et FK restrictive).
3. Revoir les chemins de réactivation d'un actif et les associations historiques, puis actualiser le statut des gates Phase 1.

### Validation CI — cycle de vie Asset↔Risk

- HEAD validé : `de7e8d996040b6a581d437df0b7a01bf82b66bd1`.
- Workflows push `45970471909` et pull_request `45970480134` : cinq jobs réussis chacun (Backend, PostgreSQL Integration, Frontend, Compose Smoke, Production Runtime Smoke).
- Logs PostgreSQL du workflow push : **43 tests réussis** sur la suite d'intégration PostgreSQL ciblée, incluant `test_asset_lifecycle_postgres.py`. Les erreurs SQL attendues dans certains tests négatifs (unicité, FK restrictive, append-only et contraintes CHECK) ne sont pas des échecs du job ; le job s'est terminé avec succès.
- Le test Asset↔Risk ajouté dans la tranche précédente est donc exécuté avec succès sur PostgreSQL 16 CI.

### Tranche PostgreSQL Application↔Asset — cardinalité 1:N

- Le modèle `Asset.application_id` référence `applications.id` avec `ON DELETE RESTRICT`, sans unicité sur `application_id`. La migration `0008_asset_app_cardinality` retire l'ancienne contrainte 1:1 et son downgrade refuse de réintroduire l'unicité si des doublons existent.
- Test PostgreSQL ajouté dans `backend/tests/test_asset_lifecycle_postgres.py` : création de deux actifs rattachés à une même application, réaffectation du second actif à une autre application, puis vérification que la suppression de chacune des applications référencées est refusée par la FK restrictive.
- Le test nettoie les événements d'audit des actifs, les actifs et les applications dans cet ordre.
- Commit du test : `70f4c4c371c1f6ff61da6f14e5f00d6435aa68ec`.
- **Validation de cette nouvelle tranche en attente** : les workflows doivent être observés sur le HEAD qui contient ce test. Aucun résultat local n'est revendiqué.

### Prochaine tranche

1. Vérifier les deux exécutions CI (push et PR) sur le nouveau HEAD et lire le résultat PostgreSQL.
2. Examiner la cohérence de l'affectation `application_id` lors de l'import CSV et des mises à jour partielles.
3. Poursuivre la revue des dépendances et de la réactivation des actifs, puis mettre à jour le registre de maturité Cartographie.

### Tranche complémentaire — validation application CSV et réactivation avec historique

- HEAD de code validé : `3297c576129dd90d2e7684343ce8ba370c10edef`.
- Prévisualisation CSV : ajout d'un test qui fournit un `application_id` inconnu et vérifie le rejet de la ligne (`can_import=false`, zéro ligne valide), le message « Application associée introuvable » et l'absence de toute écriture.
- Réactivation PostgreSQL : ajout d'un scénario qui réactive un actif retiré et vérifie simultanément la remise à `NULL` de `retired_at`, la conservation de `application_id`, la conservation du lien historique Asset↔Risk et la création d'un événement `REACTIVATE` dans l'audit outbox.
- Validation observée sur le workflow Push `45975232474`, associé au HEAD exact :
  - Backend : **513 passed, 46 skipped, 1 warning**.
  - PostgreSQL Integration : **45 passed** ; le scénario de réactivation avec application et lien de risque est inclus dans cette suite.
  - Frontend : succès.
  - Docker Compose Smoke : succès, y compris les vérifications du parser et de ClamAV.
  - Production Runtime Smoke : succès, y compris santé, TLS, proxy, isolation réseau, parser et ClamAV.
- Résultat : **5/5 jobs réussis** sur le HEAD de code. Les tests sont exécutés par GitHub Actions ; aucun résultat de test local n'est revendiqué.
- Les erreurs PostgreSQL visibles dans les logs correspondent à des cas négatifs attendus (contraintes d'unicité/FK, append-only et CHECK) ; la suite se termine avec succès.
- Limite : le test CSV du nouvel identifiant d'application est un test unitaire de prévisualisation avec session mockée ; il complète les tests existants mais ne constitue pas un parcours HTTP complet d'import confirmé sur PostgreSQL.

### Prochaine tranche

1. Vérifier les workflows sur le HEAD documentaire qui enregistre cette validation.
2. Étendre les scénarios CSV à la confirmation PostgreSQL et à la concurrence d'import si l'architecture du pipeline le permet.
3. Poursuivre la matrice des relations Asset↔Asset, y compris cycles, réactivation, relations historiques et contention concurrente.
4. Terminer l'audit de cohérence des routes et permissions Cartographie avant de déclarer un jalon Phase 1 achevé.


### Tranche relations Asset↔Asset — validation CI et concurrence de cycle à trois nœuds

- HEAD de code précédent contrôlé : `6988442f642a4677b7e532bdd2641ffc0b623a80`.
- Workflow Push `45975764226`, associé au SHA exact : **5/5 jobs terminés avec succès**.
  - Backend : `513 passed, 47 skipped, 1 warning` ; compilation Python réussie.
  - PostgreSQL Integration : **46 passed** ; migrations, contrôle de drift, chemin upgrade/downgrade et sauvegarde/restauration exécutés avant les tests.
  - Frontend : build réussi.
  - Compose Smoke : parser isolé, authentification/fail-closed et ClamAV réel vérifiés ; fichier sain accepté et EICAR détecté.
  - Production Runtime Smoke : santé, TLS/proxy/isolation réseau, parser, authentification/fail-closed et ClamAV réel vérifiés ; fichier sain accepté et EICAR détecté.
- La revue du code confirme que les créations de relations `depends_on` acquièrent un verrou consultatif transactionnel PostgreSQL commun (`pg_advisory_xact_lock(736291, 1)`) avant la vérification de cycle. Les deux actifs sont ensuite verrouillés dans l'ordre déterministe de leur identifiant. Un test PostgreSQL antérieur vérifie déjà deux arêtes opposées concurrentes ; le test de cycle de vie Asset↔Asset vérifie la conservation des liens au retrait puis la création après réactivation.
- Nouvelle couverture ajoutée dans `backend/tests/test_asset_relationships_postgres.py` : trois créations concurrentes A→B, B→C et C→A doivent aboutir à exactement deux relations acceptées et une relation rejetée HTTP 422 ; le graphe persistant reste donc acyclique. Le test vérifie les arêtes persistées et nettoie les événements d'audit ainsi que les données créées.
- Commit de test : `08837d2440fdc08f5674e31fd58045705b90fd6d`.
- **Statut de cette nouvelle couverture : en attente d'exécution CI sur le nouveau HEAD.** Les 46 tests PostgreSQL et les 513 tests backend ci-dessus valident le HEAD précédent, pas encore le commit `08837d2`.
- La PR #1 reste ouverte, Draft et non fusionnée ; la branche `main` n'est pas modifiée.

### Prochaine tranche

1. Vérifier le workflow complet du commit `08837d2`, en particulier le nouveau test PostgreSQL concurrent à trois arêtes.
2. Si la CI passe, poursuivre l'audit des permissions croisées Cartographie↔Risques et Cartographie↔Fournisseurs, puis les tests JWT E2E.
3. Reprendre le chantier de volumétrie/performance (graphe, qualité, analyse d'impact) et la clarification des responsables d'actifs, sans migration destructive avant inventaire des modèles et données.


### Résultats CI — concurrence des dépendances et revue RBAC intermodules

- HEAD évalué : `a2ba214b89405c7f1a025a099b2c0866398c9c9d`.
- Workflows Push `45976555066` et Pull Request `45976563403` : **5/5 jobs réussis chacun**.
- Backend : **513 passed, 48 skipped, 1 warning**.
- PostgreSQL Integration : **47 passed**. Le nouveau test `test_concurrent_three_edge_dependency_cycle_is_rejected` est inclus dans cette suite et a réussi. Il confirme que trois arêtes concurrentes A→B, B→C, C→A ne peuvent persister un cycle : deux relations sont créées et la troisième est rejetée.
- Frontend, Compose Smoke et Production Runtime Smoke : jobs réussis dans les deux workflows.
- Les messages PostgreSQL `ERROR` relevés dans les logs concernent des tests négatifs intentionnels (contraintes FK/UNIQUE/CHECK et journal append-only) ; la suite PostgreSQL se termine bien avec 47 tests réussis.
- Revue RBAC intermodules : les rôles ayant accès à la lecture Cartographie et à la lecture des risques sont admin, executive et auditor ; Viewer peut lire les risques mais pas l'inventaire des actifs. La lecture des relations fournisseurs-actifs est limitée à admin/auditor. Les opérations de modification de liens Asset↔Risk et Asset↔Supplier sont réservées à admin, qui possède les permissions de modification des deux modules. Cette intersection est maintenant verrouillée par un test paramétré de matrice dans `backend/tests/test_assets_permissions.py`.
- Commit de test de matrice RBAC : `9f7d3948e3c0b33e2aae008c9ef771c6ecbc8391`. Sa validation CI est documentée dans la tranche consolidée ci-dessous.
- PR #1 reste ouverte, Draft et non fusionnée ; `main` reste inchangée.

### Suite de validation Cartographie

1. Valider la nouvelle matrice RBAC sur le HEAD `9f7d394`.
2. Compléter les tests HTTP d'accès aux routes croisées (risques et fournisseurs), notamment les refus avant accès DB.
3. Passer aux tests JWT end-to-end et aux contrôles de volumétrie/performance du graphe, de la qualité d'inventaire et de l'analyse d'impact.
4. Maintenir ouverte la décision métier sur les colonnes sensibles de l'export CSV et le modèle de rattachement des responsables d'actifs.


### Tranche performance SQL et autorisations HTTP croisées — validation CI complète

- HEAD validé : `4b775fd883afd09da492b66989f9e2fed4bd9751`.
- Workflows Push `45978265241` et Pull Request `45978271743` : **5/5 jobs réussis chacun**.
- Backend : **523 passed, 49 skipped, 1 warning** dans les deux workflows.
- PostgreSQL Integration : **48 passed** dans les deux workflows. Le test `test_inventory_quality_sql_aggregates_active_assets_and_blank_values` est explicitement inclus dans la commande CI depuis le commit `f9e1ea317fa7cf54a8f7b38029d576dd051b1825`; il valide sur PostgreSQL les actifs actifs/retirés, les champs NULL ou blancs, les dates de support échues et à échéance dans les 90 jours.
- Frontend, Compose Smoke et Production Runtime Smoke : succès dans les deux workflows. Les vérifications runtime incluent santé, TLS/proxy, séparation réseau, parser, gestion fail-closed et ClamAV réel (fichier sain accepté, EICAR détecté).
- Optimisation de `GET /assets/graph` : les relations sont maintenant filtrées en SQL par deux sous-requêtes sur les actifs actifs (source et cible), au lieu de charger toutes les relations puis filtrer en Python. Les tests vérifient la présence des deux prédicats SQL.
- Optimisation de `GET /assets/quality` : les compteurs de complétude et les indicateurs de fin de support sont calculés par une agrégation SQL unique. Le comportement conserve l'exclusion des actifs retirés et considère les chaînes nulles, vides ou composées d'espaces comme des champs manquants.
- Couverture HTTP intermodules ajoutée dans `backend/tests/test_asset_http_authorization.py` : Viewer ne peut pas lire les actifs liés à un risque sans permission `assets:read`; Executive et Viewer ne peuvent pas consulter les fournisseurs liés à un actif sans `suppliers:read_assets`; Auditor peut accéder à cette route. Les refus vérifient qu'aucune requête DB n'est exécutée.
- Les commits de cette tranche sont `55322b53` (agrégation SQL qualité), `0212f133` (tests agrégations), `5e01fa12` (filtrage SQL graphe), `0df27b84` (normalisation des champs blancs), `edfc1147` (test PostgreSQL), `f9e1ea31` (inclusion explicite dans le workflow CI) et `4b775fd8` (tests HTTP RBAC croisés).
- Un avertissement de dépréciation Node.js 20 apparaît dans les runners GitHub Actions ; il ne fait pas échouer les tests. Les erreurs PostgreSQL consignées par les tests négatifs sont attendues et les suites se terminent avec succès.
- Limites restantes : aucune mesure de charge représentative ni plan `EXPLAIN ANALYZE` n'a été exécuté. Cette optimisation réduit les lignes chargées/transférées mais ne constitue pas une preuve de latence sous volumétrie de production. L'analyse d'impact transitive et ses jointures associées restent à profiler.
- PR #1 reste ouverte, Draft et non fusionnée ; la branche `main` reste inchangée.

### Prochaine tranche de validation Cartographie

1. Profiler l'analyse d'impact transitive et vérifier les plans SQL/index existants sur un jeu de données représentatif, sans ajouter d'index spéculatif.
2. Compléter les parcours JWT end-to-end des routes Cartographie, Risques et Fournisseurs ; les tests HTTP actuels utilisent des dépendances utilisateur surchargées et ne remplacent pas les tests JWT.
3. Examiner les permissions et les accès DB sur les autres routes Asset↔Risk et Asset↔Supplier, puis couvrir les refus et succès par rôle.
4. Poursuivre l'inventaire des modèles User/organisation avant toute évolution du rattachement owner/custodian/direction.
5. Garder ouvertes les décisions métier relatives à la confidentialité des exports CSV et à la validation des responsables d'actifs.


### Tranche JWT réel sur routes Cartographie — validation CI complète

- HEAD de code validé : `4c8f49b20710bc4ee8e0a612b40129d600617eca`.
- Workflows Push `45978806087` et Pull Request `45978815233` : **5/5 jobs réussis chacun**.
- Backend : **526 passed, 49 skipped, 1 warning** sur les deux workflows.
- PostgreSQL Integration : **48 passed** sur les deux workflows.
- Frontend, Compose Smoke et Production Runtime Smoke : succès sur les deux workflows.
- Trois tests HTTP supplémentaires utilisent la signature JWT réelle (HS256 de test) et la dépendance `get_current_user` réelle, sans override de l'authentification :
  - JWT d'auditeur valide : accès autorisé au graphe Cartographie.
  - `auth_version` périmé : refus HTTP 401 après la seule lecture de l'utilisateur, sans requête métier Cartographie.
  - rôle du JWT différent du rôle courant en base : refus HTTP 403 avant toute requête métier.
- Ces tests complètent, sans les remplacer, les tests d'authentification, de rotation et de révocation des sessions déjà présents. Ils ne simulent pas encore un parcours navigateur complet login → MFA → cookies → refresh → accès à la route.
- Commit : `4c8f49b20710bc4ee8e0a612b40129d600617eca`.
- Aucune migration de schéma n'a été introduite dans cette tranche.
- PR #1 reste ouverte, Draft et non fusionnée ; `main` reste inchangée.

### Prochaine tranche

1. Couvrir le cycle HTTP complet login/MFA/refresh/logout avec cookies réels et session PostgreSQL, en réutilisant les tests de rotation/révocation déjà existants.
2. Étendre les tests JWT aux routes Risques↔Cartographie et Fournisseurs↔Cartographie, y compris les rôles Executive, Auditor et Viewer.
3. Profiler les requêtes de l'analyse d'impact et obtenir des plans `EXPLAIN (ANALYZE, BUFFERS)` sur un volume représentatif avant toute décision d'index.
4. Reprendre l'analyse des modèles d'organisation et de responsabilité des actifs, sans migration destructive.


### Tranche sécurité intermodules — JWT réel sur Risques et Fournisseurs

- HEAD de départ contrôlé : `ff5aeb89aca0e3a667bc9c00adea6453cc8163ea`. La branche de travail et `main` étaient distinctes ; PR #1 restait ouverte, Draft et non fusionnée.
- Les workflows Push et PR de ce HEAD documentaire ont terminé avec succès, chacun avec 5/5 jobs : backend, frontend, PostgreSQL integration, Compose smoke et production runtime smoke.
- Constat : les routes `GET /risks/{risk_id}/assets` et `GET /suppliers/assets/{asset_id}/suppliers` avaient des tests HTTP avec surcharge d'utilisateur, mais pas encore de couverture JWT réel équivalente à celle de la route Graphe des actifs.
- Correction de couverture dans `backend/tests/test_asset_http_authorization.py` :
  - JWT signé Auditor, rôle et `auth_version` relus depuis l'utilisateur courant, accès autorisé aux actifs liés à un risque ;
  - JWT signé Auditor, accès autorisé aux fournisseurs liés à un actif ;
  - JWT signé Executive, refus 403 sur la lecture des fournisseurs liés à un actif.
- Le helper HTTP JWT monte désormais les routeurs Assets, Risks et Suppliers dans la même application de test.
- Commit : `17d63c0b561d8d30c2d10a1e262957b88a14ff43` — `test(cartography): exercise risk and supplier routes with real JWTs`.
- Limite de preuve : ces tests vérifient le décodage JWT, la résolution de l'utilisateur en base simulée et les contrôles d'autorisation HTTP ; ils ne constituent pas un parcours PostgreSQL réel de bout en bout. Le test d'intégration PostgreSQL reste séparé.
- CI du commit : déclenchée après le push ; résultats à vérifier avant de considérer cette tranche validée.

### Prochaine tranche

1. Vérifier les workflows Push et PR du commit JWT intermodules.
2. Examiner les tests existants de rotation et révocation pour identifier les étapes manquantes du parcours login/MFA/cookie/refresh/logout.
3. Ajouter un test de parcours HTTP complet réutilisant les fixtures existantes, sans réimplémenter le système d'authentification dans les tests.


#### Résultat CI — JWT intermodules

- Commit code `17d63c0b561d8d30c2d10a1e262957b88a14ff43` : workflows Push `45980193926` et PR `45980205024` terminés avec succès, chacun 5/5 jobs.
- Backend : `529 passed, 49 skipped, 1 warning`.
- PostgreSQL integration : `48 passed`, migrations et contrôle backup/restore réussis.
- Frontend, Compose smoke et Production runtime smoke : succès sur les deux workflows.
- La tranche JWT Risques/Fournisseurs est donc validée par CI. Le test d'authentification HTTP complet ajouté ensuite est suivi séparément.


### Tranche authentification — parcours HTTP PostgreSQL complet

- Un premier essai CI du nouveau test a échoué avec HTTP 422 à la requête login : l'adresse de fixture utilisait le domaine réservé `.invalid`, rejeté par la validation `EmailStr`. Il s'agissait d'une donnée de test invalide, pas d'un défaut de l'authentification.
- Correction : adresse de fixture remplacée par un domaine valide `.com`, sans changement du code applicatif.
- Commit du test corrigé : `958747943c335066e4ce08fc63c7c65b836c4be1`.
- Le test `test_http_login_mfa_refresh_logout_lifecycle` exerce les routes FastAPI réelles avec PostgreSQL :
  - connexion avec mot de passe vérifié ;
  - validation TOTP réel à partir d'un secret chiffré ;
  - émission du JWT d'accès et du refresh token en cookie HttpOnly ;
  - rotation via la route HTTP et émission du nouveau cookie ;
  - déconnexion HTTP, suppression du cookie et révocation des deux sessions persistées ;
  - vérification des événements d'audit en outbox.
- Validation PostgreSQL : `49 passed, 1 warning`, incluant le nouveau parcours.
- Workflow PR `45980765680` : 5/5 jobs réussis.
- Workflow Push `45980759047` : 5/5 jobs réussis.
- Backend : `529 passed, 50 skipped, 1 warning`. Les tests PostgreSQL sont exécutés dans le job dédié ; le parcours HTTP complet est exécuté et réussi dans ce job.
- Frontend, Compose smoke et Production runtime smoke : succès sur les deux workflows.
- Limite : le parcours testé concerne un compte déjà enrôlé MFA. Le scénario d'enrôlement initial et de changement obligatoire de mot de passe reste couvert par des tests dédiés, mais pas encore dans un seul parcours HTTP intégré.

### Décision de modèle — responsabilités et unités organisationnelles

- Inspection du modèle physique : `User` contient un champ texte `department`, mais aucun modèle ni table `OrganizationUnit` n'existe dans le dépôt au checkpoint.
- Le modèle `Asset` contient encore `owner`, `custodian` et `direction` sous forme de chaînes de caractères.
- Décision : ne pas créer maintenant de FK `owner_user_id` / `owner_unit_id` et ne pas lancer de migration. Il n'existe pas encore de référentiel organisationnel canonique ni de correspondance de reprise vérifiée ; mapper des noms libres vers des comptes ou directions serait risqué et pourrait attribuer une responsabilité au mauvais acteur.
- La section Organisation de `docs/TARGET_DATA_MODEL.md` distingue désormais explicitement la cible proposée du schéma physique existant.
- Les champs actuels sont conservés sans changement. Une migration additive ne sera étudiée qu'après identification de la source organisationnelle, de ses codes stables, des règles hiérarchiques et des correspondances validées.

### Prochaine priorité Phase 1

1. Compléter les scénarios d'intégrité du cycle de vie Asset ↔ Application/Risk/Supplier et les tests de concurrence.
2. Auditer les règles d'orientation et les cas limites de l'analyse d'impact ; obtenir des mesures `EXPLAIN (ANALYZE, BUFFERS)` sur PostgreSQL représentatif.
3. Finaliser les tests d'import/export et la décision de classification des champs exportables.
4. Terminer la recette frontend et la matrice de couverture route × rôle × opération.


### Tranche analyse d'impact — frontières du cycle de vie

- Tests ajoutés dans `backend/tests/test_asset_graph_api.py` :
  - une analyse d'impact dont l'actif source est retiré retourne HTTP 404 avant toute lecture du graphe ;
  - la requête des relations `depends_on` filtre les deux extrémités sur `retired_at IS NULL` et exclut les états `Retiré` et `Décommissionné`.
- Premier passage CI : 1 assertion de test incorrecte, car les valeurs de statut sont des paramètres SQLAlchemy liés et non du texte SQL littéral. Correction du test pour examiner les valeurs liées compilées ; aucun changement de code applicatif nécessaire.
- Commit de correction et de couverture : `be02ef103bbf506664665c49dac0ee27593d70ef`.
- Validation sur ce HEAD :
  - Push `45983071899` : 5/5 jobs réussis.
  - PR `45983079134` : 5/5 jobs réussis.
  - Backend : `531 passed, 50 skipped, 1 warning`.
  - PostgreSQL integration : succès.
  - Frontend, Compose smoke et Production runtime smoke : succès.
- Aucun index supplémentaire n'est ajouté à ce stade. Les relations disposent déjà d'index sur les colonnes source et cible ainsi que d'une contrainte unique composite. Une décision d'indexation supplémentaire doit être fondée sur un plan `EXPLAIN (ANALYZE, BUFFERS)` obtenu sur une volumétrie représentative, pas sur une supposition.
- Limite restante : les workflows valident le comportement et les migrations, mais ils ne remplacent pas une campagne de profilage sur un inventaire volumineux représentatif. Aucun temps de réponse ni gain de performance n'est revendiqué.

### Priorités restantes avant clôture de la Phase 1

1. Compléter la matrice des scénarios de cycle de vie et de concurrence entre Actifs, Applications, Risques et Fournisseurs.
2. Obtenir un jeu de données PostgreSQL représentatif et documenter les plans `EXPLAIN (ANALYZE, BUFFERS)` des requêtes d'impact, de graphe, de pagination et de qualité.
3. Revoir les cas limites de l'agrégation des risques et des expositions fournisseurs dans l'analyse d'impact.
4. Terminer la revue de bout en bout du frontend Cartographie et la matrice route × rôle × opération.
5. Consolider les critères de sortie et les preuves de non-régression dans la recette Phase 1.


### Tranche intégrité — concurrence Asset ↔ Risk et cycle de vie

- Commit de test : `50ad440c8e2c90396c8bad8356bdc6fe7373bf06` — `test(cartography): serialize risk links with asset retirement`.
- Le nouveau test PostgreSQL `test_asset_risk_link_creation_and_retirement_are_serialized` lance en concurrence la création d'un lien actif↔risque et le retrait du même actif, puis vérifie l'état persistant de l'actif et du lien.
- Les deux opérations verrouillent la ligne Asset avec `SELECT ... FOR UPDATE`. La sérialisation garantit que le lien est soit créé avant le retrait (et conservé comme association historique), soit refusé si le retrait est déjà effectif. Le retrait reste autorisé en présence d'un lien Asset↔Risk historique ; les liens fournisseur actifs et les demandes d'accès ouvertes sont, eux, des bloqueurs métier explicites.
- Contrôle du code fournisseur : la création d'une relation fournisseur↔actif verrouille également l'actif ; un test PostgreSQL concurrent création de lien fournisseur/retrait existait déjà dans `test_asset_lifecycle_postgres.py`. Le chemin de création d'une demande d'accès verrouille le fournisseur, la relation fournisseur-actif et l'actif avant validation.
- Validation du commit `50ad440c` : workflow Push `45987836209` et workflow Pull Request `45987849935`, chacun avec **5/5 jobs réussis** (backend, PostgreSQL integration, frontend, Compose smoke et Production runtime smoke). Backend : **531 passed, 51 skipped, 1 warning**. Le warning concerne une dépréciation Starlette/AnyIO ; il n'a pas fait échouer la suite.
- Aucun changement de code applicatif ni migration de schéma dans cette tranche : ajout de couverture de concurrence et documentation uniquement.
- Limite : les tests de concurrence valident des interleavings contrôlés par les opérations asynchrones du test, mais ne constituent pas un test de stress multi-utilisateurs prolongé ni une preuve de performance sous charge.
- PR #1 reste ouverte, Draft et non fusionnée ; `main` reste inchangée.

### Prochaine tranche d'intégrité

1. Ajouter/compléter un test de concurrence entre création d'une demande d'accès fournisseur et retrait d'actif, avec vérification de l'absence d'autorisation ouverte sur un actif retiré.
2. Vérifier les chemins de modification/réactivation d'un lien fournisseur et leur cohérence avec les demandes d'accès historiques.
3. Finaliser la matrice route × rôle × opération pour les endpoints Asset, Risk et Supplier, en incluant refus avant toute lecture métier.
4. Terminer les essais d'import CSV transactionnels/concurrents et l'équivalence pagination/export.
5. Maintenir le profilage PostgreSQL représentatif comme gate séparé : aucun `EXPLAIN (ANALYZE, BUFFERS)` représentatif n'est encore disponible.



### Tranche intégrité — demande d'accès fournisseur et terminaison du lien

- Commit de test : `bcde1afefe6f3dfce44ddbb1095379c2a3778f18` — `test(cartography): tighten supplier access concurrency fixture`.
- Le test PostgreSQL `test_supplier_access_request_creation_and_link_termination_are_serialized` exécute simultanément la création d'une demande d'accès et la terminaison du lien fournisseur↔actif concerné.
- Deux résultats cohérents sont acceptés :
  - la demande est créée (HTTP 201), puis la terminaison est refusée (HTTP 409) car une demande ouverte existe ;
  - la terminaison réussit (HTTP 200), puis la demande est refusée (HTTP 404), car le lien n'est plus accessible comme relation active.
- Après les deux transactions, le test relit PostgreSQL et vérifie l'invariant persistant : un lien marqué `Terminé` ne possède aucune demande dans les états ouverts `Demandé`, `Approuvé` ou `Suspendu`.
- Workflows Push `45991739766` et Pull Request `45991747213` : **5/5 jobs réussis chacun**.
- Backend : **531 passed, 52 skipped, 1 warning**. PostgreSQL Integration : **51 passed, 1 warning**. Frontend, Compose Smoke et Production Runtime Smoke : succès.
- Les messages PostgreSQL `ERROR` présents dans les logs sont les violations attendues par des tests négatifs (contraintes/FK, append-only, unicité) ; le job s'est terminé avec succès. Ils ne constituent pas des échecs de la suite.
- Aucun changement applicatif ni migration de schéma dans cette tranche : ajout d'un test d'intégration de concurrence.
- Limite : ce scénario contrôle des interleavings entre deux opérations concurrentes ; il ne constitue pas un test de charge prolongé ni une mesure de performance.

### Revue du cycle de vie des liens fournisseur — décision de périmètre

- Le modèle `SupplierAssetLink` limite les statuts à `Actif`, `Suspendu` et `Terminé`, et impose une unicité sur `(supplier_id, asset_id, relationship_type)`.
- Les routes observées permettent la création d'un lien et sa terminaison. Aucun endpoint de réactivation ou de modification du statut d'un lien terminé n'a été identifié dans le routeur actuel.
- La création d'un nouveau lien de même fournisseur, actif et type de relation après terminaison est empêchée par la contrainte d'unicité : il ne faut donc pas présenter la recréation comme une réactivation prise en charge.
- Décision : ne pas ajouter de route de réactivation ni modifier la contrainte d'unicité sans règle métier validée. Une éventuelle évolution devra définir si la réactivation réutilise l'identifiant historique ou crée une nouvelle version, comment elle traite les demandes d'accès anciennes (révoquées/expirées/refusées), et comment l'audit conserve la chronologie. Une demande d'accès ouverte doit continuer à bloquer la terminaison.
- Les associations Asset↔Risk historiques sont conservées lors du retrait/réactivation de l'actif ; cela ne doit pas être transposé automatiquement aux liens fournisseur, dont la relation et les autorisations d'accès ont un cycle de vie distinct.
- Aucun changement de schéma ni de comportement n'est effectué sur la base de cette revue statique.

### Prochaine tranche d'intégrité

1. Tester explicitement la conservation et la lecture des demandes d'accès historiques après terminaison d'un lien, en distinguant demandes révoquées, expirées et refusées.
2. Compléter les tests de décision, révocation, expiration et revue d'accès pour s'assurer qu'aucune transition ne réouvre implicitement un droit après terminaison du lien.
3. Poursuivre la matrice route × rôle × opération sur les endpoints Asset, Risk et Supplier.
4. Terminer les essais d'import CSV transactionnels/concurrents et l'équivalence pagination/export.
5. Maintenir le profilage PostgreSQL représentatif comme gate séparé : aucun `EXPLAIN (ANALYZE, BUFFERS)` représentatif n'est encore disponible.


### Tranche contrôle des revues d'accès fournisseur — éligibilité revalidée

- Revue du parcours des demandes d'accès : création, décision, revue périodique, révocation, expiration et terminaison du lien fournisseur↔actif.
- Défaut identifié : la revue périodique pouvait auparavant accepter une décision `Maintenue` ou `Réduite` sur une autorisation encore `Approuvé` sans revalider l'éligibilité actuelle du fournisseur, du lien et de l'actif.
- Correction dans `review_supplier_access` : pour les issues `Maintenue` et `Réduite`, l'endpoint verrouille et recontrôle le fournisseur (non archivé et approuvé), le lien (actif et rattaché au fournisseur) et l'actif (non retiré/décommissionné, marqueur `retired_at` absent). En cas d'inéligibilité, la revue est refusée HTTP 409 avant toute modification ou insertion d'une revue.
- La révocation `Révoquée` reste possible sans exiger que le lien soit encore actif : elle doit pouvoir fermer un droit devenu non éligible. Les règles de séparation des tâches et de validité temporelle restent appliquées.
- Test ajouté : `test_supplier_access_review_cannot_maintain_authorization_after_link_termination`. Il vérifie le refus d'une revue `Maintenue` lorsque le lien actif est introuvable/terminé, et l'absence d'insertion, de commit ou de modification.
- Commit applicatif : `521c54462dea4d21a60c4b4808c8aac9b4ec8592` — `fix(suppliers): revalidate access eligibility during reviews`.
- Commit de test : `efdf7e567069d4616e2ebc033fdb03936cc2a974` — `test(suppliers): reject reviews on terminated asset links`.
- Workflows Push `46003710011` et Pull Request `46003717916` du commit applicatif : **5/5 jobs réussis chacun**.
- Workflows Push `46003735120` et Pull Request `46003742969` du commit de test : **5/5 jobs réussis chacun**.
- Backend : **532 passed, 53 skipped, 1 warning**. PostgreSQL Integration : **52 passed, 1 warning**. Frontend, Compose Smoke et Production Runtime Smoke : succès sur les deux workflows du commit de test.
- Aucun changement de schéma ou de migration. Le contrôle supplémentaire utilise les lignes existantes et leurs verrous transactionnels.
- Limite : ce test est une validation unitaire de la branche de refus ; les tests PostgreSQL confirment la suite d'intégration existante, mais un parcours PostgreSQL HTTP complet de décision/revue/révocation/expiration reste à construire.

### Prochaine tranche prioritaire

1. Construire un parcours PostgreSQL HTTP couvrant demande → approbation → revue maintenue/réduite → révocation/expiration, avec séparation des rôles et traces d'audit.
2. Ajouter un test PostgreSQL vérifiant que la terminaison du lien reste impossible tant qu'une autorisation approuvée/suspendue est ouverte, puis possible après révocation ou expiration.
3. Compléter la matrice HTTP réelle JWT route × rôle × opération pour les endpoints de gestion des demandes d'accès fournisseur.
4. Reprendre l'import CSV transactionnel/concurrent et l'équivalence pagination/export.
5. Obtenir des plans `EXPLAIN (ANALYZE, BUFFERS)` sur une volumétrie représentative avant toute décision d'indexation.


### Tranche PostgreSQL — révocation avant terminaison du lien fournisseur

- Test ajouté dans `backend/tests/test_supplier_access_lifecycle_postgres.py` : `test_approved_access_blocks_link_termination_until_revocation`.
- Le test prépare un fournisseur approuvé, un actif actif, un lien actif et une demande d'accès déjà approuvée ; vérifie que la terminaison du lien retourne HTTP 409 ; appelle ensuite l'endpoint réel de révocation ; termine enfin le lien et relit l'état persistant ainsi que les événements d'audit.
- Le premier workflow PostgreSQL a détecté une erreur de fixture : le statut `Approuvé` exige `decided_by_id` **et** `decided_at`, conformément à la contrainte `ck_supplier_access_requests_decision_trace`. La fixture a été corrigée en fournissant aussi la date et le commentaire de décision. Ce n'était pas un défaut du code applicatif ni une modification de schéma.
- Commit du test corrigé : `c8300d3eb8cef7d2b7d9c32b074c2c4961b7ab28`.
- Workflows Push `46004867979` et Pull Request `46004879203` : **5/5 jobs réussis chacun**.
- Backend : **532 passed, 54 skipped, 1 warning**. PostgreSQL Integration : **53 passed, 1 warning**. Frontend, Compose Smoke et Production Runtime Smoke : succès.
- Les messages PostgreSQL `ERROR` observés dans les logs d'intégration correspondent aux tests négatifs de contraintes, FK et append-only ; le job est terminé avec succès.
- Les événements `REVOKE_SUPPLIER_ACCESS` et `TERMINATE_SUPPLIER_ASSET_LINK` sont vérifiés dans l'outbox. Le test ne prétend pas valider toute la matrice JWT/rôles ni l'expiration automatique.
- Aucun changement applicatif, migration ou modification de schéma dans cette tranche : ajout de couverture d'intégration PostgreSQL.

### Prochaine tranche prioritaire

1. Couvrir l'expiration d'une autorisation réellement échue, puis la terminaison du lien, avec conservation de la trace d'audit.
2. Étendre le parcours PostgreSQL aux décisions d'approbation et aux revues maintenue/réduite, avec des acteurs distincts lorsque les règles de séparation des tâches l'exigent.
3. Construire la matrice HTTP JWT route × rôle × opération pour les endpoints Supplier (demande, décision, revue, révocation, expiration, gestion des liens).
4. Reprendre les contrôles CSV transactionnels/concurrents et l'équivalence pagination/export.
5. Obtenir des plans `EXPLAIN (ANALYZE, BUFFERS)` sur une volumétrie représentative avant toute décision d'indexation.

## Complément — expiration d'une autorisation fournisseur (27/11/2026)

Le commit `a0f272cd771fc490739b328226a7ee102de4add9` ajoute le test PostgreSQL
`test_expired_approved_access_can_be_expired_before_link_termination`.

Le scénario vérifie qu'un lien fournisseur ne peut pas être terminé tant qu'une
autorisation approuvée et arrivée à échéance n'a pas été explicitement expirée.
L'endpoint d'expiration applique les contrôles de statut et de date, verrouille
la demande avec `SELECT ... FOR UPDATE`, puis écrit l'événement
`EXPIRE_SUPPLIER_ACCESS` dans l'outbox dans la même transaction. Après expiration,
la terminaison du lien est autorisée et son événement d'audit est vérifié.

**Résultats CI observés sur le SHA exact** :
- Workflow Push `46007313446` : 5/5 jobs réussis.
- Backend : `532 passed, 55 skipped, 1 warning`.
- PostgreSQL Integration : `54 passed, 1 warning`.
- Frontend, Compose Smoke et Production Runtime Smoke : succès.

Les messages PostgreSQL `ERROR` visibles dans le journal d'intégration proviennent
de tests négatifs intentionnels (contraintes d'intégrité, append-only et clés
étrangères) ; le job se termine avec 54 tests réussis et aucun échec.

Cette validation est une intégration PostgreSQL appelant les fonctions d'endpoint
dans le contexte de test ; elle ne remplace pas une matrice HTTP/JWT complète
sur les routes fournisseurs.

**Suite** : compléter la matrice HTTP/JWT rôles × permissions × opérations pour
les routes fournisseurs, puis traiter les tests transactionnels/concurrence CSV,
pagination et équivalence des exports. La Phase 0 demeure ouverte.


## Complément — contrôle HTTP/JWT des permissions fournisseurs (27/11/2026)

Le commit `a85f2dd764900e866218cb989e82b7fb74da7dcf` ajoute quatre scénarios HTTP
dans `backend/tests/test_asset_http_authorization.py`, exécutés via FastAPI
`TestClient` avec des access tokens JWT réellement signés et validés par
`get_current_user` :

- un auditeur authentifié peut consulter les demandes d'accès d'un fournisseur ;
- les rôles `executive` et `viewer` sont refusés sur cette lecture, avant toute
  requête métier ;
- un auditeur ne peut pas créer une demande d'accès ;
- une requête sans bearer token reçoit HTTP 401.

Le contrôle utilise une base simulée pour isoler le chemin HTTP, la validation
du JWT, l'état du compte et la dépendance RBAC. Il ne constitue donc pas encore
un parcours HTTP/JWT adossé à PostgreSQL, ni une couverture exhaustive de
chaque opération (décision, revue, révocation, expiration et terminaison).

**Résultats CI sur le SHA exact `a85f2dd`** — workflow Push
`46012310288` : **5/5 jobs réussis**.
- Backend : **537 passed, 55 skipped, 1 warning**.
- PostgreSQL Integration : **54 passed, 1 warning** ; migrations, contrôle de
  dérive, chemin upgrade/downgrade et sauvegarde/restauration réussis.
- Frontend : build réussi.
- Compose Smoke : démarrage de la stack, API/proxy, parser isolé, authentification,
  refus fail-closed et verdicts ClamAV sain/EICAR réussis.
- Production Runtime Smoke : images durcies, migrations, démarrage, health,
  TLS/proxy, isolation réseau et parcours parser réussis.

Le warning backend est une dépréciation Starlette/TestClient
(`anyio.abc.BlockingPortal`) ; il n'a pas fait échouer les tests. Les messages
PostgreSQL `ERROR` du job correspondent aux tests négatifs intentionnels
(constraints, FK et append-only), avec 54 tests réussis et aucun échec.

**Prochaine tranche** : étendre la matrice HTTP/JWT aux opérations de décision,
revue, révocation, expiration et terminaison ; puis relier au moins un parcours
de bout en bout aux fixtures PostgreSQL réelles. Les contrôles CSV
transactionnels/concurrents, pagination et équivalence export restent au
backlog. La Phase 0 demeure ouverte.


## Complément — matrice HTTP/JWT et parcours PostgreSQL réel (27/11/2026)

Deux niveaux de preuve supplémentaires ont été ajoutés :

1. Dans `backend/tests/test_asset_http_authorization.py`, cinq tests HTTP
   utilisent des JWT signés et couvrent le refus des rôles auditeur sur les
   opérations de décision, revue, révocation, expiration et terminaison d'une
   relation fournisseur-actif. Chaque refus vérifie qu'aucune requête métier,
   écriture ou validation transactionnelle ne suit l'authentification.
2. Dans `backend/tests/test_supplier_access_lifecycle_postgres.py`, le test
   `test_supplier_access_http_jwt_uses_real_postgres_user_and_supplier`
   traverse réellement FastAPI `TestClient`, la validation du JWT, la lecture
   du compte en PostgreSQL et les requêtes fournisseur en PostgreSQL. Il
   confirme qu'un auditeur peut lire les demandes d'accès et qu'une création
   lui est refusée (HTTP 403), sans persister de demande.

**Résultats CI sur le SHA `e6c5a6f094d2dde91ff783c018c14af3d8c14025`** —
workflow Push `46013346513` : **5/5 jobs réussis**.
- Backend : **542 passed, 56 skipped, 1 warning**.
- PostgreSQL Integration : **55 passed, 1 warning** ; le nouveau parcours
  HTTP/JWT PostgreSQL réel est inclus dans ce décompte.
- Frontend : build réussi.
- Compose Smoke : API/proxy, parser isolé, authentification, refus fail-closed
  et verdicts ClamAV sain/EICAR réussis.
- Production Runtime Smoke : migrations, démarrage, health, TLS/proxy,
  isolation réseau et parcours parser réussis.

Les warnings observés sont des dépréciations Starlette/TestClient
(`anyio.abc.BlockingPortal`) et de l'environnement d'exécution ; aucun job
n'a échoué.

**Limite restante** : le parcours PostgreSQL réel couvre une lecture autorisée
et une création refusée. Il ne couvre pas encore l'ensemble des mutations
fournisseurs avec JWT et base réelle (décision, revue, révocation, expiration,
terminaison). Cette extension, ainsi que les contrôles CSV transactionnels/
concurrents, pagination et équivalence export, reste au backlog. La Phase 0
demeure ouverte.


## Complément — cycle complet fournisseur via HTTP/JWT et PostgreSQL (27/11/2026)

Le test `test_supplier_access_full_lifecycle_over_http_with_real_jwt_and_postgres`
dans `backend/tests/test_supplier_access_lifecycle_postgres.py` valide
maintenant le cycle métier complet à travers les routes FastAPI et la base
PostgreSQL migrée :

- un premier administrateur authentifié crée la demande ;
- un second administrateur authentifié l'approuve (l'identité distincte
  vérifie l'interdiction d'auto-approbation) ;
- le second administrateur révoque l'autorisation ;
- il termine ensuite la relation fournisseur-actif ;
- le test relit les états persistés et contrôle les événements d'audit
  `CREATE_SUPPLIER_ACCESS_REQUEST`, `REVOKE_SUPPLIER_ACCESS` et
  `TERMINATE_SUPPLIER_ASSET_LINK`.

Les deux comptes sont de vrais utilisateurs PostgreSQL ; les access tokens
sont signés et validés par la dépendance d'authentification de l'application.
Les appels passent par `TestClient`, sans remplacer la dépendance JWT par
un utilisateur simulé.

**Résultats CI sur le SHA `ca0716989be7c08bfa892115347fe85de1d89ff6`** —
workflow Push `46013811517` : **5/5 jobs réussis**.
- Backend : **542 passed, 57 skipped, 1 warning**.
- PostgreSQL Integration : **56 passed, 1 warning** ; le cycle complet HTTP/JWT
  et PostgreSQL est inclus dans ce décompte.
- Frontend : build réussi.
- Compose Smoke : stack, API/proxy, parser isolé, authentification, refus
  fail-closed et verdicts ClamAV sain/EICAR réussis.
- Production Runtime Smoke : migrations, démarrage, health, TLS/proxy,
  isolation réseau et parcours parser réussis.

**Portée** : la création, l'approbation, la révocation et la terminaison sont
désormais couvertes de bout en bout. Les opérations de revue périodique et
d'expiration restent à ajouter à ce parcours PostgreSQL HTTP/JWT ; les tests
HTTP de refus RBAC de l'auditeur existent déjà pour ces deux opérations.
La Phase 0 reste ouverte.


## Complément — revue périodique et expiration HTTP/JWT/PostgreSQL (27/11/2026)

Le test `test_supplier_review_and_expiration_over_http_with_real_jwt_and_postgres`
ajoute deux opérations au parcours de bout en bout, sur des utilisateurs et
des enregistrements réellement persistés :

- un administrateur distinct du demandeur et de l'approbateur réalise une
  revue périodique via HTTP ; le test vérifie la réponse, l'identité du
  réviseur, la mise à jour de la prochaine date de revue et l'événement
  `REVIEW_SUPPLIER_ACCESS` ;
- un administrateur expire via HTTP une autorisation approuvée dont la date
  de fin est dépassée ; le test vérifie le statut `Expiré` persisté et
  l'événement `EXPIRE_SUPPLIER_ACCESS`.

Les opérations sont exécutées par `TestClient` avec de vrais JWT signés,
validés par `get_current_user`, et des sessions SQLAlchemy reliées à
PostgreSQL. Les opérations de revue et d'expiration ne reposent pas sur des
fonctions d'endpoint appelées directement.

**Résultats CI sur le SHA `395ac06ed1f32b1d11b777278f4b10a7dfdb1649`** —
workflow Push `46014328276` : **5/5 jobs réussis**.
- Backend : **542 passed, 58 skipped, 1 warning**.
- PostgreSQL Integration : **57 passed, 1 warning**.
- Frontend : build réussi.
- Compose Smoke : réussi.
- Production Runtime Smoke : réussi.

Le cycle HTTP/JWT/PostgreSQL des autorisations fournisseurs couvre maintenant
création, approbation par un tiers, revue périodique, révocation, expiration
et terminaison de la relation fournisseur-actif. Les refus RBAC de l'auditeur
sur les opérations de mutation sont également couverts en HTTP.

Les contrôles de concurrence/import CSV, pagination et équivalence export
restent au backlog. La Phase 0 demeure ouverte tant que les contrôles restants
ne sont pas vérifiés et documentés.


## Complément — concurrence et atomicité de l'import CSV (27/11/2026)

Le test `test_asset_csv_concurrent_http_import_is_atomic_with_real_postgres`
force deux requêtes HTTP authentifiées à franchir la prévalidation CSV avant
de poursuivre simultanément vers l'insertion. Les deux tentatives importent
la même référence d'actif.

Résultat vérifié sur PostgreSQL :
- une requête reçoit HTTP 201 et importe exactement un actif ;
- l'autre reçoit HTTP 409 après conflit sur la contrainte d'unicité ;
- un seul actif portant la référence est présent après les deux appels ;
- un seul événement d'audit `IMPORT` est conservé.

Ce test confirme que la prévalidation seule ne porte pas la garantie
d'unicité : la contrainte PostgreSQL reste l'arbitre final et le rollback
empêche une importation partielle en cas de conflit concurrent.

**Résultats CI sur le SHA `6556b63770120f8cbe7bd4951a3ad6791ccd741b`** —
workflow Push `46014867736` : **5/5 jobs réussis**.
- Backend : **542 passed, 59 skipped, 1 warning**.
- PostgreSQL Integration : **58 passed, 1 warning**.
- Frontend : build réussi.
- Compose Smoke : réussi.
- Production Runtime Smoke : réussi.

La couverture de concurrence de l'import est désormais prouvée pour la
collision de référence et l'atomicité d'une insertion concurrente. Les
prochains contrôles restent l'import de plusieurs lignes avec rollback
intégral après conflit, les doublons concurrents sur hostname/numéro de série
et la cohérence pagination/export sur les mêmes filtres. La Phase 0 reste
ouverte.


## Complément — exécution CI des tests CSV et rollback multi-lignes (27/11/2026)

Le contrôle précédent a révélé que le workflow PostgreSQL utilisait une liste
explicite de fichiers : le nouveau fichier de tests CSV n'était pas exécuté.
Le workflow `.github/workflows/backend-checks.yml` a donc été corrigé pour
inclure explicitement `backend/tests/test_asset_csv_import_postgres.py`.
Les deux tests CSV sont maintenant réellement exécutés dans le job PostgreSQL.

Dans ce fichier dédié :

- `test_asset_csv_concurrent_http_import_is_atomic_with_real_postgres`
  synchronise deux imports HTTP après prévalidation : une réponse 201, une
  réponse 409, un seul actif et un seul événement d'audit ;
- `test_asset_csv_multirow_conflict_rolls_back_every_insert` injecte une
  insertion concurrente après la prévalidation mais avant le flush. Le
  conflit sur la seconde ligne renvoie HTTP 409 ; la première ligne du lot
  est absente après rollback, l'actif concurrent est conservé et aucun
  événement d'import n'est créé.

**Résultats CI sur le SHA `7e285d97f8bfbfc19e1e0e6b9c209a4c666370b7`** —
workflow Push `46015748067` : **5/5 jobs réussis**.
- Backend : **542 passed, 60 skipped, 1 warning**.
- PostgreSQL Integration : **59 passed, 1 warning** ; les deux tests CSV
  apparaissent maintenant dans l'exécution effective.
- Frontend : build réussi.
- Compose Smoke : réussi.
- Production Runtime Smoke : réussi.

Le contrôle établit maintenant l'atomicité d'un import multi-lignes face à
un conflit concurrent et confirme que la CI exécute bien le fichier de tests.
Restent à vérifier les collisions concurrentes sur hostname/numéro de série
(si ces attributs doivent être uniques au niveau global), ainsi que la
cohérence pagination/export sur les mêmes filtres. La Phase 0 reste ouverte.


## Complément — équivalence pagination / export de l'inventaire (27/11/2026)

Le test `test_asset_inventory_pagination_matches_filtered_csv_export_over_http`
dans `backend/tests/test_asset_inventory_quality_postgres.py` vérifie les
routes HTTP réelles avec un JWT auditeur et PostgreSQL :

- trois actifs satisfont les filtres communs ; un actif d'un autre type et un
  actif retiré doivent être exclus ;
- les pages 1 et 2 retournent respectivement deux et un actifs, avec le même
  total et le même nombre de pages ;
- l'export CSV utilise exactement les mêmes filtres ;
- l'ensemble ordonné des références exportées est identique à la concaténation
  des références des pages ;
- l'autorisation d'export est exécutée et son action `EXPORT` est vérifiée.

**Résultats CI sur le SHA `e40286a02b3799793133732fa75d9721aa59a0d9`** —
workflow Push `46016290040` : **5/5 jobs réussis**.
- Backend : **542 passed, 61 skipped, 1 warning**.
- PostgreSQL Integration : **60 passed, 1 warning**.
- Frontend : build réussi.
- Compose Smoke : réussi.
- Production Runtime Smoke : réussi.

La cohérence pagination/export est maintenant démontrée pour un jeu de filtres
multi-critères, incluant l'exclusion des actifs retirés. Les prochains contrôles
restants portent notamment sur les collisions concurrentes hostname/numéro
de série (selon la règle métier retenue) et sur la couverture des filtres
combinés/limites de pagination. La Phase 0 reste ouverte.


## Complément — pagination/export PostgreSQL et inclusion effective dans la CI (27/11/2026)

Le test `test_asset_inventory_pagination_and_csv_export_use_identical_postgres_filters`
a été isolé dans `backend/tests/test_asset_inventory_pagination_postgres.py`
pour séparer les scénarios Cartographie des tests du cycle fournisseur.
Il crée des actifs dans PostgreSQL, appelle les routes HTTP avec un JWT
administrateur signé, puis compare les références des pages successives à
celles de l'export CSV appliquant les mêmes filtres.

Le test vérifie le total, le nombre de pages, le découpage, l'ordre stable,
l'égalité des références exportées et l'exclusion des actifs hors périmètre.
La CI PostgreSQL exécute désormais explicitement ce fichier dans
`.github/workflows/backend-checks.yml`. La revue a détecté et corrigé son
omission temporaire de la liste explicite après le déplacement du test :
le fichier présent dans le dépôt n'était pas automatiquement exécuté par
ce job.

**Résultats CI sur le SHA `2c0fbc80aa9a8cb1593d8c19075909b89892dedb`** :
- Workflow Push `46018133444` : **5/5 jobs réussis**.
- Workflow Pull Request `46018143207` : **5/5 jobs réussis**.
- Backend : **542 passed, 62 skipped, 1 warning**.
- PostgreSQL Integration : **61 passed, 1 warning**.
- Frontend : build réussi.
- Compose Smoke : réussi.
- Production Runtime Smoke : réussi.

La couverture Cartographie validée inclut maintenant la concurrence de
l'import CSV, le rollback complet d'un lot lorsqu'une ligne entre en conflit,
ainsi que l'équivalence des filtres et de l'ordre entre pagination et export.
Le contrôle ne démontre pas encore une recette avec les données et
l'infrastructure réelles de production. La Phase 0 reste ouverte.


## Complément — inventaire paginé, export CSV et atomicité des imports (27/11/2026)

### Pagination / export
Le test PostgreSQL HTTP `test_asset_inventory_pagination_and_csv_export_use_identical_postgres_filters`
vérifie sur une base migrée que :
- les deux pages successives couvrent exactement les trois actifs du jeu de
  données, sans doublon ni omission ;
- le total et le nombre de pages sont cohérents ;
- les mêmes filtres (recherche, type, direction, propriétaire, exclusion des
  actifs retirés) donnent le même ensemble et le même ordre dans la pagination
  et dans le CSV exporté.

Le contrôle RBAC HTTP du nouvel endpoint `/api/v1/assets/page` a également
été étendu : les rôles `auditor` et `executive` peuvent consulter une page
d'inventaire, tandis que `viewer` reçoit HTTP 403 avant toute requête SQL.

### Import CSV — concurrence et rollback
Les tests PostgreSQL HTTP couvrent désormais deux scénarios distincts :
- deux imports simultanés de la même référence, prévalidés avant concurrence :
  une réponse HTTP 201, une réponse HTTP 409, un seul actif persistant et un
  seul événement d'audit ;
- import multi-lignes dont la seconde référence est créée par une transaction
  concurrente après prévalidation : la confirmation retourne HTTP 409, la
  première ligne du lot est également annulée, l'actif concurrent reste intact
  et aucun événement d'import n'est enregistré.

Ces scénarios confirment l'atomicité du lot au niveau PostgreSQL et le rôle
des contraintes d'unicité comme protection finale contre les courses.

**Résultats CI sur le SHA `731e3940883784c25a470cf02000b992908d05ad`** :
les workflows Push `46018578677` et Pull Request `46018571336` sont
terminés avec **5/5 jobs réussis chacun**.
- Backend : **545 passed, 62 skipped, 1 warning**.
- PostgreSQL Integration : **61 passed, 1 warning**.
- Frontend build, Compose Smoke et Production Runtime Smoke : réussis.

Les tests PostgreSQL sont exécutés contre une base dédiée migrée par le
workflow. Les tests backend unitaires/API mockés ne doivent pas être confondus
avec ces tests d'intégration. Le résultat ne remplace pas une revue humaine de
la configuration de production ni une validation de restauration de sauvegarde.

### Prochaines vérifications
- étendre les scénarios de concurrence aux collisions hostname et numéro de
  série, si ces champs sont effectivement couverts par des contraintes uniques ;
- tester les limites hautes de pagination et les filtres combinés ;
- confirmer la cohérence des filtres entre l'interface frontend et les
  paramètres API, au-delà de l'équivalence backend pagination/export.
La Phase 0 reste ouverte.


## Complément — validation des bornes de pagination HTTP (27/11/2026)

Six cas HTTP supplémentaires vérifient que l'API `GET /api/v1/assets/page`
rejette avant toute requête SQL :
- `page=0` ;
- `page_size=0` et `page_size=201` (maximum contractuel : 200) ;
- une recherche de plus de 100 caractères ;
- un propriétaire de plus de 150 caractères ;
- une localisation de plus de 200 caractères.

Chaque cas doit retourner HTTP 422 et le mock de session confirme qu'aucun
appel `execute` n'est effectué. Ces tests complètent la couverture de
pagination/export PostgreSQL, les contrôles RBAC et la stabilité du tri.

**Résultats CI sur le SHA `78c241a4c85bb55ebfd883a4dc15b4d4fe099815`** :
workflows Push `46019594990` et Pull Request `46019604715` terminés avec
**5/5 jobs réussis chacun**.
- Backend : **551 passed, 62 skipped, 1 warning**.
- PostgreSQL Integration : **61 passed, 1 warning**.
- Frontend build : réussi.
- Compose Smoke : réussi.
- Production Runtime Smoke : réussi.

La validation CI prouve les contrôles automatisés dans les environnements
décrits par les workflows ; elle ne remplace pas les essais utilisateurs sur
l'environnement cible. La Phase 0 reste ouverte.


## Complément — contrôles HTTP des entrées CSV (27/11/2026)

Le fichier `backend/tests/test_asset_csv_import_http.py` ajoute sept
cas HTTP sur la route de prévisualisation de l'import CSV :

- rejet d'une extension non CSV (HTTP 415) ;
- rejet d'un fichier dépassant 1 Mio (HTTP 413) ;
- rejet d'un contenu qui n'est pas en UTF-8 valide (HTTP 400) ;
- rejet d'en-têtes dupliqués après normalisation des espaces (HTTP 422) ;
- rejet de plus de 5 000 lignes de données (HTTP 413) ;
- détection des doublons hostname sans distinction de casse ;
- détection des doublons de numéro de série sans distinction de casse.

Pour les contrôles de rejet précoces, les tests vérifient qu'aucune requête
SQL n'est déclenchée. Les deux tests de doublons vérifient que la prévisualisation
signale les erreurs et ne permet pas la confirmation de l'import.

**Limite de portée :** ces nouveaux tests utilisent une session DB mockée.
Ils valident le contrat HTTP, la validation des entrées et le comportement de
prévisualisation, mais ne prouvent pas les contraintes concurrentes réelles
sur hostname/numéro de série dans PostgreSQL. Les tests PostgreSQL d'atomicité
et de concurrence déjà recensés restent distincts.

**Résultats CI sur le SHA `f26f573e09a2789ee1eb9033dc6b736b6783ec8e`** :

- Workflow Push `46020812384` : **5/5 jobs réussis**.
- Backend : **558 passed, 62 skipped, 1 warning**.
- PostgreSQL Integration : **61 passed, 1 warning**.
- Frontend build : réussi.
- Compose Smoke : réussi.
- Production Runtime Smoke : réussi.

Le commit précédent `a0314ad` a correctement fait échouer le backend sur
une assertion de test qui attendait un séparateur dans le libellé de la limite
de lignes, alors que l'API retourne `5000`. L'assertion a été corrigée dans
`f26f573`, puis le workflow Push sur ce nouveau SHA a réussi. Cette correction
n'a pas modifié le comportement applicatif.

### Suite de la validation CSV

- Ajouter une validation PostgreSQL HTTP des collisions concurrentes de
  hostname et numéro de série, uniquement selon les contraintes réellement
  définies dans le schéma.
- Vérifier les cas CSV limites (BOM UTF-8, lignes vides, champs avec
  séparateurs/guillemets, fins de ligne CRLF) et leur cohérence preview/confirm.
- Contrôler que les erreurs de validation ne divulguent aucune donnée
  technique ou personnelle d'un actif préexistant.

La Phase 0 reste ouverte.


## Complément — cas limites CSV et non-divulgation des valeurs rejetées (28/11/2026)

La revue du parseur a confirmé que le décodage utf-8-sig accepte le BOM
UTF-8 et que le lecteur CSV traite les champs cités et les fins de ligne
CRLF. Des tests HTTP couvrent maintenant ces cas, y compris un champ cité
contenant un retour à la ligne, un séparateur dans une valeur et des lignes
vides ignorées. Le test confirme qu'une seule ligne de données est comptée
et que la prévisualisation reste importable.

La revue a également identifié une exposition évitable : la représentation
texte native d'une erreur Pydantic peut inclure la valeur fournie dans le CSV.
Le traitement a été corrigé pour ne retourner que les noms de champs et les
messages de validation, sans valeur d'entrée, URL de documentation ni contexte
de validation. Un test HTTP injecte une valeur sentinelle et vérifie qu'elle
n'apparaît pas dans la réponse.

**Résultats CI sur le SHA d1ff9aa206374e1471174cc8d82796968c54e9cf** :
- Workflow Push 46136144430 : **5/5 jobs réussis**.
- Workflow Pull Request 46136147673 : **5/5 jobs réussis**.
- Backend : **561 passed, 62 skipped, 1 warning**.
- PostgreSQL Integration : **61 passed, 1 warning**.
- Frontend build : réussi.
- Compose Smoke : réussi.
- Production Runtime Smoke : réussi.

Les commits intermédiaires 46fddda, c14d3c8 et 32eaf92 ont
déclenché des workflows dont le backend a échoué pendant la collecte des tests
à cause d'une erreur de syntaxe dans la nouvelle fixture paramétrée. La
syntaxe a été corrigée dans d1ff9aa, puis les deux workflows complets
(Push et Pull Request) ont réussi. Ces échecs intermédiaires ne sont pas
masqués dans le suivi.

**Limites restantes** : la cohérence des données importées entre preview et
confirm n'est pas encore démontrée par un test HTTP dédié avec le même fichier
et une comparaison exhaustive des objets persistés. Les collisions
concurrentes hostname/numéro de série ne doivent être testées comme conflits
bloquants que si une contrainte d'unicité correspondante est ajoutée après
validation de la règle métier. La Phase 0 reste ouverte.


## Complément — parcours HTTP prévisualisation puis confirmation PostgreSQL (28/11/2026)

Un test d'intégration supplémentaire couvre désormais le parcours complet avec
un même contenu CSV envoyé successivement aux endpoints HTTP
`/import/preview` et `/import/confirm`. Le test utilise un JWT signé,
un utilisateur administrateur dédié, une base PostgreSQL migrée et une
connexion indépendante pour vérifier les données persistées.

Le scénario contrôle :
- la prévisualisation HTTP (`can_import`, une ligne analysée et valide) ;
- les valeurs normalisées retournées pour la référence, le nom, le type,
  la criticité, le propriétaire et le commentaire ;
- la confirmation HTTP avec le même fichier et une réponse 201 ;
- l'égalité des champs persistés en PostgreSQL avec ceux présentés dans la
  prévisualisation ;
- la présence d'un seul événement d'audit `IMPORT` ;
- le nettoyage des données de test après exécution.

**Résultats CI sur le SHA 22a5a6e59badfbb1da0f6d6758a2ff9b1d43b860** :
- Workflow Push `46137828908` : **5/5 jobs réussis**.
- Workflow Pull Request `46137834416` : **5/5 jobs réussis**.
- Backend : **561 passed, 63 skipped, 1 warning**.
- PostgreSQL Integration : **62 passed, 1 warning**.
- Frontend build, Compose Smoke et Production Runtime Smoke : réussis.

Ce contrôle démontre la cohérence preview/confirm pour ce scénario nominal
sur PostgreSQL. Il ne remplace pas les scénarios négatifs (fichier modifié
entre preview et confirm, droits insuffisants, validation métier rejetée,
collision concurrente) déjà couverts partiellement ou restant à compléter.
La Phase 0 reste ouverte.


## Complément — réduction des colonnes chargées par le graphe Cartographie (28/11/2026)

La route `GET /api/v1/assets/graph` charge désormais explicitement uniquement
les colonnes nécessaires à la représentation des nœuds et des relations.
Les descriptions longues, identifiants techniques et autres attributs
d'inventaire non affichés par ce graphe ne sont plus transférés depuis
PostgreSQL pour chaque actif. Le tri des nœuds et des relations est rendu
déterministe avec des clés secondaires stables.

Cette optimisation ne limite pas artificiellement le nombre d'actifs et ne
modifie pas le contrat JSON de l'API. Elle réduit le volume de données ORM
chargé en mémoire ; elle ne constitue pas encore une mesure de performance
sur un volume représentatif. Un benchmark avec données synthétiques et une
mesure des plans SQL restent nécessaires avant toute décision de pagination
ou de plafonnement du graphe.

Le test `test_graph_returns_active_assets_and_relationships` vérifie que les
colonnes utiles restent sélectionnées et que les colonnes inutiles
(`description` de l'actif, `serial_number`, horodatage de création de la
relation) ne sont plus incluses dans les requêtes du graphe.

## 6. Complément — résultats et écarts actualisés (28 novembre 2026)

### P1-CARTO-007 — Synthèse de risques incomplète sur l'actif source

**Statut : corrigé et validé par CI complète sur le SHA 8065988 (5/5 jobs).**

La revue a montré que l'agrégat de risques de l'analyse d'impact ne prenait
en compte que les actifs dépendants et omettait les risques directement liés
à l'actif analysé. Le cas sans dépendant retournait également une synthèse
vide, même si l'actif source avait des risques associés.

La correction :
- agrège les risques de l'actif source et de ses dépendants transitifs ;
- déduplique un même risque lié à plusieurs actifs ;
- expose les risques de l'actif source dans la réponse ;
- les affiche dans le panneau d'analyse d'impact ;
- ajoute un test PostgreSQL couvrant un risque partagé source/dépendant et
  un risque lié uniquement à la source, ainsi qu'un test unitaire source-only.

Le workflow PR 46162054458 sur le SHA 80659881ee3a1111296f3e5f86c8af18db12a6ae est terminé avec 5/5 jobs réussis : Backend (596 passed / 64 skipped), PostgreSQL Integration (63 passed), Frontend, Compose Smoke et Production Runtime Smoke. Le workflow PR 46163329501 sur le SHA a4289248eaec66fde7ad4e3e1107e2598fb9704f est également vert 5/5.

### Matrice des preuves automatisées disponibles

- Application 1:N, réaffectation et suppression restrictive : PostgreSQL.
- Relations Asset↔Asset : prévention de cycles simples et concurrents,
  cycles à trois nœuds, retrait/réactivation : PostgreSQL.
- Liens Asset↔Risk : intégrité, agrégat de risques dédupliqué et audit.
- Fournisseurs : liens, autorisations, demandes et cycle de vie : PostgreSQL.
- Inventaire : pagination, filtres et export cohérents ; import CSV avec
  prévalidation, concurrence et rollback multi-lignes.
- RBAC HTTP : refus de mutation pour auditor, executive et viewer ; refus
  de lecture viewer sur les routes inventaire et relations.
- Interface : 3 parcours Playwright (admin, auditor, viewer) sur Chromium,
  Firefox et WebKit ; 24 tests navigateur au total sur le SHA a428924.

### Points restant à traiter avant sortie Phase 1

- Compléter la matrice route × rôle × opération et la matrice formelle
  des transitions de cycle de vie.
- Mesurer graphe/impact/qualité sur volumétrie synthétique représentative,
  avec plans SQL et latence.
- Définir la sémantique métier des types de relations orientées.
- Décider le modèle de responsabilité owner/custodian/direction seulement
  après identification du référentiel organisationnel CTF.
- Compléter les tests UI sur les parcours création, modification, import,
  export, liens risques/fournisseurs et gestion des erreurs.
- Vérifier la CI complète sur le HEAD final et effectuer la revue de
  non-régression automatisée.
### Mise à jour E2E — retrait logique (28 novembre 2026)

Le parcours administrateur vérifie désormais aussi le retrait logique d'un
actif : confirmation, requête DELETE et rechargement de l'inventaire.
Le test a été corrigé dans le commit a1874e0c890e3479e41585887584c301ba7a9163. Le workflow Push 46164007103 sur ce SHA est terminé avec 5/5 jobs réussis, dont Production Runtime Smoke. Le job Frontend confirme 24/24 tests Playwright réussis sur Chromium, Firefox et WebKit, retrait logique inclus.

### Organisation de la sortie de Phase 1

La sortie de développement de Phase 1 repose sur des preuves automatisées
et une revue de non-régression. La recette humaine et l'installation locale
ne sont pas attendues à ce stade : elles seront regroupées après la clôture
de l'ensemble des développements PGCC. Les validations qui nécessitent les
référentiels organisationnels, le réseau ou les secrets réels CTF restent
explicitement des gates de déploiement.