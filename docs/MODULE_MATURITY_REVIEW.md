# PGCC — Revue initiale de maturité des modules

**Date:** 21 novembre 2026  
**Branche:** `chore/phase0-stabilization`  
**Statut:** Inventaire initial sur la base de la structure du dépôt et de la documentation. Les statuts ne constituent pas une validation fonctionnelle.

## Méthode

- **Présent dans le dépôt:** modèles, endpoints, services, vues ou tests repérés.
- **Partiel:** une base de code existe, mais la complétude ou les validations ne sont pas démontrées.
- **À vérifier:** une revue ciblée, des tests ou une validation runtime sont nécessaires.
- **Absent/non identifié:** aucun module dédié repéré lors de l'inventaire initial; cela ne prouve pas l'absence de toute fonctionnalité connexe.

## Inventaire initial

| Domaine | Éléments repérés | Statut initial | Revue nécessaire |
|---|---|---|---|
| Authentification / RBAC | endpoints auth/me, core security, RBAC, store auth, tests CI | Présent, à sécuriser | sessions, rotation/revocation, MFA, permissions par endpoint, scénarios négatifs |
| Risques | endpoint risks, modèle Risk, scoring service, vue Risks | Présent, maturité inconnue | lifecycle, scoring, résiduel, acceptation, historique, liens, audit |
| Actions | endpoint actions, ActionItem, verification, workflow/lifecycle services, panel UI | Présent, maturité inconnue | états, transitions, ownership, échéances, preuves, vérification, tests |
| Cartographie / actifs | endpoint assets, Asset, Applications, AssetsView, docs d'implémentation/revue | MVP, à valider | import, pagination, filtres, export, graph, dépendances, impact, intégrité et RBAC |
| Applications | endpoint apps, modèle Application, AppsView | Présent | relation avec Asset, source de vérité, lifecycle, imports |
| Conformité ISO | endpoint compliance, ISOControl, assessment/evidence models, ISO view | Partiel | dataset 93 contrôles, source/licence, applicability, assessment workflow, preuves, SoA |
| Documents / preuves | endpoint documents, Document/Chunk, extractor, RAG, DocumentsView | Partiel | ACL au retrieval, versioning, stockage, malware scanning, sandbox parsing, retention |
| IA / RAG | endpoints ai/ai_advanced, AI services, RAG, assistant UI | Présent, à valider | grounding, citations, permission filtering, prompt injection, modèles/config, tests |
| Fournisseurs / TPRM | endpoint suppliers, supplier models/services, view, docs, ADR | Développé en grande partie, à valider | workflows, validations, permissions, migrations, access expiry, snapshots/trends |
| Reporting | endpoint reports, dashboard, TPRM printable report | Partiel | KPI definitions, authorization, report scope, PDF/CSV/XLSX, audit exports |
| Journaux sécurité | endpoint security_logs, SecurityLog model/service | Présent | tamper resistance, retention, alerting, privileged access, export |
| Audits | aucun endpoint/model/view Audit dédié identifié dans l'inventaire | Non identifié | concevoir programme, missions, constats, recommandations, preuves, actions |
| Gouvernance | aucun domaine organisation/gouvernance dédié identifié | Non identifié/partiel | unités organisationnelles, politiques, objectifs, décisions, owners, approvals |
| Notifications/workflows transverses | services action/supplier présents; orchestration globale non identifiée | Partiel | échéances, email/in-app, retries, préférences, audit, règles de déclenchement |
| Administration | apps/auth/config existants | Partiel | gestion utilisateurs/rôles/périmètres, paramètres, configuration, audit |
| Infrastructure / production | Docker Compose, CI workflows, migrations | En cours | fresh install, existing DB upgrade, secrets, backups, restore, monitoring, reverse proxy, hardening |

## Risques transverses prioritaires à confirmer

1. Stratégie Alembic baseline et migration sur bases neuves/existantes.
2. Tests API d'intégration (auth, permissions, risks, actions, documents, suppliers).
3. Isolation des documents et du RAG selon permissions/classification.
4. Historique formel des risques et acceptation du risque résiduel.
5. Audit logs: intégrité, rétention et alertes.
6. Sécurité upload/parsing: antivirus et isolation/sandbox.
7. Ownership actions et entités organisationnelles: relations structurées plutôt que champs libres lorsque pertinent.
8. Données de conformité et preuves: validation et provenance.
9. Déploiement/backup/restore/monitoring et runbooks.

## Priorité de revue

- **P0:** Phase 0 — migration baseline, CI HEAD, Docker/runtime, auth/RBAC, documents/RAG ACL, revue PR.
- **P1:** Cartographie, risques et actions — intégrité des liens et workflows de bout en bout.
- **P1:** TPRM — lifecycle fournisseur, accès, contrats, assessments et indicateurs.
- **P2:** Conformité — dataset, assessments, evidence et SoA.
- **P2:** Reporting — définitions KPI et permissions.
- **P3:** Audits, gouvernance, notifications et industrialisation — cadrage et backlog détaillé.

## Prochaine mise à jour

Chaque module sera revu à partir de ses fichiers réels (models, schemas, endpoints, services, frontend, migrations et tests). Le statut sera remplacé par **Validé**, **Partiel**, **Bloquant** ou **Non commencé**, avec références aux tests et aux issues de backlog.
