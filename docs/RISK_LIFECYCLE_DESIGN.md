# PGCC — Conception cible du cycle de vie GRC des risques

**Statut :** conception technique proposée, non encore implémentée  
**Date :** 28 novembre 2026  
**Branche :** `chore/phase0-stabilization`  
**Périmètre :** Phase 2 — évaluations, traitement, acceptation et historique des risques

Ce document formalise une cible additive à partir du modèle legacy actuel. Il ne vaut pas approbation de la méthodologie de risque ni des délégations de pouvoir de la CTF.

## 1. État de départ

Le modèle `Risk` conserve aujourd'hui un seul couple impact/vraisemblance, un score courant, un statut et un champ texte `treatment_plan`. Le score est calculé par le service selon la formule initiale impact × vraisemblance (échelle 1–5). Les migrations `0030` et `0031` protègent les invariants du score, l'unicité de référence et la conservation des actions.

Ces éléments restent compatibles avec les usages existants mais ne constituent pas un historique GRC complet. En particulier, le statut « Accepté » n'est pas une décision d'acceptation formelle.

## 2. Principes non négociables

1. **Migration additive :** conserver les colonnes legacy et les contrats API actuels pendant la transition.
2. **Aucune réécriture historique :** ne pas inventer une évaluation résiduelle, une justification ou une approbation qui n'existe pas dans les données.
3. **Historique append-only :** les événements métier ne sont ni modifiés ni supprimés par les opérations ordinaires.
4. **Calcul serveur :** les scores sont calculés à partir d'une méthodologie versionnée ; le client ne fournit jamais le score de référence.
5. **Traçabilité :** auteur, horodatage UTC, méthode, valeurs, justification et lien vers l'évaluation précédente sont conservés.
6. **Autorisation explicite :** les permissions d'évaluation, de traitement et d'acceptation sont distinctes ; les rôles et délégations sont configurables et testés côté API.
7. **Pas de seuil inventé :** les seuils, niveaux d'autorité, délais de revue et règles de séparation des tâches CTF ne sont pas codés en dur sans source organisationnelle approuvée.
8. **Compatibilité :** les anciens champs restent disponibles pour les écrans et intégrations jusqu'à migration complète des consommateurs.

## 3. Modèle cible proposé

### 3.1 RiskMethodology

Référentiel versionné d'une méthode de cotation.

Champs proposés :
- `id` UUID ;
- `code` et `version` uniques ;
- `name`, `description` ;
- `scale_definition` JSONB décrivant les échelles et leurs libellés ;
- `scoring_rule` JSONB ou identifiant de stratégie calculable côté serveur ;
- `status` (draft/active/retired) ;
- `created_at`, `created_by`, et métadonnées de publication.

Une méthodologie publiée est immuable. Toute évolution crée une nouvelle version. Aucune méthodologie ne devient active par défaut à partir de cette proposition ; le déploiement doit conserver la formule legacy tant qu'aucune méthode n'a été formellement choisie.

### 3.2 RiskAssessment

Évaluation ponctuelle, immuable, inhérente ou résiduelle.

Champs proposés :
- `id` UUID, `risk_id` FK RESTRICT ;
- `assessment_kind` (inherent/residual) ;
- `methodology_id` FK RESTRICT ;
- valeurs d'impact/vraisemblance et score calculé côté serveur ;
- `rationale`, `assessed_at`, `assessed_by` ;
- `supersedes_assessment_id` nullable pour chaîner les réévaluations ;
- `source_kind` et `source_reference` pour documenter une reprise legacy sans la présenter comme une nouvelle évaluation ;
- `created_at`.

Contraintes : plages validées par la méthodologie ; score cohérent ; référence de méthode obligatoire ; type d'évaluation explicite. Une évaluation résiduelle doit pouvoir référencer le traitement auquel elle se rapporte lorsque le workflow est en place.

### 3.3 RiskTreatmentDecision

Décision de traitement associée à un risque.

Champs proposés :
- `id`, `risk_id` FK RESTRICT ;
- `strategy_code` et `strategy_label` ;
- `decision`, `rationale`, `scope` ;
- `decided_by`, `decided_at`, `status` ;
- lien facultatif vers les actions correctives existantes ;
- dates de début/fin et historique de révision.

Les stratégies sont des valeurs référentielles/configurables. Les valeurs exactes et la terminologie CTF restent à valider avant activation.

### 3.4 RiskAcceptance

Enregistrement distinct d'acceptation d'un risque résiduel.

Champs proposés :
- `id`, `risk_id` FK RESTRICT ;
- `residual_assessment_id` FK RESTRICT obligatoire ;
- `justification` non vide ;
- `authority_user_id` FK vers l'autorité identifiée ;
- `effective_at`, `review_due_at`, `expires_at` ;
- `status` (proposed/approved/rejected/revoked/expired) ;
- `approved_by`, `approved_at`, et motif de décision.

Invariants : date de revue/expiration postérieure à la date d'effet ; aucune acceptation approuvée sans évaluation résiduelle, justification et autorité ; approbateur et initiateur distincts seulement si la règle de séparation des tâches CTF le requiert et après configuration. La durée maximale et les seuils d'autorité ne sont pas codés en dur.

### 3.5 RiskStatusEvent

Journal append-only des transitions du statut courant.

Champs proposés :
- `id`, `risk_id` FK RESTRICT ;
- `from_status`, `to_status`, `reason` ;
- `actor_id`, `occurred_at` ;
- `correlation_id`, `source` (API, import, migration contrôlée).

L'événement et la mise à jour du statut courant sont enregistrés dans la même transaction. Les événements de migration historique doivent être explicitement étiquetés comme importés et ne doivent pas fabriquer un ancien statut ou un acteur.

## 4. Transactions et règles de service

- Verrouiller la ligne Risk avec `SELECT FOR UPDATE` avant une mutation de cycle de vie.
- Vérifier les permissions, la validité des relations et les préconditions avant écriture.
- Insérer l'évaluation/décision/acceptation et l'événement d'audit dans une transaction atomique.
- En cas d'échec d'audit, rollback de l'ensemble.
- Ne pas supprimer les évaluations, décisions, acceptations ni événements ; corriger par nouvel enregistrement compensatoire.
- Le champ legacy `Risk.risk_level` reste synchronisé avec le score de référence affiché tant que les anciens consommateurs existent ; la règle de sélection de l'évaluation courante doit être explicite et testée.
- Les actions restent liées au risque et leurs FK restrictives sont conservées.

## 5. API cible (proposition)

- `GET /risks/{id}/assessments`
- `POST /risks/{id}/assessments`
- `GET /risks/{id}/treatment-decisions`
- `POST /risks/{id}/treatment-decisions`
- `POST /risks/{id}/acceptances` (création d'une proposition)
- `POST /risks/{id}/acceptances/{acceptance_id}/approve`
- `POST /risks/{id}/acceptances/{acceptance_id}/reject`
- `GET /risks/{id}/history`

Les opérations de lecture appliquent les permissions risques et les filtres de portée pertinents. Les mutations ont des permissions spécifiques et ne reposent pas uniquement sur le masquage UI.

## 6. Plan de migration et de livraison

1. Ajouter les tables et contraintes sans modifier/supprimer les champs legacy.
2. Ajouter des tests migration fresh install, upgrade depuis `0031`, downgrade sûr et round-trip.
3. Créer une méthodologie legacy identifiée comme telle, uniquement si les règles de migration sont déterministes ; ne pas marquer une méthode comme « approuvée CTF ».
4. Ne convertir les données legacy qu'en snapshots de provenance, sans générer artificiellement d'évaluations inhérentes/résiduelles ni d'acceptations.
5. Implémenter services transactionnels et tests concurrence/rollback/audit.
6. Exposer API et RBAC avant l'intégration UI.
7. Ajouter UI pour historique, évaluations, décisions et acceptations.
8. Ajouter Playwright pour les parcours positifs et négatifs.
9. Revalider KPI, rapports, actifs, fournisseurs, actions et documents.

## 7. Tests de sortie requis

- score calculé serveur, méthode/version persistée et méthode immuable ;
- évaluation inhérente et résiduelle distinctes, historisées et reliées ;
- impossibilité de modifier/supprimer un enregistrement historique par les routes ordinaires ;
- transitions concurrentes sérialisées et événements cohérents ;
- acceptation impossible sans évaluation résiduelle, justification, autorité et dates valides ;
- permissions testées sur chaque route et rôle ;
- rollback atomique si audit ou persistance échoue ;
- migrations fresh/upgrade/downgrade et non-régression des champs legacy ;
- rapports et tableaux de bord qui distinguent clairement scores legacy, inhérents et résiduels.

## 8. Décisions restant dépendantes d'une source CTF

Ces points ne bloquent pas la préparation du code générique, mais doivent rester configurables et inactifs tant qu'ils ne sont pas documentés :
- matrice de cotation officielle et libellés des échelles ;
- seuils de criticité et niveaux d'escalade ;
- autorités d'acceptation et délégations ;
- séparation des tâches et éventuels seuils d'approbation ;
- fréquence maximale de revue et durée de validité des acceptations ;
- stratégies de traitement autorisées et responsabilités organisationnelles.

**Conclusion :** cette conception permet de développer un workflow GRC traçable sans casser les modules existants ni figer arbitrairement des règles métier propres à la CTF. Elle constitue la base de réalisation de l'issue #8, sous réserve de garder les paramètres organisationnels non approuvés inactifs.
