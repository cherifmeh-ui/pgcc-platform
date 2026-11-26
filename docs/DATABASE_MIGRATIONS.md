# Database migration baseline

The repository now contains an Alembic baseline migration, `0001_initial`.

## Fresh database

Set the backend environment variables, then from `backend/` run:

```bash
alembic upgrade head
```

The baseline imports the current model registry for foreign-key metadata but creates only its explicit ten historical tables. Later tables are created by their own Alembic revisions. This remains a transitional, model-backed baseline rather than a fully hand-authored schema snapshot; the table set is frozen to prevent future models being created ahead of their migrations.

## Existing development database

Do **not** run the baseline blindly against a database already initialized by `Base.metadata.create_all()`. First inspect schema, indexes, constraints and extensions, compare against the model metadata, back up the database, and only then stamp the revision:

```bash
alembic stamp 0001_initial
```

Stamping records migration state; it does not modify the schema.

## Production

Production startup no longer runs `create_all()`. Schema changes must be applied through Alembic before deploying the application version that requires them.

The initial migration downgrade is intentionally disabled to avoid accidental deletion of all application tables. Subsequent revisions should provide explicit, reviewed upgrade/downgrade operations.

## Phase 0 integrity checks

Static tests check that migration revision identifiers are unique, the history has exactly one root (`0001_initial`), parent revisions exist, and the current history remains linear. They also protect the intentionally non-destructive baseline downgrade and the frozen baseline table set.

The PostgreSQL CI workflow now validates:
- empty database `alembic upgrade head`;
- `alembic check` against complete SQLAlchemy metadata (`No new upgrade operations detected`);
- upgrade from revision `0024_audit_outbox`;
- downgrade `0026 -> 0025` followed by upgrade to `head`;
- custom-format `pg_dump` and `pg_restore` into a fresh database, including Alembic version and fixture checks.

Run `45586284593` passed these checks on code HEAD `91ec0cc` (26 PostgreSQL integration tests passed). This is CI evidence only; production backup/restore, encrypted backup custody, WAL retention, and approved RPO/RTO still require an operational rehearsal.

The baseline still uses `Base.metadata.create_all()` for its frozen ten-table set. Before production, replace it with a reviewed deterministic schema snapshot or retain the transitional approach only with schema-equivalence checks and controlled imports.

## pgvector initialization

The initial schema uses the PostgreSQL `vector` type for document embeddings. The baseline migration and development startup now execute `CREATE EXTENSION IF NOT EXISTS vector` before creating metadata tables. The database image must include pgvector, and the database role must have permission to create the extension (or it must be provisioned by an administrator). Verify this in the disposable PostgreSQL migration run.


## Contraintes d'intégrité ajoutées — révisions 0029 et 0030

- 0029_supplier_access_link_scope lie par contrainte composite la demande d'accès au fournisseur et à l'actif portés par le lien.
- 0030_risk_integrity_constraints verrouille au niveau base la matrice de calcul du risque (impact et vraisemblance de 1 à 5, score égal au produit), les références non vides et leur unicité normalisée.
- Les deux migrations effectuent un contrôle préalable des données historiques et interrompent l'upgrade en présence d'incohérences. Les données doivent être analysées et corrigées de manière contrôlée avant nouvelle tentative.
- La CI valide l'upgrade depuis une base neuve, la mise à niveau depuis 0024_audit_outbox, le downgrade jusqu'à 0025_user_auth_version, la remise à niveau vers 0030, le contrôle de dérive et le dump/restore.
