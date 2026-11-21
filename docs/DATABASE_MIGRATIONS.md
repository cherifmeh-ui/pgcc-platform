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
