# NiDataStream/Ghidra schema policy

Status date: 2026-05-25

This policy applies to tracked schemas and machine-readable workflow outputs in the Ghidra/NiDataStream discovery lane.

## Current rule

The v1 schemas are fail-closed promotion brakes. They intentionally require:

- `CandidateOnly: true` for discovery/status outputs.
- `ParserExportPromotionAllowed: false` for `nidatastream-promotion-status/v1`.
- `FieldOrderPromoted: false` for descriptor proof status and descriptor summaries embedded in promotion status.
- `additionalProperties: false` on promotion-critical objects where shape drift would weaken review.

## Adding or changing schemas

When adding a schema or changing an existing schema:

1. Keep the output machine-readable and repo-relative.
2. Use a stable `SchemaVersion` string and tracked JSON schema under `docs/schemas/`.
3. Add or update a targeted test that validates at least one positive fixture/output against the schema.
4. Add a negative fixture when the schema represents a safety brake.
5. Do not loosen `CandidateOnly`, `ParserExportPromotionAllowed`, or `FieldOrderPromoted` in a drive-by cleanup.
6. Do not use schema changes to hide missing evidence, generated-output risk, or parser/export drift.
7. Keep generated reports under ignored `Exports/` unless explicitly approved otherwise.

## Versioning rule

Use a new `/v2` schema only when the output contract must change incompatibly. A v2 schema for promotion-critical output must include migration notes and tests proving the old fail-closed expectations were either preserved or intentionally replaced by stronger gates.

## Promotion rule

A future schema that permits parser/export promotion is not sufficient by itself. Parser/export promotion still requires:

- positive descriptor field-order proof,
- sample-byte agreement on the selected corpus,
- pairing-impact review that does not promote noise,
- parser/export non-consumption guard updates reviewed alongside the behavior change,
- generated-output guard pass,
- targeted parser/export regression tests.
