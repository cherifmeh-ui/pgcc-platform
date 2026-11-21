# Revue du modèle de données — Cartographie des actifs

**Périmètre :** modèle Asset, relations de dépendance, liens vers les risques et applications.  
**Référence :** branche `chore/phase0-stabilization`, migrations `0006` à `0009`.

## 1. Modèle logique validé

```mermaid
erDiagram
    APPLICATION ||--o{ ASSET : "application_id"
    ASSET ||--o{ ASSET_RELATIONSHIP : "source"
    ASSET ||--o{ ASSET_RELATIONSHIP : "target"
    ASSET ||--o{ ASSET_RISK_LINK : "asset_id"
    RISK ||--o{ ASSET_RISK_LINK : "risk_id"
```

- `Asset` est le référentiel central d'inventaire.
- `AssetRelationship` représente les relations orientées entre actifs.
- `AssetRiskLink` matérialise la relation N:N entre actifs et risques.
- `Application` reste le catalogue applicatif existant; plusieurs actifs peuvent référencer une application.

## 2. Règles d'intégrité

| Domaine | Règle |
|---|---|
| Identité | UUID technique et référence métier obligatoire |
| Référence | Unicité SQL actuelle sur la valeur exacte |
| Application | FK avec suppression restrictive; cardinalité N actifs vers 1 application |
| Relations | Source et cible obligatoires, différentes, FK restrictives |
| Relations dupliquées | Unicité sur source, cible et type |
| Dépendances | Le backend bloque les nouveaux cycles `depends_on` |
| Risques | Unicité d'une paire actif/risque |
| Retrait | Retrait logique via `retired_at`, pas de suppression physique d'actif dans l'API |
| CIA | Valeurs contrôlées par contraintes SQL et validation Pydantic |
| Cycle de vie | Valeurs contrôlées par contrainte SQL et validation Pydantic |

## 3. Indexation

La migration `0009_asset_inventory_filter_indexes` ajoute des index sur les colonnes utilisées par les filtres d'inventaire : propriétaire, localisation, cycle de vie, criticité et classification. Les index existants sur référence, nom, application, direction, hostname et numéro de série sont conservés.

## 4. Politique de liaison inter-modules

- Lecture de la cartographie : `assets:read`.
- Création/modification/retrait : permissions dédiées `assets:create/update/delete`.
- Export de données techniques : `assets:export`, réservé aux rôles Admin et Auditor.
- Lecture des risques depuis la cartographie : `risks:read` en plus de `assets:read`.
- Modification d'une liaison actif/risque : `assets:update` ET `risks:update`.
- Les champs de risque ne sont inclus dans l'analyse d'impact que si `risks:read` est accordée.

## 5. Points à traiter avant l'intégration Fournisseurs

1. **Normalisation de référence :** la contrainte SQL actuelle est sensible à la casse alors que l'import CSV détecte les références sans tenir compte de la casse. Une normalisation uniforme et un index unique fonctionnel nécessitent d'abord un audit des doublons historiques.
2. **Hostname et numéro de série :** la détection de doublons CSV est une validation applicative. Il n'existe pas encore de contraintes uniques SQL sur ces champs; il faut confirmer les règles d'unicité réelles avec les équipes d'exploitation avant de les imposer.
3. **Responsable et direction :** `owner`, `custodian` et `direction` sont encore des chaînes libres. Le futur référentiel Organisation/Utilisateurs devra être relié par clés étrangères dans une migration progressive, avec correspondance et reprise contrôlées.
4. **Historique métier :** le journal de sécurité trace les opérations, mais le modèle n'est pas encore un historique versionné complet des changements de chaque actif.
5. **Suppression des risques :** la FK `AssetRiskLink.risk_id` utilise désormais `ON DELETE RESTRICT`. Avant de généraliser l'archivage, confirmer si la suppression d'un risque doit être bloquée dès qu'il est lié à des actifs afin de préserver la traçabilité métier.
6. **Relations orientées :** les types de relation sont stockés en texte contrôlé; la sémantique source/cible doit être documentée et normalisée avant l'ajout de relations fournisseurs.

## 6. Décision d'architecture

Le modèle actuel est suffisamment stable pour achever la tranche Cartographie, sous réserve de conserver les points de vigilance ci-dessus comme prérequis de conception du module Fournisseurs. Le module Fournisseurs devra référencer les actifs et contrats par relations explicites, et ne pas introduire de champs fournisseurs libres dans `Asset`.

## 7. Chaîne de migrations

`0006_asset_inventory` → `0007_asset_risk_links` → `0008_asset_application_cardinality` → `0009_asset_inventory_filter_indexes`.

Les migrations doivent être vérifiées sur une base de test vide et sur une copie représentative de la base existante avant tout déploiement. Le downgrade `0008` peut échouer si une application possède plusieurs actifs; ne pas l'exécuter sans contrôle des données.


## 8. Protection de la traçabilité Actif–Risque

La suppression physique d'un risque est refusée tant qu'il possède des associations avec des actifs. La FK `asset_risk_links.risk_id` est configurée en `ON DELETE RESTRICT` (migration `0010_asset_risk_restrict_delete`). La suppression d'une association doit passer par l'endpoint explicite de dissociation, autorisé uniquement avec `assets:update` et `risks:update`. Cela évite la disparition silencieuse du contexte de cartographie.
