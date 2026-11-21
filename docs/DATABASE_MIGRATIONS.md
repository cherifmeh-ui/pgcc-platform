# Database migration baseline

The repository now contains an Alembic baseline migration, `0001_initial`.

## Fresh database

Set the backend environment variables, then from `backend/` run:

```bash
alembic upgrade head
```

The baseline imports all SQLAlchemy models and creates their metadata. This is a transitional baseline, not yet a fully hand-authored migration history.

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

A static graph test now checks that migration revision identifiers are unique, the history has exactly one root (`0001_initial`), parent revisions exist, and the current history remains linear. It also protects the intentionally non-destructive baseline downgrade.

These checks **do not validate actual PostgreSQL schema creation or upgrade behavior**. Phase 0 still requires disposable PostgreSQL integration runs for:
- empty database `alembic upgrade head`;
- inspection of the resulting schema against model metadata;
- legacy database baseline/stamp procedure;
- upgrade from a representative previous revision;
- backup/restore and recovery rehearsal.

The baseline uses `Base.metadata.create_all()` and is transitional. Before production, replace it with a reviewed, deterministic schema baseline or keep the transitional approach only with documented schema equivalence checks and controlled model imports.

## pgvector initialization

The initial schema uses the PostgreSQL `vector` type for document embeddings. The baseline migration and development startup now execute `CREATE EXTENSION IF NOT EXISTS vector` before creating metadata tables. The database image must include pgvector, and the database role must have permission to create the extension (or it must be provisioned by an administrator). Verify this in the disposable PostgreSQL migration run.
