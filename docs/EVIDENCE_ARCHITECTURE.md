# Evidence Architecture Decision — PGCC

Status: proposed; implementation intentionally deferred until the database migration baseline and authorization model are validated.

## Objective

Make evidence first-class in the GRC workflow without duplicating uploaded document binaries or treating a document's existence as proof that a control is implemented.

Evidence should support controls, risks, actions, audits, and findings, with traceable ownership, verification, provenance, integrity, and lifecycle.

## Current state and constraints

- `Document` stores document metadata, extracted text, and binary content in PostgreSQL.
- `DocumentChunk` stores RAG chunks and embeddings; deletion currently removes chunks explicitly.
- `EntityLink` is a polymorphic link table with UUID endpoints and enum types, but endpoints have no database foreign keys. It cannot guarantee referential integrity.
- `IsoControl` currently holds a manual coverage boolean; compliance status is declarative.
- The initial Alembic migration delegates to `Base.metadata.create_all`; it is not a safe schema-evolution strategy for populated deployments.

## Proposed model

### Evidence

One evidence record should reference a source document where applicable; it should not duplicate document binary data.

Fields (proposed):
- `id`: UUID primary key
- `title`, `description`: required/optional bounded text
- `evidence_type`: controlled enum (document, screenshot, export, configuration, log, test_result, attestation, other)
- `source_document_id`: nullable FK to documents; deletion policy RESTRICT or explicit archival
- `sha256`: nullable initially, required for file-backed evidence after backfill
- `collected_at`, `valid_until`: timestamps/date; validity is not inferred from upload time
- `owner_id`, `verified_by_id`: nullable FKs to users
- `verification_status`: pending, verified, rejected, expired
- `verified_at`, `verification_notes`
- `created_at`, `updated_at`; use timezone-aware UTC timestamps

### Evidence relationships

Prefer explicit association tables with foreign keys over the existing generic `EntityLink` for evidence:
- `evidence_controls`: evidence_id + iso_control_id; relationship context and optional period
- `evidence_risks`: evidence_id + risk_id; relationship context
- `evidence_actions`: evidence_id + action_item_id; relationship context
- Audit/finding association should be introduced with those domain models, not as dangling polymorphic UUIDs.

Association rows should have unique constraints on the pair, created_at, created_by_id, and bounded relationship notes. Decide whether one evidence item can support multiple entities (recommended: yes, with explicit links).

## Lifecycle and rules

1. Upload/ingest source document using existing validation and RBAC.
2. Create evidence metadata and relationship links; default verification is pending.
3. Verify evidence through a separate permissioned action; capture verifier, timestamp, outcome, and notes.
4. Reverification/expiry should make stale evidence visible without automatically asserting a control is non-compliant.
5. Evidence deletion should be restricted when referenced by assessments/audit records; prefer archival/retention state over hard deletion.
6. Hash the exact original file bytes (SHA-256) at ingestion and recompute on retrieval/verification if storage supports it.
7. Do not treat AI-extracted text, embeddings, or keyword matches as verified evidence.
8. Control status must be a separate assessment with assessor, date, rationale, applicability, implementation state, and evidence links.

## API outline

- `POST /evidence`: create metadata and link existing document; permission: evidence:create
- `GET /evidence`: filtered/paginated list; permission: evidence:read
- `GET /evidence/{id}`: metadata and authorized relationships
- `PATCH /evidence/{id}`: metadata changes with audit trail
- `POST /evidence/{id}/verify`: verify/reject; permission: evidence:verify
- `POST /evidence/{id}/links`: add typed, FK-backed relationship
- `DELETE /evidence/{id}/links/{link_id}`: unlink with audit record
- No public download route; if implemented, authorize per evidence/document and use safe content disposition.

## Migration and rollout

1. Validate current database schema and migration history; document supported fresh-install and existing-install paths.
2. Add explicit migration(s) for evidence and association tables; do not alter the baseline migration.
3. Backfill document SHA-256 in bounded batches, with progress and rollback-safe handling.
4. Introduce permissions and tests before enabling UI.
5. Keep current compliance endpoint contract during transition; expose evidence verification separately.
6. Add API tests for ownership/permissions, cross-tenant or unauthorized access (if tenancy is introduced), FK integrity, duplicate links, invalid transitions, expired evidence, hash mismatch, and audit logging.

## Decisions requiring validation before implementation

- Retention and archival policy for evidence and source documents.
- Whether the application needs tenant/department-level authorization; current RBAC is role-level.
- Whether storage remains PostgreSQL binary or moves to private object storage.
- Whether evidence can be verified by the uploader; default recommendation is separation of duties for high-impact evidence.
- Audit/finding model and its relationship to evidence.
