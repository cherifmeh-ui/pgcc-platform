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
