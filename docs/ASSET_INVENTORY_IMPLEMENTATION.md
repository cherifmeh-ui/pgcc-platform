# PGCC — Implémentation du socle Cartographie

**État :** MVP initial implémenté — validation CI effectuée  
**Branche :** `chore/phase0-stabilization`

## 1. Périmètre livré

- Modèles SQLAlchemy `Asset` et `AssetRelationship`.
- Migration Alembic `0006_asset_inventory`.
- API REST versionnée sous `/api/v1/assets`.
- Permissions backend `assets` : lecture réservée Admin, Executive et Auditor ; création, modification et retrait réservés Admin.
- Journalisation des créations, modifications, retraits et relations.
- Vue frontend `AssetsView.vue`, filtres, fiche actif, CRUD et gestion initiale des relations.
- Navigation et route protégée par permissions.
- Tests de validation des schémas et RBAC.

## 2. API

| Méthode | Endpoint | Fonction |
|---|---|---|
| GET | `/api/v1/assets/` | Liste paginée, recherche et filtres |
| POST | `/api/v1/assets/` | Créer un actif |
| GET | `/api/v1/assets/{asset_id}` | Consulter un actif |
| PATCH | `/api/v1/assets/{asset_id}` | Modifier un actif |
| DELETE | `/api/v1/assets/{asset_id}` | Retrait logique / archivage |
| GET | `/api/v1/assets/{asset_id}/relationships` | Lister les relations |
| POST | `/api/v1/assets/{asset_id}/relationships` | Ajouter une relation |

## 3. Intégration au catalogue Applications existant

Le catalogue `Application` reste inchangé. Le champ facultatif `application_id` sur Asset permet d'enrichir une application existante avec des informations d'inventaire. La relation est protégée par FK et restriction de suppression.

Le MVP ne transforme pas automatiquement les applications existantes en actifs : une conversion de données devra être préparée, validée et exécutée séparément, afin de ne pas créer de doublons ou modifier la donnée historique sans décision.

## 4. Garanties

- Référence d'actif unique.
- Valeurs contrôlées pour type, criticité, classification CIA et cycle de vie.
- Relations auto-référentes interdites.
- Relations dupliquées (source, cible, type) interdites.
- Suppression physique non proposée dans l'API : retrait logique.
- Permissions vérifiées côté backend.
- Migrations et tests CI.

## 5. Limites du MVP et prochaines étapes

- Vue graphique du graphe et analyse d'impact : à développer.
- Import CSV avec validation, prévisualisation et rapport d'erreurs : à développer.
- Liens explicites avec risques, contrôles, documents et fournisseurs : à développer.
- Historique détaillé des modifications métier et workflow de validation de criticité : à développer.
- Pagination UI et compteur total : à améliorer.
- Revue de sécurité spécifique des données techniques (IP, hostname, serial) et règles de visibilité : à poursuivre.
- Tests API avec base PostgreSQL de CI et tests migration upgrade/downgrade : à compléter.

## 6. Validation

Le workflow GitHub Actions `Backend checks` (compilation Python, tests unitaires et build frontend) a été observé en succès sur la version initiale de ce MVP. Les derniers changements de permissions et tests doivent être confirmés par le workflow déclenché sur le commit courant.


## 7. Intégration au registre des risques — première tranche

- Migration `0007_asset_risk_links` et modèle `AssetRiskLink` : liaison explicite many-to-many Asset/Risk.
- API : `GET/POST /api/v1/assets/{asset_id}/risks`, `DELETE /api/v1/assets/{asset_id}/risks/{risk_id}`.
- API inverse de consultation : `GET /api/v1/risks/{risk_id}/assets`.
- Les associations comportent un contexte facultatif, auteur et date; mutations journalisées.
- Migration `0008_asset_application_cardinality` retire la contrainte 1:1 entre Asset et Application; une application peut désormais être associée à plusieurs actifs techniques.
- Les routes existantes de risques et actifs sont conservées. Les tests de schéma sont étendus. La validation runtime/CI reste à confirmer sur le HEAD courant.


## Interface d'intégration — implémentation initiale

- `AssetsView.vue` : panneau Relations affiche désormais les risques associés, contexte, liaison et dissociation (si permission update); le chargement est conditionné à la permission de lecture Risques.
- `RisksView.vue` : action dédiée permet d'afficher les actifs associés à un risque via l'endpoint inverse; affichage des caractéristiques essentielles et du contexte.
- Les fonctions existantes de CRUD actifs/risques, matrice, export CSV, assistant IA et plan d'action sont conservées.
- Les validations frontend build et CI sur le commit UI sont en cours.


## Détection des cycles dans les dépendances

L'API refuse désormais une nouvelle relation `depends_on` lorsqu'elle créerait un cycle dans le graphe de dépendances. Le contrôle parcourt les relations existantes et vérifie si la cible atteint déjà la source. Les autres types de relations restent libres de représenter des liens bidirectionnels ou non hiérarchiques. Des tests unitaires couvrent le cycle détecté, une branche sans cycle et un graphe préexistant cyclique.


## Analyse d'impact transitive — première version

L'endpoint `GET /assets/{asset_id}/impact` retourne l'actif source, les actifs qui en dépendent transitivement, leur distance dans le graphe, les informations d'identification/criticité et les risques explicitement liés à chaque actif impacté. L'analyse s'appuie uniquement sur les relations `depends_on`; les autres types de relations ne sont pas interprétés comme une dépendance directionnelle.

L'interface Cartographie expose une action **Impact** sur chaque actif et affiche les résultats, la distance et les risques associés. La fonction de parcours utilise un ensemble visité pour éviter les doublons et terminer même si des cycles préexistants sont rencontrés.

Tests unitaires ajoutés : chaîne de dépendances, actif non lié, chemins multiples et cycle préexistant.

- Les risques associés dans la réponse d'analyse d'impact ne sont retournés que si l'utilisateur dispose de `risks:read`; l'analyse des actifs reste disponible avec `assets:read`.


## Graphe des dépendances — première intégration

- API `GET /assets/graph` expose les actifs non retirés comme nœuds et les relations explicites comme arêtes.
- Les relations dont une extrémité n'appartient pas à l'inventaire actif sont exclues du graphe.
- L'interface Cartographie fournit un panneau de graphe avec recherche, filtre par type de relation, inventaire des nœuds et liste des relations. Cette première version est une vue structurée, pas encore une visualisation géométrique interactive de type force-directed.
- Tests API ajoutés pour un graphe non vide et un inventaire vide.

- La suppression d'une relation d'actif est désormais disponible via `DELETE /assets/{asset_id}/relationships/{relationship_id}`, avec vérification que la relation concerne bien l'actif fourni, permission `assets:update`, journalisation et test API.

- L'interface affiche maintenant une visualisation SVG circulaire du graphe avec nœuds colorés par criticité, relations, recherche et filtre par type. Il s'agit d'une disposition déterministe, non d'un algorithme de placement automatique avancé.
- Les relations peuvent être supprimées depuis le panneau de dépendances; la suppression est journalisée et limitée à une relation associée à l'actif sélectionné.
- Les tests ajoutés ont été corrigés après CI : les fixtures utilisent désormais des UUID valides.
