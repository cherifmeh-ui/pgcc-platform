# Implémentation — Référentiel Fournisseurs

## Tranche 1 — Référentiel et contacts

- Modèles SQLAlchemy `Supplier` et `SupplierContact`.
- Migration Alembic `0012_supplier_register`.
- API CRUD de base, archivage logique, recherche et pagination par limit/offset.
- Gestion des contacts professionnels, désactivation plutôt que suppression.
- Permissions dédiées `suppliers:read/create/update/archive/manage_contacts/export`.
- Journalisation des créations, modifications et archivages.
- Codes fournisseurs normalisés et indexés avec unicité insensible à la casse.
- Aucun endpoint de suppression physique et aucun stockage de secrets.

### Routes

- `GET/POST /api/v1/suppliers/`
- `GET/PATCH /api/v1/suppliers/{supplier_id}`
- `POST /api/v1/suppliers/{supplier_id}/archive`
- `GET/POST /api/v1/suppliers/{supplier_id}/contacts`
- `PATCH /api/v1/suppliers/{supplier_id}/contacts/{contact_id}`

### Suite

Contrats et pièces justificatives, évaluations versionnées, accès tiers et relations explicites avec actifs/risques seront ajoutés dans des tranches indépendantes avec migrations et tests dédiés.


## Tranche 2 — Contrats et clauses SSI

- Modèle SupplierContract relié au fournisseur par FK RESTRICT.
- Référence contractuelle unique par fournisseur, insensible à la casse.
- Dates contrôlées côté API et base; préavis borné; renouvellement explicite.
- Clauses SSI suivies individuellement : confidentialité, notification d'incident, droit d'audit, continuité, réversibilité, localisation, sous-traitance, restitution/destruction.
- Référence facultative au document existant (documents.id) : aucun stockage binaire ni duplication documentaire.
- API : lecture paginée, création et modification; aucune suppression physique.
- Permissions dédiées : lecture Admin/Auditor, gestion Admin.
- Migration Alembic 0013_supplier_contracts; downgrade limité à la nouvelle table.
- Pas d'automatisation de statut ni d'alertes avant mise en place d'un service de notifications et de règles de date validées.


## Tranche 2 — Contrats et clauses SSI

- Modèle SupplierContract relié au fournisseur par FK RESTRICT.
- Référence contractuelle unique par fournisseur, insensible à la casse.
- Dates contrôlées côté API et base; préavis borné; renouvellement explicite.
- Clauses SSI suivies individuellement : confidentialité, notification d'incident, droit d'audit, continuité, réversibilité, localisation, sous-traitance, restitution/destruction.
- Référence facultative au document existant (documents.id) : aucun stockage binaire ni duplication documentaire.
- API : lecture paginée, création et modification; aucune suppression physique.
- Permissions dédiées : lecture Admin/Auditor, gestion Admin.
- Migration Alembic 0013_supplier_contracts; downgrade limité à la nouvelle table.
- Pas d'automatisation de statut ni d'alertes avant mise en place d'un service de notifications et de règles de date validées.

## Tranche 3 — Évaluations de sécurité fournisseurs

- Évaluations historisées par fournisseur et type (initiale, périodique, renouvellement, incident, changement majeur).
- Chaque évaluation conserve un instantané JSONB du questionnaire et sa version : les changements futurs ne modifient pas l'historique.
- Réponses structurées avec score, commentaire et référence facultative à une preuve du module Documents.
- Calcul pondéré déterministe côté serveur, score sur 100 et niveau de risque explicite; les données manquantes ne sont jamais assimilées à la conformité.
- Cycle : Brouillon → À valider → Validée. Les réponses deviennent non modifiables après soumission.
- Séparation des tâches : l'évaluateur ne peut pas valider sa propre évaluation.
- Une approbation simple est interdite pour un risque Élevé ou Critique; une approbation conditionnelle ou un refus est alors requis.
- Permissions dédiées : Admin pour évaluer et valider; Admin/Auditor en lecture.
- Migration Alembic 0014_supplier_assessments; aucune modification des tables historiques.
- La validation reste une décision humaine; le score ne modifie pas automatiquement le statut du fournisseur.
### Contrôle de confiance du questionnaire

- Le client ne transmet plus la définition ni les pondérations du questionnaire.
- Les versions publiées sont définies côté serveur; la création charge une copie profonde de la version autorisée et la conserve en instantané dans l'évaluation.
- Une version inconnue est rejetée. Cela empêche un utilisateur de modifier les pondérations ou les questions afin de manipuler le score.
- Toute évolution du référentiel doit publier une nouvelle version; les évaluations historiques conservent leur propre instantané.