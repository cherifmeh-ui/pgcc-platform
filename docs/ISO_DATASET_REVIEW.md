# ISO/IEC 27002:2022 Seed Dataset — Review Required

## Status
The repository seed currently contains 93 entries and a claimed 37/8/14/34 distribution. The seed data must not be presented as an authoritative ISO/IEC 27002:2022 reference until all reference codes, official titles, domains, and mappings have been independently validated against a legally obtained authoritative copy.

## Known issues observed in current seed
- Several A.5 control titles/descriptions are visibly shifted or inconsistent with the 2022 control structure (for example A.5.4, A.5.8, A.5.17 onward).
- Many A.8 titles are in English while A.5-A.7 are in French, and several descriptions are prescriptive implementation examples rather than neutral control intent.
- Seed descriptions include arbitrary technical recommendations (products, technologies, thresholds, architectures) that should not be treated as ISO requirements.
- `category` is currently used as a version marker, not as a controlled assessment attribute.
- Manual coverage is a Boolean and has no evidence, assessment owner, date, applicability decision, maturity, or review trail.

## Governance decision
Until validated, label the catalog as **Draft / Référentiel à valider**. Do not use the dataset to produce a certification-readiness claim or a compliance percentage implying audited implementation.

## Recommended canonical data model
- framework_id and version (ISO/IEC 27002:2022)
- control_ref (unique)
- official_title (validated source)
- domain (Organizational, People, Physical, Technological)
- control_type (Preventive, Detective, Corrective; validated classification)
- purpose / intent (originally authored, not copied from copyrighted normative text)
- source_verified_at, source_verified_by, source_provenance

Assessment must be separate from the reference catalog:
- applicability: Applicable / Not applicable / To determine
- justification for non-applicability
- implementation_status: Not assessed / Planned / Partial / Implemented / Verified
- maturity_level and methodology version
- evidence links and evidence validity
- assessment owner, assessor, assessment date, next review date
- findings and linked risks/actions
- approval and audit history

## Compliance score policy
A control with a risk or action whose text happens to contain the reference is **not** covered. Such matches are only candidates for human review. A manually asserted coverage flag without evidence is **Declared covered**, not verified. The score should be computed only from the approved assessment model, and its methodology must be displayed. Not-applicable controls should be handled separately and justified; they must not be silently counted as implemented.

## Seed safety
The canonical backend seed should be idempotent and non-destructive. The legacy root seed must delegate to it rather than deleting all rows. Assessment fields must not be overwritten when refreshing catalog metadata.

## Validation plan
1. Obtain an authoritative reference permitted for internal use.
2. Verify all 93 references, titles and domain counts.
3. Have a qualified ISO 27001/27002 practitioner review the catalog.
4. Create a separate assessment schema and migration.
5. Import only validated metadata.
6. Build tests for exact count, unique refs, domain distribution, and version.
7. Keep catalog changes and assessment history auditable.
