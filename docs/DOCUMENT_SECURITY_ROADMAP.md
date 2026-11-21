# Document Security and Evidence Roadmap

## Current protections (reviewed in repository)
- Upload reads at most 10 MiB plus one byte and rejects larger files.
- Only PDF and DOCX extensions are accepted.
- PDF signature is checked; DOCX must begin with ZIP signature and contain a valid Word document structure.
- PDF extraction is limited to 50 pages.
- DOCX archive is limited by entry count, total uncompressed size, and compression ratio.
- Extracted text is capped at 2,000,000 characters.
- Parser errors are returned generically; malformed PDF pages are skipped without printing parser details.
- Documents are permission-gated through the API.

## Important residual risks / not yet implemented
- No malware scanning/AV integration or quarantine workflow.
- File signature checks are not a substitute for content disarm and reconstruction or sandboxing.
- Files and extracted text are stored in PostgreSQL; no object storage, encryption-at-rest policy, retention, or classification model is implemented here.
- No persisted SHA-256 file integrity field or immutable version history.
- Duplicate filename check is not a database uniqueness constraint and may race.
- Document deletion does not yet have archive/retention controls.
- RAG indexing is invoked synchronously by API and needs a job queue, status model, retries, and failure state.
- RAG chunks lack robust document version/page/classification metadata and retrieval access filtering.
- Extracted document content is untrusted. It can contain prompt-injection instructions; AI services must treat it as data, never system instructions.
- No evidence approval/review workflow is implemented.

## Decisions
1. Keep the current PDF/DOCX-only policy for now; do not enable additional formats casually.
2. Before production, require malware scanning with fail-closed behavior or a documented risk acceptance.
3. Add a migration baseline before schema changes; then add SHA-256, classification, owner, retention, version, processing state, and archive metadata.
4. Use a database unique constraint for document identity only after deciding version semantics; filenames alone are not identity.
5. Move file bytes to private object storage when deployment architecture permits; use authorization checks and short-lived download URLs or a controlled download endpoint.
6. Add asynchronous indexing with `pending/processing/completed/failed`, retries and bounded worker resources.
7. Enforce document ACL/classification filtering before retrieval; never retrieve restricted documents for an unauthorized user.
8. Record evidence provenance and validation separately from document metadata.
9. Add tests for malformed PDFs/DOCX, archive bombs, oversized uploads/text, unsupported extensions, and upload/download authorization.

## Production release gate
The upload feature is not considered production-hardened until the residual risks above have been addressed or explicitly accepted by the system owner, and tests/security review have been performed.
