# Phase 1 — Cartographie du SI : état initial et plan d'exécution

**Date du checkpoint :** 27 novembre 2026  
**Branche de travail :** `chore/phase0-stabilization`  
**HEAD de départ Phase 1 :** `f4cce2ac69ee4f8f9beb58ab93fc089517a64459`  
**Statut :** Phase 1 démarrée — audit initial du code et cadrage des corrections.  
**Hypothèse de pilotage :** les validations humaines Phase 0 sont supposées conformes pour permettre le démarrage du développement ; leur preuve et la clôture administrative restent à enregistrer séparément.

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

- `docs/TARGET_DATA_MODEL.md` décrit encore une relation Application↔Asset optionnelle 1:1.
- `docs/ASSET_INVENTORY_IMPLEMENTATION.md` indique que la migration `0008_asset_application_cardinality` a supprimé cette cardinalité 1:1 : une application peut être associée à plusieurs actifs techniques.
- Le modèle Asset contient un `application_id` facultatif et une FK ; aucun indice de contrainte unique n'apparaît dans le modèle actuel.
- **Action :** confirmer la migration physique et mettre à jour le modèle cible en relation Application 1:N Asset. Ne pas modifier les données ni le schéma pour corriger une simple contradiction documentaire.

### P1-CARTO-002 — Responsabilités d'actifs encore textuelles

- Le modèle actuel stocke `owner`, `custodian` et `direction` comme chaînes de caractères.
- Le modèle cible mentionne `owner_user_id`, `owner_unit_id`, `custodian_user_id`.
- Les valeurs textuelles facilitent l'import initial, mais fragilisent la qualité, les affectations, les filtres et la traçabilité des changements de responsable.
- **Action :** inventorier les modèles User et organisation existants, les règles de périmètre et les données réelles avant toute migration. Étudier une transition additive avec références structurées, sans supprimer les champs historiques prématurément. Ne pas inventer de module OrganizationUnit s'il n'existe pas.

### P1-CARTO-003 — Endpoints graphe et qualité à évaluer en charge

- `GET /assets/graph` charge tous les actifs actifs et toutes les relations avant filtrage en mémoire.
- `GET /assets/quality` charge tous les actifs actifs pour calculer les compteurs.
- L'impact charge les relations de dépendance pour parcourir le graphe.
- **Action :** définir des seuils de volumétrie, examiner les plans SQL et ajouter des tests de volumétrie/latence. Envisager agrégations SQL, filtrage serveur ou pagination/limites explicites si les mesures le justifient.

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
- [ ] Réconciliation des documents de modèle et d'implémentation.

### Jalon 2 — Intégrité métier et responsabilités
- [ ] Tester et corriger les transitions de cycle de vie.
- [ ] Valider Asset↔Application et Asset↔Risk sur PostgreSQL.
- [ ] Valider Asset↔Asset, cycle, doublons et concurrence.
- [ ] Valider les interactions fournisseurs et demandes d'accès.
- [ ] Décider le modèle de responsabilité (User/Unité) sur la base des entités existantes.

### Jalon 3 — Inventaire et opérations de masse
- [ ] Tests API complets pagination/filtres/export.
- [ ] Tests d'import CSV : encodage, limites, doublons, concurrence, atomicité et audit.
- [ ] Vérification de l'absence de fuite de données dans les exports.
- [ ] Vérification de la performance sur volumétrie représentative.

### Jalon 4 — Graphe et analyse d'impact
- [ ] Tests de parcours multi-niveaux, chemins multiples, actifs retirés et cycles.
- [ ] Définir précisément la sémantique des relations orientées.
- [ ] Valider la déduplication des risques et les agrégats.
- [ ] Vérifier l'accès aux informations fournisseurs et risques selon permissions.
- [ ] Tester les limites de volumétrie et la stabilité de l'interface.

### Jalon 5 — Validation et clôture
- [ ] Tests unitaires, API et PostgreSQL sur les scénarios pertinents.
- [ ] Tests frontend et parcours utilisateur.
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

