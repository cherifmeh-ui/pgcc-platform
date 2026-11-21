# ADR-007 — Modélisation du module Fournisseurs

- **Statut :** Accepté pour conception; implémentation après consolidation Cartographie.
- **Contexte :** PGCC doit suivre les fournisseurs, contrats, évaluations, accès tiers et dépendances SSI.
- **Décision :** intégrer le module Fournisseurs dans le monolithe modulaire existant avec des entités relationnelles dédiées : Supplier, SupplierContact, SupplierContract, SupplierAssessment, SupplierAssessmentAnswer, SupplierAccess, SupplierAssetLink et SupplierRiskLink.
- **Intégration :** réutiliser Asset, Risk, ActionItem, Document, User et le journal de sécurité; ne pas dupliquer leurs données.
- **Sécurité :** RBAC fin, séparation demandeur/approbateur, historique des décisions, pas de stockage de secrets dans le registre des accès.
- **Conséquences :** modèle testable et interopérable avec Cartographie et Risques; coût initial de conception des workflows et de la matrice de permissions.
- **Alternatives écartées :** microservice séparé (complexité prématurée); simple champ fournisseur sur Asset (insuffisant pour contrats, accès, évaluations et historisation).
- **Références :** `docs/SUPPLIER_MODULE_DESIGN.md`, `docs/ASSET_DATA_MODEL_REVIEW.md`.
