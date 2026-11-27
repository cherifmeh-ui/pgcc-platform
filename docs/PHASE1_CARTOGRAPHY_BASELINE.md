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
