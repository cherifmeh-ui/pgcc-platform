# PGCC — Master Roadmap

**Version:** 1.0  
**Date:** 21 novembre 2026  
**Branch:** `chore/phase0-stabilization`  
**Status:** Baseline de pilotage — roadmap proposée, à affiner après revue de maturité.

## Vision

Construire une plateforme GRC intégrée, sécurisée, traçable et exploitable, avec une architecture modulaire monolithique, une source de vérité par domaine, des workflows contrôlés, des KPI fondés sur les données et une IA locale/contrôlée.

## Règles de pilotage

- Une phase n'est clôturée qu'après validation de ses critères d'acceptation.
- Présence de fichiers ou endpoints ne signifie pas fonctionnalité validée.
- Les tests CI ne remplacent pas les validations runtime, intégration, sécurité et métier.
- Toute évolution doit préserver les modules existants et suivre migrations, tests, permissions et documentation.
- Les décisions de risque, conformité, validation et clôture restent humaines et traçables.
- Ne pas fusionner dans `main` sans revue et approbation explicites.

## Roadmap à 9 phases

| Phase | Domaine | Scope principal | Critères de sortie |
|---|---|---|---|
| 0 | Stabilisation & fondations | Architecture, CI, sécurité, migrations, tests, Docker, revue PR | CI sur HEAD, builds propres, démarrage sur DB neuve et DB existante documenté, migrations cohérentes, tests d'intégration de base, revue de sécurité, PR prête à revue |
| 1 | Cartographie SI | Inventaire actifs, import/export, pagination, filtres, relations, dépendances, impact, liens risques | Parcours CRUD/import/export validés, permissions, intégrité relationnelle, analyse d'impact vérifiée, tests et documentation |
| 2 | Gestion des risques | Méthodologie, registre, scoring, traitement, résiduel, acceptation, historique, liens transverses | Cycle de vie complet testé, règles de score documentées, acceptation contrôlée, historique fiable, relations actifs/tiers/contrôles/actions |
| 3 | TPRM | Fournisseurs, services, contrats, clauses, évaluations, accès, revues, risques, tendances | Workflow fournisseur complet, règles d'accès, échéances, snapshots et indicateurs vérifiés, tests API et UI |
| 4 | Conformité & contrôles | Référentiels, applicabilité, évaluation, maturité, preuves, écarts, SoA | Dataset source/licence validés, évaluations versionnées, preuves contrôlées, SoA exportable, écarts reliés aux actions |
| 5 | Audits | Programme, mission, périmètre, constats, recommandations, preuves, suivi | Cycle audit complet, séparation constat/action/clôture, permissions, rapports, tests |
| 6 | Gouvernance & workflows | PSSI/politiques, objectifs, rôles, unités, décisions, approbations, notifications | Workflow configurable ou documenté, validations/audit, échéances et notifications fiables |
| 7 | Pilotage & reporting | Dashboards RSSI/PDG, KPI GRC consolidés, tendances, rapports PDF/CSV/XLSX | Définitions KPI, permissions, périodes, exports vérifiés, rapports reproductibles et tests |
| 8 | Automatisation, IA & production | Alertes, intégrations, assistant contextuel, monitoring, sauvegardes, durcissement, déploiement | IA sourcée et permission-aware, automatisations auditées, sauvegarde/restauration testée, observabilité et runbooks, sécurité de production |

## Dépendances et ordre recommandé

1. Phase 0 doit sécuriser le socle avant clôture.
2. Phase 1 cartographie fournit le contexte aux risques, contrôles, fournisseurs et audits.
3. Phase 2 risques constitue le registre central utilisé par les domaines transverses.
4. Phase 3 TPRM s'appuie sur fournisseurs, actifs, risques, documents et actions.
5. Phase 4 conformité s'appuie sur documents/preuves, actions et risques.
6. Phase 5 audits réutilise risques, contrôles, actifs, fournisseurs, documents et actions.
7. Phase 6 gouvernance formalise décisions et workflows transverses.
8. Phase 7 pilotage consolide les modules validés; les dashboards ne doivent pas masquer les lacunes de qualité des données.
9. Phase 8 automatise seulement les processus validés et prépare l'exploitation.

## État initial au 21/11/2026

| Phase | Statut initial | Commentaire |
|---|---|---|
| 0 | En cours | PR #1 Draft; CI visible verte, validations runtime et revue complète restent ouvertes |
| 1 | MVP présent, validation incomplète | Module assets et documentation existent; revue fonctionnelle complète requise |
| 2 | Présent, maturité à établir | Risks endpoint/model/view présents; lifecycle et historique formel à auditer |
| 3 | Développé en grande partie, validation à établir | Supplier module, overview, snapshots, tendances et concentration présents dans le dépôt; revue end-to-end requise |
| 4 | Partiel | Compliance endpoint, modèles ISO et assessments/evidence présents; couverture et workflow de conformité à valider |
| 5 | Non identifié comme module autonome | Aucun endpoint/model/view Audit dédié repéré dans l'inventaire initial |
| 6 | Partiel/non identifié | Auth/RBAC présent; gouvernance organisationnelle et workflows formels à inventorier |
| 7 | Partiel | Dashboard et reporting endpoint présents; consolidation GRC et exports doivent être audités |
| 8 | Partiel | IA/RAG présent; automatisation et readiness production restent à évaluer |

Ces statuts sont des estimations de présence du code, non des validations de fonctionnalités.

## Jalon actuel

**J0 — Revue de maturité et clôture Phase 0.** Avant d'élargir le périmètre, établir l'inventaire des modules, confirmer le HEAD et CI, examiner les migrations, exécuter les tests runtime disponibles, documenter les écarts et prioriser les corrections.

## Definition of Done commune

- API et UI cohérentes, validation serveur et permissions testées.
- Migrations idempotentes/compatibles selon la stratégie retenue et documentées.
- Tests unitaires et intégration pertinents.
- Aucun secret, données sensibles ou fichiers temporaires dans le dépôt.
- Audit trail pour opérations métier sensibles.
- Documentation API, modèle de données et utilisateur mise à jour.
- CI verte sur le commit cible.
- Revue non-régression et décision de jalon documentée.

## Prochaines tâches

1. Revue détaillée du code et des tests de chaque module.
2. Revue migrations et stratégie de baseline Alembic.
3. Vérification CI sur le HEAD réel et Docker/runtime.
4. Matrice maturité/écarts/priorités.
5. Backlog issues par phase avec critères d'acceptation.
