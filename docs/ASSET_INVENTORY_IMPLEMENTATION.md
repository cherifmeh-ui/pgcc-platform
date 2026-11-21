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
