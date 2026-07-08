# Binary Phase 0 Handoff — Ghidra Tooling Audit & Binary Baseline

**Date**: 2026-07-07
**Roadmap**: `docs/roadmap/binary-signature-roadmap.md` — Phase 0
**Status**: ✅ EXIT COMPLETE — all milestones met

---

## Milestones Completed

### M0.1: Ghidra Headless Pipeline Verified

- **Fixed**: Import path bug in `scripts/ghidra_runner.py` — `rift_x64.exe` is at `Exports/`, not `src/RiftAssetDumper/`. Added pre-flight `FileNotFoundError` guard (line 120).
- **Fixed**: Project lock issue — `TempProject` already existed and was locked. Switched to `RiftAnchorSurvey` project name.
- **Result**: Ghidra headless launches, imports PE, and completes with exit code 0.
- **Ghidra version**: 12.1 PUBLIC
- **JDK**: 21.0.11+10
- **Project**: `Exports/ghidra-projects/RiftAnchorSurvey.rep`

### M0.2: FunctionSiteSurvey Re-Run (8 Targets)

All 8 targets from `docs/ghidra-function-site-targets.json` surveyed against current `rift_x64.exe`:

| # | Key | Address | Status | Function Found | Report |
|---|-----|---------|--------|----------------|--------|
| 1 | twad-header-magic | `0x1406e905f` | ✅ | `FUN_1406e8e90` at `0x1406e8e90` | `twad_site_survey.json` |
| 2 | nidatastream-loadbinary | `0x141186980` | ✅ | `FUN_141186900` at `0x141186900` | `nidatastream_loadbinary_141186980.json` |
| 3 | nidatastream-semantic-adapter | `0x14111e910` | ✅ | `FUN_14111e8c0` at `0x14111e8c0` | `nidatastream_semantic_adapter_14111e910.json` |
| 4 | nimesh-material-binding-caller | `0x14111f570` | ✅ | `FUN_14111f4c0` at `0x14111f4c0` | `nimesh_material_binding_caller_14111f570.json` |
| 5 | nidatastream-descriptor-helper | `0x1411821f0` | ✅ | `FUN_1411821a0` at `0x1411821a0` | `nidatastream_descriptor_1411821f0.json` |
| 6 | nidatastream-descriptor-builder-1770 | `0x141181770` | ✅ | `FUN_141181740` at `0x141181740` | `nidatastream_descriptor_builder_141181770.json` |
| 7 | nidatastream-descriptor-builder-17c0 | `0x1411817c0` | ✅ | `FUN_141181740` at `0x141181740` | `nidatastream_descriptor_builder_1411817c0.json` |
| 8 | phase3-zoneinfo | `0x14264da02` | ❌ REFUTED | NOT a function — `.rdata` ASCII string "zone" | N/A |

**Key findings**:

- 7/8 targets confirmed as valid functions — all addresses are stable across the current binary
- Target 8 (`phase3-zoneinfo`) was correctly refuted: address `0x14264da02` is a `.rdata` string literal ("zone\x00\x00Caster is married"), not executable code. This matches the roadmap's note that this was a "medium confidence" candidate from string-based discovery.
- Functions 6 and 7 share the same entry (`FUN_141181740`) — they are two entry points within the same function body, consistent with the descriptor builder architecture.
- All JSON reports are valid and contain function metadata, instruction context, and cross-references.

### M0.3: Binary Baseline Fingerprint

Captured at `Exports/binary-phase0/binary-baseline.json`:

| Field | Value |
|-------|-------|
| File size | 60,024,256 bytes (~57 MB) |
| Image base | `0x140000000` (PE32+) |
| Entry point | `0x2480984` |
| PE timestamp | `0x0` (zeroed — no build timestamp) |
| File version | `1.0.0.0` (generic) |
| Sections | 7 (.text, .rdata, .data, .pdata, _RDATA, .rsrc, .reloc) |
| `.text` size | 39,373,824 bytes (65.6% of binary) |

**Notable**: `_RDATA` section is non-standard (likely custom linker section). PE timestamp is zeroed, so binary identification must rely on section layout + file hash.

### M0.4: `live_memory_scanner.py` Audit

**File**: `scripts/live_memory_scanner.py` (1,766 lines)

| Question | Answer |
|----------|--------|
| Scanning framework | Custom manual — `bytes.find()` + wildcard byte-by-byte; zero external dependencies |
| Input format | `label=hex` strings, `live-memory-scan-targets/v1` JSON, or `parse_wildcard_hex()` |
| Output format | JSON with `PatternResults`/`SignatureResults` (Address, MatchCount, Matches) |
| Validate uniqueness? | **Yes** — check `MatchCount == 1` via `FixtureProcessReader` |
| API | `scan_process_reader(reader, patterns, ...)` or `scan_wildcard_signatures(reader, sigs, ...)` |
| Dependencies | Pure stdlib (ctypes, json, re, struct) |
| Works with `signature-candidates.json`? | Partially — `parse_wildcard_hex()` accepts `sig_hex` directly, but no native loader for the candidate schema |

**Bug found**: Lines 588, 749 use Python 2-style `except ValueError, TypeError:` — should be `except (ValueError, TypeError):`.

**Related scripts**: `signature_match.py` already validates sig uniqueness using bytes-regex. `cross_validate_signatures.py` compares expected vs actual RVAs.

---

## Exit Criteria Met

- [x] Ghidra headless pipeline functional against current binary
- [x] All 8 catalogued function sites re-surveyed (7 confirmed, 1 refuted)
- [x] Binary baseline fingerprint recorded
- [x] Handoff committed with audit findings

## Artifacts Produced

| Artifact | Location | Gitignored |
|----------|----------|------------|
| Function site surveys (8 JSON) | `Exports/ghidra-reports/*.json` | Yes |
| Binary baseline | `Exports/binary-phase0/binary-baseline.json` | Yes |
| Ghidra project | `Exports/ghidra-projects/RiftAnchorSurvey.rep` | Yes |
| This handoff | `docs/handoffs/2026-07-07-binary-phase0-audit.md` | No (committed) |

## Fixes Applied

1. **`scripts/ghidra_runner.py`**: Added pre-flight import path validation — raises `FileNotFoundError` with helpful hint if the binary doesn't exist at the specified path.
2. **`scripts/ghidra_runner.py`**: Import path now resolved via `Path.resolve()` before passing to Ghidra, preventing double-backslash and relative-path issues.

## Recommended Next Steps

1. **Phase 1 M1.1**: Inventory RiftReader's current hardcoded offsets (LocalPlayer base, coordinate fields, facing, turn rate)
2. **Phase 1 M1.2**: Ghidra back-trace from known offsets — use ModRM scanning (1,337 sites already found) to extract concrete byte signatures
3. **Fix Python 2 except syntax** in `live_memory_scanner.py` lines 588, 749
4. **Add `load_signature_candidates_v1()` adapter** to bridge `signature-candidates.json` → `WildcardSignature` objects
5. **Run uniqueness validation** — load `.text` into `FixtureProcessReader`, feed all 8 candidate signatures, verify each produces exactly 1 match
