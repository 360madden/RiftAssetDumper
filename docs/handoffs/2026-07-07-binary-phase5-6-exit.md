# Binary Phase 5 + 6 Exit Handoff — Unified Signature DB + Automation

**Date**: 2026-07-07
**Session**: Phase 5 (Session 7) + Phase 6 (Session 8) of the binary-signature lane
**Roadmap**: `docs/roadmap/binary-signature-roadmap.md` — Phases 5 & 6
**Status**: Phase 5 ✅ COMPLETE | Phase 6 ✅ COMPLETE (M6.3 wiring shipped; 3 pre-existing live-memory commands still need backfill)

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

### M6.3 workflow wiring — SHIPPED ✅

`extract-binary-signatures` + `compare-binary-signatures` are now first-class read-only commands, invokable from the `rift_read_only.py` peer entry point (or from `rift_workflow.py` as deprecation-noticed spawner commands).

**Changes:**

`scripts/rift_read_only.py`:
- Added both commands to `READ_ONLY_COMMANDS` frozenset (count: 41 → 46; +2 M6.3 + 3 pre-existing live-memory commands that were already in the set but not yet wired)
- Added 7 new argparse flags in `_build_parser()`: `--phase2-catalog`, `--phase3-catalog`, `--validate-only` (extract); `--old-db`, `--new-db`, `--diff-out`, `--diff-markdown-out` (compare). All default to `None` so the underlying scripts' defaults apply when omitted.
- Added 2 example lines to the module docstring's `Example:` block for discoverability.

`scripts/rift_workflow.py`:
- Added both commands to `COMMAND_MAP` with empty `dotnet`/`base` keys (pure-Python, satisfies the read-only no-spawn invariant).
- Added 7 new argparse flags inline to `main()` (mirroring the read-only entry point's parser).
- Added 2 dispatch blocks in `_run_command()` immediately after the `batch-export-sibling` block, mirroring the same `subprocess.run` pattern. Underlying scripts own their schema validation and exit-code mapping (0=success, 1=schema-violation, 2=missing-input).
- Added a 3-line pre-spawn-guard rationale comment to the `compare-binary-signatures` dispatcher explaining why the `--old-db`/`--new-db` missing-args case exits 1 (user input invalid) instead of letting the underlying script's argparse raise `SystemExit(2)`. `batch-export-sibling` doesn't pre-validate because its only flag is optional.
- Added 2 example lines to the module docstring's `Examples:` block for discoverability.

`tests/test_m6_3_wiring.py` (6 tests):
- `test_extract_dispatch_propagates_exit_code_zero` — extract happy path with `--phase2-catalog` + `--out`
- `test_extract_dispatch_propagates_exit_code_two` — extract error path (rc=2 from underlying)
- `test_compare_dispatch_propagates_exit_code` — compare happy path with all 4 flags
- `test_compare_dispatch_propagates_exit_code_one` — compare schema-violation path (rc=1)
- `test_read_only_set_size_at_least_43` — sanity that the count grew (was 41; M6.3 adds 2; ≥43)
- `test_argparse_flag_parity_between_two_entry_points` — pins that all 7 M6.3 flags appear in BOTH `rift_read_only._build_parser()` and `rift_workflow.py:main()` (mitigates future argparse drift)

**Parametrized invariants (from `tests/test_rift_read_only_no_spawn.py`) all satisfied for the 2 new commands:**
1. `test_read_only_command_has_empty_dotnet_key` ✓ (empty `dotnet` key in COMMAND_MAP)
2. `test_read_only_command_has_dispatch_block` ✓ (`if command == "X":` marker in source)
3. `test_read_only_command_invokes_dispatch` ✓ (delegates to `rift_workflow._run_command` via `rift_read_only.main`)
4. `test_read_only_command_does_not_invoke_orphan_guard` ✓ (read-only entry point does not import/call the guard)

**e2e smoke (verified locally):**
- `python scripts/rift_read_only.py extract-binary-signatures --phase2-catalog /tmp/nonexistent.json` → exit 2 (underlying script's FileNotFoundError)
- `python scripts/rift_read_only.py compare-binary-signatures` → exit 1 (pre-spawn guard) + clear "requires --old-db and --new-db" stderr message

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
| M6.3 pre-spawn guard | `compare-binary-signatures` exits 1 with a domain-specific message when `--old-db`/`--new-db` are missing, rather than letting the underlying script's argparse raise `SystemExit(2)` with a less friendly error |
| Argparse flag parity | `test_argparse_flag_parity_between_two_entry_points` pins that all 7 M6.3 flags appear in BOTH `rift_read_only._build_parser()` and `rift_workflow.py:main()` — future maintainers adding a flag to one parser will fail this test |

---

## Commit map (this session)

| Hash | Description |
|---|---|
| `e52d234` | `feat(binary-phase5):` unified signature DB synth + schema extensions + enum-locked GhidraFindings |
| `a5b152a` | `feat(binary-phase6):` automation scripts — extract pipeline + diff tool + tests |
| (M6.3) | `feat(binary-phase6-m6.3):` workflow wiring — `extract-binary-signatures` + `compare-binary-signatures` registered in `rift_read_only.py` + `rift_workflow.py` (COMMAND_MAP + argparse + dispatch blocks) + 6-test regression suite + handoff doc update |

All pushed to `origin/main`.

---

## Resume Protocol — next session

1. Verify: `git log --oneline -3` should show the M6.3 commit on top of `a5b152a`
2. Re-run M6.3 e2e smokes:
   ```bash
   python scripts/rift_read_only.py extract-binary-signatures --validate-only
   python scripts/rift_read_only.py compare-binary-signatures --old-db <path1> --new-db <path2>
   ```
3. Re-run the M6.3 regression suite:
   ```bash
   pytest tests/test_m6_3_wiring.py -v
   ```
4. Generate a fresh diff against a saved prior version (Phase 6 full pipeline):
   ```bash
   python scripts/extract_binary_signatures.py
   python scripts/compare_signature_databases.py --old-db <prev> --new-db Exports/binary-phase5/rift-x64-signature-database.json
   ```
5. **Optional follow-up (not in M6.3 commit)**: see "Pre-existing test failures" below — the 3 live-memory commands need the same wiring treatment.

---

## Known polish (non-blocking)

- `modrm-shake` 25% threshold over-triggers on small-N fields (e.g. 4 -> 5 hits counts as a 'shake'). Could be hybridized with absolute threshold (`max(25% delta, abs_delta >= 100)`).
- `_compare_confidence` hardcoded `rank` dict silently demotes any future enum value (e.g., `verifed` -> -1). Pin to schema enum or warn on unknown.
- `--strict` mode for `compare_signature_databases.py` (nonzero exit on breaking categories) deferred.
- `--phase3-catalog ""` empty-string shortcut: argparse with `type=Path` accepts empty string, the handler passes it through, and the underlying script's `is_file()` check skips it. Documented as "omit to skip" in help text but empty string also works. Either document the empty-string shortcut or reject empty strings explicitly in the handler.

---

## Pre-existing test failures (out of M6.3 scope)

While validating the M6.3 wiring, validation surfaced 7 pre-existing parametrized test failures in `tests/test_rift_read_only_no_spawn.py`. **These are not caused by the M6.3 changes** (all 6 M6.3 tests pass; the M6.3 dispatch wiring satisfies all 4 read-only invariants for both new commands).

The 7 failures concern 3 commands that were added to `rift_read_only.READ_ONLY_COMMANDS` in a prior session but were never fully wired into `rift_workflow.COMMAND_MAP` + `_run_command` dispatch:

| Command | Tests failing |
|---|---|
| `probe-modrm-leads` | `test_read_only_command_has_empty_dotnet_key` + `test_read_only_command_has_dispatch_block` |
| `scan-live-values` | `test_read_only_command_has_empty_dotnet_key` + `test_read_only_command_has_dispatch_block` |
| `scan-live-diff` | `test_read_only_command_has_empty_dotnet_key` + `test_read_only_command_has_dispatch_block` |
| (subset check) | `test_read_only_commands_are_subset_of_rift_workflow` |

**Total: 7 failures** out of 191 parametrized tests (46 commands × 4 invariants + 1 subset + 6 M6.3 = 191).

**Fix path (out of M6.3 scope, follow-up commit recommended):**
1. Add 3 entries to `rift_workflow.COMMAND_MAP` (empty `dotnet`/`base` keys).
2. Add 3 minimal dispatch blocks in `rift_workflow._run_command()` — these would call the underlying scripts (`scripts/probe_modrm_leads.py` for `probe-modrm-leads`; functions in `scripts/live_memory_scanner.py` for `scan-live-values` and `scan-live-diff`).
3. Re-run `pytest tests/test_rift_read_only_no_spawn.py` — should drop to 184/184 passing.

**Why out of M6.3 scope:** The user's request was specifically M6.3 wiring for the 2 binary-signature commands. The 3 live-memory commands are a separate lane (live-memory scanning, not binary-signature extraction) and their proper dispatch requires understanding the `x64dbg_bridge.py` + `live_memory_scanner.py` integration. Best as a focused follow-up commit.

---

*End of handoff. Phases 5 + 6 of the binary-signature lane (including M6.3) are shipped to origin/main. The 3 pre-existing live-memory commands + secondary-struct mapping (M3.2) are documented follow-ups.*
