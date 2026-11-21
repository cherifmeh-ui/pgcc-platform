# PGCC — Interactions entre modules

**Statut :** Référence fonctionnelle et technique  
**Version :** 1.0  
**Date :** 21 novembre 2026

## 1. Règle générale

Les modules PGCC sont intégrés autour d'une source de vérité commune. Un module crée et maintient son objet métier ; les autres le référencent et ajoutent leur contexte. Les opérations transversales sont réalisées via des services métier, transactions, contrats API et événements internes documentés.

## 2. Matrice des interactions

| Module source | Module cible | Interaction |
|---|---|---|
| Cartographie | Risques | Un actif peut être affecté à un ou plusieurs risques ; l'analyse de risque peut prendre en compte sa criticité et ses dépendances. |
| Cartographie | Conformité | Les actifs et périmètres peuvent être associés aux contrôles pertinents. |
| Cartographie | Documents | Les fiches, schémas, configurations et preuves sont référencés. |
| Cartographie | Fournisseurs | Les actifs ou services peuvent être fournis, hébergés ou maintenus par un tiers. |
| Cartographie | Audits | Le périmètre d'audit référence des actifs et leurs relations. |
| Risques | Actions | Un risque peut générer plusieurs actions de traitement ; une action peut référencer un risque selon les règles existantes. |
| Conformité | Actions | Un contrôle non conforme ou partiellement conforme peut générer une action corrective. |
| Audits | Actions | Un constat peut produire une ou plusieurs actions ; le statut de l'action ne clôt pas automatiquement le constat. |
| Fournisseurs | Risques | Évaluation tiers, criticité, accès et services alimentent le risque fournisseur. |
| Fournisseurs | Cartographie | Les services et accès fournisseurs sont associés aux actifs concernés. |
| Fournisseurs | Documents | Contrats, clauses, questionnaires et attestations sont conservés comme preuves. |
| Pilotage | Tous | Les KPI sont calculés à partir des données autorisées et des règles de définition. |
| IA | Tous | L'assistant consulte les données selon les permissions et fournit des suggestions, sans modifier les objets métier de façon autonome. |

## 3. Flux métier de référence

### 3.1 Cartographie → Risques → Actions

1. Un actif est créé ou importé.
2. Le propriétaire et la criticité sont renseignés.
3. Les dépendances sont enregistrées.
4. Les risques sont associés à l'actif ou créés depuis le contexte.
5. Le risque est évalué et traité.
6. Les actions sont créées, suivies et vérifiées.
7. Le dashboard actualise les indicateurs.

### 3.2 Conformité → Écart → Action corrective

1. Un contrôle est évalué.
2. Une preuve est liée à l'évaluation.
3. L'écart est identifié et documenté.
4. Une action corrective est créée et reliée au contrôle.
5. L'action suit son workflow.
6. La vérification d'efficacité est réalisée.
7. L'évaluation du contrôle est mise à jour par une personne habilitée, avec historique.

### 3.3 Audit → Constat → Action → Vérification

1. Une mission d'audit définit le périmètre.
2. Les constats sont enregistrés.
3. Le constat est relié aux risques, actifs et contrôles concernés.
4. Le plan d'action est établi.
5. Les preuves de réalisation sont ajoutées.
6. La vérification d'efficacité est documentée.
7. La clôture du constat est une décision distincte, selon les règles d'audit.

### 3.4 Fournisseur → Évaluation → Risque → Revue

1. Le fournisseur et ses services sont référencés.
2. Le contrat et les clauses de sécurité sont documentés.
3. Une évaluation initiale ou périodique est réalisée.
4. Les accès sont recensés et approuvés.
5. Les risques sont associés et traités.
6. Les échéances de contrat, d'accès et de revue déclenchent des alertes.
7. La revue périodique est conservée dans l'historique.

### 3.5 Données métier → KPI → Rapport

1. Le service KPI interroge les données persistées.
2. Les définitions, filtres, période et version de calcul sont appliqués.
3. Les résultats sont présentés au dashboard.
4. Un rapport utilise les mêmes données et règles.
5. La génération, les paramètres et l'utilisateur sont journalisés.
6. Les exports sont soumis aux permissions et règles de confidentialité.

## 4. Cartographie et analyse d'impact

Le graphe de dépendances doit permettre de répondre, avec les données enregistrées :
- Quels processus dépendent de cet actif ?
- Quelles applications et infrastructures sont en aval ?
- Quels fournisseurs interviennent sur cet actif ?
- Quels risques sont associés ?
- Quels contrôles et preuves sont pertinents ?
- Quelles actions ou audits concernent cet actif ?
- Quel est l'impact potentiel d'une panne ou d'une compromission ?

L'analyse d'impact doit distinguer :
- Relations directes et indirectes.
- Dépendances opérationnelles et techniques.
- Niveau de criticité connu et source.
- Données manquantes ou relations non vérifiées.

Aucune criticité calculée ne doit être présentée comme validée si elle n'est qu'une estimation.

## 5. Services et contrats d'intégration

Les interactions doivent passer par des services métier dédiés, par exemple :
- AssetService : gestion des actifs et dépendances.
- RiskService : évaluation et traitement.
- ComplianceService : évaluations et preuves.
- ActionService : workflow, liens et vérifications.
- SupplierService : tiers, contrats, évaluations et accès.
- ReportingService : KPI et rapports.
- AuditService : journalisation métier et événements.

Les noms sont indicatifs et doivent s'adapter à l'organisation existante.

## 6. Événements internes envisagés

Les événements internes sont des notifications de domaine ; ils ne nécessitent pas un broker externe au MVP.

- asset.created / asset.updated / asset.retired
- asset.relationship.created / asset.relationship.updated
- risk.assessed / risk.treatment.updated
- control.assessed
- action.created / action.status_changed / action.verified
- audit.finding.created / audit.finding.closed
- supplier.assessed / supplier.contract.expiring / supplier.access.review_due
- document.expired
- report.generated

Chaque événement doit contenir un identifiant de corrélation et une référence d'objet, sans secrets ni données sensibles inutiles. Les événements ne remplacent pas les transactions ni les contrôles d'accès.

## 7. Notifications

Notifications possibles :
- échéance d'action ;
- action en retard ;
- revue d'actif ;
- actif sans propriétaire ;
- contrat proche d'expiration ;
- revue fournisseur due ;
- accès fournisseur expirant ou non revu ;
- preuve expirée ;
- écart de conformité nécessitant action ;
- rapport périodique à produire.

Les règles, destinataires et fréquence doivent être configurables et éviter les notifications répétitives inutiles.

## 8. Permissions et confidentialité

- Chaque interaction applique les permissions de l'utilisateur.
- Les rapports ne doivent pas contourner les permissions des données source.
- Les documents sont accessibles uniquement via un mécanisme autorisé.
- Les exports sont journalisés et limités.
- Les dashboards exécutifs agrègent les informations selon leur audience ; ils ne doivent pas exposer des détails sensibles non nécessaires.

## 9. Transactions, cohérence et erreurs

- Les opérations qui créent simultanément plusieurs objets métier doivent utiliser une transaction.
- Une création d'action depuis un constat doit éviter un constat sans action partiellement créé si l'opération échoue.
- Les liens doivent être validés : objet existant, type autorisé, permission suffisante.
- Les échecs d'intégration doivent être explicites et journalisés.
- Les suppressions d'objets référencés doivent être empêchées ou remplacées par archivage/retrait.

## 10. Ordre de développement

1. Documentation cible et compatibilité avec les modèles existants.
2. Cartographie : modèles, migration, services, API, tests, RBAC et audit.
3. Interface de cartographie : liste, fiche actif, relations et filtres.
4. Liens progressifs avec risques, applications, documents et contrôles.
5. Fournisseurs : référentiel, contrats, évaluations, accès.
6. Pilotage : définitions KPI, dashboard, rapports.
7. Notifications et automatisation.
8. IA contextualisée et assistance.

Chaque étape doit être intégrée sans casser les routes, modèles, migrations, tests ou vues déjà en place.
