# Phase 3 M3.2 — Secondary Structs Framework (2026-07-07)

## Status vs Original Ask

The original ask was: *"Continue Phase 3 M3.2: map secondary structs
(Camera, ZoneInfo, EntityList) by running FunctionSiteSurvey against
their Ghidra targets and extending `scripts/synthesize_struct_layout.py`
to emit them alongside LocalPlayer."*

| Original ask | Shipped status | Reason |
|---|---|---|
| Camera | **Skipped** | May 2026 handoff explicitly guards `RiftReader_camera_feature` WIP |
| ZoneInfo — FunctionSiteSurvey | **Target added, survey pending** | Scanner found candidate at `0x14264da02` (MEDIUM confidence); survey is the verification step |
| ZoneInfo — Fields[] populated | **Pending** | Survey must run first to discover the actual field layout |
| EntityList — FunctionSiteSurvey | **Target NOT added** | Scanner found 0 candidates with hints `[EntityList, EntityPool, ObjectList, ActorList]`; iterated to 12 broader hints but still no discovery |
| EntityList — Fields[] populated | **Pending** | No survey address yet |
| Multi-struct synth | **Shipped** | `STRUCT_DEFINITIONS` model + `Status: pending|shipped` enum |
| Camera, ZoneInfo, EntityList **all shipped** | **Partial** | Only framework shipped; actual Ghidra runs deferred to follow-up |

**This commit ships the framework + scanner + ZoneInfo target only. The
actual FunctionSiteSurvey runs (and field population) are deferred to
follow-up commits.** A future `git log` grep MUST not interpret this
commit as "Phase 3 M3.2 DONE" — it is "Phase 3 M3.2 FRAMEWORK SHIPPED,
Ghidra runs pending."

## Design Decisions (5)

### Decision 1: Camera intentionally omitted

Per `docs/handoffs/2026-05-08-160739-rift-assets-semantic-python-nidatastream-handoff.md`:
*"Do not touch `RiftReader_camera_feature` WIP unless explicitly
authorized."* The user explicitly approved skipping Camera.

### Decision 2: Status enum has 3 states (`pending|in_progress|shipped`)

Two states (pending|shipped) miss the case where a Ghidra survey is
actively in-flight (~30 min). The 3-state enum lets future automation
distinguish "haven't started yet" from "Ghidra survey running right
now." Additive schema change, no breakage.

### Decision 3: pefile tests use mocks

Building a valid PE in-memory via pefile.PE() is non-trivial (pefile
requires either `name` or `data`). Unit tests mock pefile with
`MagicMock`; the scanner's logic (string search, RTTI detection, vtable
pattern) is what matters, not pefile re-testing. Real-binary integration
tests against `rift_x64.exe` are deferred (slow, machine-specific).

### Decision 4: `test_classify_confidence_unit` fixed to 2-arg signature

The synth's `_classify_confidence(hit_count, has_riftreader_field)` has
2 args. The test was copy-pasted from the scanner's 3-arg version
(`n_class_strings, n_rtti_typenames, n_vtables_nearby`). The synth's
confidence model is 2-dimensional, so the 2-arg signature is correct;
the test was wrong.

### Decision 5: Schema discriminator pinned

Added `test_schema_discriminator_pinned` to both test files. Asserts
the catalog's `SchemaVersion` field matches the locked constant
(`struct-layout-catalog/v1` for synth; `secondary-struct-discovery/v1`
for scanner). Prevents accidental schema bumps from regressing.

## Ship-Blockers Resolved (4)

1. **EntityList target REMOVED from registry.** Original placeholder
   was `"Address": "0x140000000"` (image base). If any consumer walked
   the registry and passed this to Ghidra, it could spawn a 30-min
   analysis run on a meaningless address. Removed entirely; re-add
   when a real candidate address is discovered.
2. **`pefile>=2024.8.26` added to `pyproject.toml [project].dependencies`.**
   The scanner does `import pefile` at runtime; this dep ensures clean
   installs work. Version verified via `pip show pefile`.
3. **Test ordering invariant documented** in
   `test_find_class_name_strings_skips_non_data_sections`. The
   `_find_class_name_strings` loop MUST check `sec_name not in
   (.rdata, .data, .rodata)` BEFORE calling `.lower()` on data. If
   anyone refactors the loop, this invariant is documented.
4. **Test renamed** `test_discover_candidates_emits_valid_schema_with_no_rdata_payload`
   → `test_discover_candidates_emits_valid_schema_with_empty_rdata`.
   The mock's `rdata_payload=b"\x00" * 0x100` is the "empty" case, not
   "no payload."

## Schema Discipline (Forward-Looking Note)

`struct-layout-catalog-v1.schema.json` has `additionalProperties: false`
on the `struct` $def. **Any new optional field on a struct MUST be
added to `properties` AND must be optional** (no `required` entry).
This is the discipline for additive evolution. The `Status` field
follows this pattern: optional in `properties`, not in `required`,
default `"shipped"`.

## Files in This Commit

| File | Type | Lines | Description |
|---|---|---|---|
| `scripts/discover_secondary_structs.py` | NEW | ~310 | pefile-based scanner; case-insensitive class-name search, RTTI TypeDescriptor detection, vtable pattern detection, confidence scoring |
| `scripts/synthesize_struct_layout.py` | MODIFIED | ~370 | Refactored to data-driven `STRUCT_DEFINITIONS` model. LocalPlayer preserved verbatim from M3.1 |
| `docs/schemas/secondary-struct-discovery-v1.schema.json` | NEW | ~60 | JSON Schema 2020-12 for scanner output |
| `docs/schemas/struct-layout-catalog-v1.schema.json` | MODIFIED | ~200 | `struct.Fields.minItems: 0` (was 1) + `Status` enum (3 states) |
| `docs/ghidra-function-site-targets.json` | MODIFIED | +5 lines | Added `phase3-zoneinfo` at `0x14264da02`; removed `phase3-entitylist` placeholder |
| `pyproject.toml` | MODIFIED | +12 lines | Added `[project]` block with `pefile>=2024.8.26` |
| `tests/test_synthesize_struct_layout.py` | NEW | ~250 | 12 tests: backward-compat LocalPlayer, empty-Fields round-trip, confidence model, schema discriminator |
| `tests/test_discover_secondary_structs.py` | NEW | ~240 | 13 tests: case-insensitive search, vtable pattern, confidence scoring, pefile mocked |

## Test Counts

- Synth tests: **12** (was 0 pre-M3.2)
- Scanner tests: **13** (was 0 pre-M3.2)
- Total: **25 new tests**, all passing
- `python scripts/synthesize_struct_layout.py --validate` → PASS
- `ruff check` → 0 errors
- `ruff format --check` → clean
- `mypy --no-error-summary` → 0 errors

## Follow-Up Commits (Documented, Not in This Commit)

### 1. ZoneInfo FunctionSiteSurvey (~30 min Ghidra run)

Run the survey against `0x14264da02`. On success, populate
`STRUCT_DEFINITIONS[ZoneInfo].Fields[]` and flip `Status` to
`"in_progress"` (during run) then `"shipped"` (on success). The
target is already in the registry.

### 2. EntityList re-discovery

The scanner found 0 candidates with the original 4 hints, and also
with the iterated 12 broader hints (`Entity, Object, Actor, World,
Unit, Character, NPC, Mob`). Next session should:

- Try a RTTI-focused pass with `rtti_typename_prefix=b".?AVActor"`,
  `b".?AVUnit"`, `b".?AVObject"` (broader mangled-name patterns)
- Or accept "no struct named EntityList in the binary" and document
  the negative result
- Re-add `phase3-entitylist` target to the registry ONLY when a real
  address is discovered (the placeholder 0x140000000 was a
  ship-blocker)

### 3. Camera authorization (deferred indefinitely)

Awaiting explicit authorization per the May 2026 WIP guard. When
authorized, the framework is already extensible to add Camera as a
4th struct to `STRUCT_DEFINITIONS` with no other changes required.

### 4. pefile test integration (slow, machine-specific)

The mocked pefile tests cover the scanner's logic. A separate
integration test against the real `rift_x64.exe` at
`C:/Program Files (x86)/Glyph/Games/RIFT/Live/rift_x64.exe` could be
added behind a `pytest.mark.slow` marker. Defer until a real-binary
CI lane exists.

## Resume Protocol

If picking back up at M3.2 Ghidra runs:

1. **ZoneInfo first** (already in registry at `0x14264da02`):

   ```bash
   python scripts/rift_read_only.py ghidra-run \
       --ghidra-project-name RiftZoneInfoSurvey \
       --ghidra-process rift_x64.exe \
       --ghidra-timeout 1800 \
       --ghidra-script scripts/ghidra/FunctionSiteSurvey.java \
       --ghidra-script-arg 0x14264da02 \
       --ghidra-script-arg Exports/ghidra-reports/phase3_zoneinfo.json
   ```

2. **Inspect the report** at `Exports/ghidra-reports/phase3_zoneinfo.json`
   to extract field offsets/names/types.
3. **Populate `STRUCT_DEFINITIONS[ZoneInfo].Fields[]`** in
   `scripts/synthesize_struct_layout.py`. Flip `Status` to `"shipped"`.
4. **Re-run synth** and commit the populated ZoneInfo struct.
5. **EntityList re-discovery** in parallel via
   `python scripts/discover_secondary_structs.py` with broader
   RTTI prefixes.

## Commit Map

| Hash | Description |
|---|---|
| `<M3.2 framework>` | This commit — framework + scanner + ZoneInfo target + 25 tests |
| `<M3.2 zoneinfo-survey>` | (Follow-up) ZoneInfo Ghidra survey + Fields[] populated |
| `<M3.2 entitylist-rediscovery>` | (Follow-up) EntityList re-discovery with RTTI-focused pass |

## Pre-Existing Test Failures (Out of M3.2 Scope)

The `test_rift_read_only_no_spawn.py` parametrized regression suite
has **7 of 184 tests failing** due to 3 live-memory commands
(`probe-modrm-leads`, `scan-live-values`, `scan-live-diff`) that are
in `rift_read_only.READ_ONLY_COMMANDS` but missing from
`rift_workflow.COMMAND_MAP` + dispatch blocks. This is a pre-existing
issue from a prior commit, **not** caused by M3.2 work. Fix is a
~10-line addition to `rift_workflow.py`; tracked as a separate
follow-up.
