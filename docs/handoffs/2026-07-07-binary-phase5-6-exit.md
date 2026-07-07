# Binary Phase 5 + 6 Exit Handoff — Unified Signature DB + Automation

**Date**: 2026-07-07
**Session**: Phase 5 (Session 7) + Phase 6 (Session 8) of the binary-signature lane
**Roadmap**: `docs/roadmap/binary-signature-roadmap.md` — Phases 5 & 6
**Status**: Phase 5 ✅ COMPLETE | Phase 6 ✅ COMPLETE (partial — M6.3 workflow wiring deferred)

---

## What was done

### Phase 5 — Unified Signature Database

Phase 5 fuses the Phase 2 byte-signature catalog and the Phase 3 struct-layout catalog into a single consumer-facing artifact. **No new schema was introduced** — the existing `binary-signatures-v1` schema (Phase 2) was extended additively.

Schema extensions (all additive — no `required` added, no `additionalProperties: false` removed):

- `structField` $def: optional `ModRMHitCount` (integer >= 0), optional `Notes` (string)
- `anchor.StructLayout.properties`: optional `BaseRegisters` (dict<int>), optional `TotalModRMHits` (int >= 0)
- `Provenance.properties`: optional `CrossCheckerVersion`, optional `Phase2CatalogPath`, optional `Phase3CatalogPath`
- `Provenance.GhidraFindings`: enum-locked to 4 known keys (`PreviousCallback0x320`, `PreviousCallback0x328`, `PropertyWalkerArchitecture`, `ActualAccessPattern`), `additionalProperties: false`
- `Summary.properties`: optional `AttachedStructCount`

Synthesizer (`scripts/synthesize_unified_signature_db.py`, ~210 lines):
- Emits `Exports/binary-phase5/rift-x64-signature-database.json` conforming to `binary-signatures/v1`
- Reads Phase 2 + Phase 3 catalogs, enriches the `vtable-dispatch` anchor's `StructLayout` with the Phase 3 8-field LocalPlayer (including `unknown_float_31c` field Phase 2 lacked)
- Defensive guards: raises `ValueError` on empty Phase 2 `Anchors[]`, emits `WARNING:` to stderr on Phase 3 parse failure, emits `WARNING:` to stderr when unknown `GhidraFindings` keys are silently dropped
- Tolerates missing Phase 3 catalog (skip-with-warning, emit still-schema-valid DB)

Tests (`tests/test_synthesize_unified_signature_db.py`, 16 tests):
- Schema conformance via jsonschema.validate()
- Merge invariants (anchor names preserved, summary counts consistent)
- Phase 3 enrichment (8-field LocalPlayer + `ModRMHitCount` + `Notes` propagated)
- Missing-Phase 3 resilience
- Provenance metadata (with `GhidraFindings` enum validation)
- Input immutability
- Defensive guards (empty-Anchors `ValueError`)

### Phase 6 — Automation & Monitoring

Two new scripts close the documentation-to-deployment loop:

`scripts/extract_binary_signatures.py` (**M6.1**, ~190 lines) — pipeline orchestrator:
- Validates Phase 2 + Phase 3 inputs against their respective schemas
- Calls `synthesize_unified_signature_db` underneath
- Validates the unified DB output
- Writes a sibling `extraction-manifest.json` (schema: `binary-extraction-manifest/v1`)
- Exit codes: 0 = success, 1 = schema-violation, 2 = missing-input/empty-Anchors/synthesis-failure
- `--validate-only` mode skips writing output
- `WARNING:` to stderr on jsonschema-fallback path

`scripts/compare_signature_databases.py` (**M6.2**, ~280 lines) — diff tool:
- Compares two unified DBs by anchor `Name`
- Reports 17 categories: `binary-version-changed`, `binary-fingerprint-moved`, `anchor-added`, `anchor-removed`, `sig-hex-changed`, `signature-length-changed`, `wildcard-count-changed`, `stability-tier-regressed`, `uniqueness-changed`, `struct-fields-added`, `struct-fields-removed`, `modrm-shake` (>=25% delta over max), `notes-changed`, **`field-name-changed`** (NEW — surfaces semantic drift when offset stays but Name shifts, e.g., `pos_x` -> `terrain_x`), `confidence-promoted`, `confidence-demoted`, `ghidra-findings-changed`
- JSON output schema: `binary-signature-diff/v1`
- Optional `--markdown-out` for human-readable report

Tests (`tests/test_compare_signature_databases.py`, 17 tests + `tests/test_extract_binary_signatures.py`, 5 tests):
- All 17 diff categories exercised with synthetic DBs
- Threshold sensitivity tests (e.g., ModRM-shake at exactly 25% delta)
- CLI smoke tests (subprocess.run paths)
- Happy/validate-only/missing-P3/missing-input/empty-Anchors paths

### M6.3 workflow wiring — DEFERRED

The kebab-case registration of `extract-binary-signatures` + `compare-binary-signatures` commands in `rift_workflow.py::COMMAND_MAP` and `rift_read_only.py::COMMAND_MAP` is **deferred**. Consumers presently invoke the scripts directly via `python scripts/extract_binary_signatures.py` / `python scripts/compare_signature_databases.py`, which is functional but does not complete the M6.3 milestone.

This deferral is non-blocking — the scripts are self-contained CLI tools and don't depend on the workflow's Ghidra orchestrator.

---

## Defense in depth — Safety Boundary

| Boundary | Mechanism |
|---|---|
| Schema conformance | jsonschema.validate() at every read/write boundary (Phase 2 input, Phase 3 input, Phase 5 output) |
| Empty-input safety | ValueError on Phase 2 `Anchors[]` empty (loud failure, not silent invalid artifact) |
| jsonschema-import safety | `WARNING:` to stderr on ImportError; lightweight fallback only validates `SchemaVersion` const + `Anchors[]` presence — explicitly does NOT satisfy full schema |
| Silently-dropped data | `WARNING:` to stderr lists any unknown `GhidraFindings` keys dropped (schema enum-locks + drift visibility) |
| CandidateOnly enforcement | Emitted artifacts pin `CandidateOnly: true` (Scanning Rule Object contract) |
| Provenance pinning | `GhidraFindings` enum-locked to documented narrative keys; downstream consumers can audit the safety boundary |

---

## Commit map (this session)

| Hash | Description |
|---|---|
| `e52d234` | `feat(binary-phase5):` unified signature DB synth + schema extensions + enum-locked GhidraFindings |
| `a5b152a` | `feat(binary-phase6):` automation scripts — extract pipeline + diff tool + tests |

Both pushed to `origin/main`.

---

## Resume Protocol — next session

1. Verify: `git log --oneline -3` should show `a5b152a` then `e52d234`
2. Re-run Phase 6 validation pipeline:
   ```bash
   python scripts/extract_binary_signatures.py --validate-only
   ```
3. Generate a fresh diff against a saved prior version:
   ```bash
   cp Exports/binary-phase5/rift-x64-signature-database.json /tmp/db_v1.json
   python scripts/extract_binary_signatures.py  # rebuilds unified DB
   python scripts/compare_signature_databases.py --old-db /tmp/db_v1.json \\
       --new-db Exports/binary-phase5/rift-x64-signature-database.json \\
       --out Exports/binary-phase6/patch-diff-report.json \\
       --markdown-out Exports/binary-phase6/patch-diff-report.md
   ```
4. Read: `docs/handoffs/2026-07-07-binary-phase3-struct-layout.md` (Phase 3 baseline) + this handoff
5. If picking back up at M6.3, fork a new branch and register commands in `rift_read_only.py::COMMAND_MAP`
6. The open Phase 3 work item is `M3.2` — map secondary structs (Camera, ZoneInfo, EntityList) — which requires additional Ghidra runs at the cost of ~30 minutes per target

---

## Known polish (non-blocking)

- `modrm-shake` 25% threshold over-triggers on small-N fields (e.g. 4 -> 5 hits counts as a 'shake'). Could be hybridized with absolute threshold (`max(25% delta, abs_delta >= 100)`).
- `_compare_confidence` hardcoded `rank` dict silently demotes any future enum value (e.g., `verifed` -> -1). Pin to schema enum or warn on unknown.
- M6.3 entry-point wiring deferred (see above).
- `--strict` mode for `compare_signature_databases.py` (nonzero exit on breaking categories) deferred.

---

*End of handoff. Phases 5 + 6 of the binary-signature lane are shipped to origin/main with M6.3 + secondary-struct mapping as documented follow-ups.*
