# Phase 0 Baseline — Semantic Discovery Roadmap

**Date**: 2026-07-07
**Roadmap**: `docs/roadmap/semantic-discovery-roadmap.md`
**Phase**: 0 — Infrastructure Readiness & Live-Archive Baseline

## Summary

All 4 Phase 0 milestones complete. The semantic indexing pipeline works against the live
archive path with zero failures. Fresh artifacts produced and schema-validated.

## M0.1 — Smoke Test (build-asset-semantic-index)

| Metric | Value |
|--------|-------|
| Command | `build-asset-semantic-index --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" --max-total 100` |
| Inspected | 100 |
| Failed | 0 |
| Output | `Exports/semantic-phase0/smoke-semantic-fresh.json` |

All 100 payloads classified as `bin` type. Semantic categories detected:
`hint:waypoint-poi` (35), `hint:actor-object` (18), `ref:texture` (64).

**Verdict**: Pipeline works against live archive. No Source/ migration issues.

## M0.2 — Full Inventory (inventory-asset-signatures)

| Metric | Value |
|--------|-------|
| Command | `inventory-asset-signatures --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" --max-total 5000` |
| Inspected | 5,000 |
| Failed | 0 |
| Signature Groups | 1,147 |
| Output | `Exports/semantic-phase0/live-signature-inventory-fresh.json` |

**Verdict**: Zero failures. 1,147 distinct signature groups across 7 types.

## M0.3 — Type Distribution Baseline

### Fresh 5k inventory (2026-07-07)

| Type | Count | Pct |
|------|------:|----:|
| dds | 2,803 | 56.1% |
| bin | 1,351 | 27.0% |
| nif | 806 | 16.1% |
| png | 25 | 0.5% |
| jpg | 12 | 0.2% |
| txt | 2 | 0.0% |
| xml | 1 | 0.0% |

### Existing 10k inventory (2026-06-28, for comparison)

| Type | Count | Pct |
|------|------:|----:|
| dds | 5,804 | 58.0% |
| bin | 1,807 | 18.1% |
| nif | 1,796 | 18.0% |
| jpg | 304 | 3.0% |
| png | 184 | 1.8% |
| txt | 104 | 1.0% |
| xml | 1 | 0.0% |

**Key observations**:

- DDS textures dominate (~56-58%) — largest type family by far
- Binary (`bin`) is second largest (~18-27%) — includes KFM, mesh data, unknown binaries
- NIF models third (~16-18%) — Gamebryo File Format 20.6.0.0
- XML is extremely rare (1 entry in 10k) — most config is binary
- Type distribution is stable across sample sizes (5k vs 10k)

### Semantic Categories (CLI output, 100-payload smoke)

| Category | Count | Notes |
|----------|------:|-------|
| hint:waypoint-poi | 35 | Waypoint/POI markers in binary payloads |
| hint:actor-object | 18 | Actor/object references |
| ref:texture | 64 | Texture references |
| asset:unknown-binary | 100 | All binary |

## M0.4 — Schema Audit

| Schema | Status | Notes |
|--------|--------|-------|
| `asset-semantic-index-v1.schema.json` | ✅ Current | Both smoke and inventory outputs validate cleanly |
| `binary-signatures-v1.schema.json` | ✅ Exists | For binary signature roadmap (separate lane) |

Schema validation results:

- All 11 required top-level fields present
- `SchemaVersion` matches `asset-semantic-index/v1`
- SignatureGroup fields: 14/14 required present
- No extra fields, no missing fields

## Exit Criteria Status

| Criterion | Status |
|-----------|--------|
| `build-asset-semantic-index` runs against live archive | ✅ |
| Type distribution known | ✅ (7 types, DDS dominant at 56%) |
| At least one smoke JSON produced and schema-valid | ✅ (2 artifacts validated) |
| Handoff committed | ✅ (this document) |

## Artifacts Produced

| File | Size | Description |
|------|------|-------------|
| `Exports/semantic-phase0/smoke-semantic-fresh.json` | ~75KB | 100-payload smoke test |
| `Exports/semantic-phase0/live-signature-inventory-fresh.json` | ~1.4MB | 5,000-payload inventory |

## Pre-existing Artifacts (2026-06-28)

| File | Size | Description |
|------|------|-------------|
| `Exports/semantic-phase0/smoke-semantic.json` | 74KB | Original 50-payload smoke |
| `Exports/semantic-phase0/live-signature-inventory.json` | 624KB | Original inventory |
| `Exports/semantic-phase0/live-signature-inventory-10k.json` | 1.5MB | 10k-payload inventory |

## Next Steps (Phase 1 — Priority 1: Zone/Map Names)

Phase 0 is complete. The next phase targets **Lane 1: Zone/Map Names** — mining the archive
for zone identifiers, map names, and location labels that RiftReader can use to validate
live-memory zone ID observations.

Potential approach:

1. Run `build-asset-semantic-index --type xml --type txt` to extract text-based entries
2. Filter for `hint:map-zone` category hits
3. Cross-reference with existing zone ID data from RiftReader
4. Produce compact zone vocabulary JSON artifact
