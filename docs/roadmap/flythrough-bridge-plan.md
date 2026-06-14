# Flythrough Bridge Plan — Assets-repo work to make RiftFlythrough production-ready

**Status**: ✅ **COMPLETE** — FT-1 through FT-7 done, FT-8 skipped (see `docs/handoffs/2026-06-10-flythrough-bridge-closure.md`)
**Version**: 2.0 (agentic rewrite)
**Created**: 2026-06-08
**Last updated**: 2026-06-10 (closure)
**Owner**: Assets repo (`RiftAssetDumper`)
**Consumer**: `C:\RIFT MODDING\RiftFlythrough` (sibling, v1.35.0, Phase 21/50 of its own roadmap)

**Naming convention**: This plan uses the **FT-1..FT-8** prefix to avoid collision with the existing **Phase 0..49** numbering in `docs/roadmap/project-roadmap.md`. The two plans are independent and address different problem spaces — the existing 0–49 plan covers NIF parser/descriptor work; this FT plan covers consumer-app integration.

**Plan status**: All 7 core phases are complete. FT-8 (mod-replacement bridge) was skipped as it conflicts with the project's read-only archive research mandate. The unified `flythrough-index.json` (217 assets, 100% cross-referenced) is the closure deliverable for RiftFlythrough consumption.

---

## 0. State (machine-checkable)

The current plan state is stored at `Assets/build/flythrough/.state.json`. An agent MUST read this file first; if absent, treat all steps as `pending`.

```json
{
  "plan": "flythrough-bridge-plan",
  "version": "2.0",
  "current_phase": "FT-1",
  "current_step": "FT-1.1",
  "phase_status": {
    "FT-1": "done",
    "FT-2": "done",
    "FT-3": "done",
    "FT-4": "done",
    "FT-5": "done",
    "FT-6": "done",
    "FT-7": "done",
    "FT-8": "skipped"
  },
  "step_status": {
    "FT-1.1": "done",
    "FT-1.2": "done",
    "..."
  },
  "plan_status": "complete",
  "last_handoff": "docs/handoffs/2026-06-10-flythrough-bridge-closure.md",
  "last_updated": "2026-06-10T04:00:00Z",
  "build_hash": null,
  "blocked_reason": null
}
```

### Status legend

| Symbol | Meaning |
|---|---|
| ⬜ pending | not started |
| 🟡 in_progress | an agent is currently working on it |
| ✅ done | acceptance criteria met, evidence committed |
| ❌ blocked | cannot proceed; `blocked_reason` populated |
| ⏸ paused | awaiting human review or external input |

### Validation command (run by any agent on resume)

```bash
python -c "import json,sys; s=json.load(open('Assets/build/flythrough/.state.json')); print(f\"current={s['current_phase']}.{s['current_step']} last_handoff={s['last_handoff']}\")"
```

---

## 1. Single-command orchestrator

After this plan is loaded, an agent should be able to make progress with one command:

```bash
# Show current state and what's next
python scripts/flythrough_plan.py status

# Run the next pending step (auto-resumes from .state.json)
python scripts/flythrough_plan.py step --next

# Run a specific step
python scripts/flythrough_plan.py step --id FT-1.3

# Mark a step done (with evidence)
python scripts/flythrough_plan.py complete --id FT-1.3 --evidence <path-to-evidence>
```

The orchestrator script (`scripts/flythrough_plan.py`) is part of **FT-5** and does not yet exist. Until then, agents work directly off this doc + manual `git commit` + `.state.json` writes.

---

## 2. Resume protocol (cold start)

When any agent (or human) opens this repo to make progress, in this order:

1. **Read** `docs/roadmap/current-phase.md` — confirms which plan is active
2. **Read** `Assets/build/flythrough/.state.json` — if it exists, the current step is `current_phase.current_step`
3. **Read** the latest handoff in `docs/handoffs/` matching `*ft{phase}-*` — gives last session context
4. **Read** the **Pre-flight** section of the current step below — run those checks first
5. **Execute** the step per its **Prompt template** and **Expected output**
6. **Validate** per the step's **Acceptance** checks
7. **Update** `.state.json` with the new current step and last handoff
8. **Commit** with the convention `ft{N}.{M}: <short description>`
9. **Hand off** by writing `docs/handoffs/2026-MM-DD-ft{N}-exit.md` (when phase exits)

---

## 3. Drift prevention (cross-phase invariants)

| Rule | Implementation | Programmatic check |
|---|---|---|
| Generated output never under `Source/`/`Extracted/`/`Exports/` root | Always under `Assets/build/flythrough/` (gitignored) | `git check-ignore Assets/build/flythrough` |
| RiftFlythrough is read-only from this repo | We only write to `RiftFlythrough/textures/converted/`, `RiftFlythrough/merged.obj`, etc. (RiftFlythrough's expected inputs) | n/a — convention only |
| Live install is read-only | Only read `C:\Program Files (x86)\Glyph\Games\RIFT\Live`; never write | file path check |
| Every step has evidence | A file under `Assets/build/flythrough/evidence/ft{N}.{M}/` | `ls Assets/build/flythrough/evidence/ft{N}.{M}/` |
| Schemas validate | `jsonschema -i <file> docs/schemas/<schema>` | `python -c "import jsonschema; jsonschema.validate(...)"` |
| No silent skips | A skipped asset must log a reason and increment `stats.skipped` | check JSON output |
| One phase = one handoff doc | `docs/handoffs/2026-MM-DD-ft{N}-exit.md` | `ls docs/handoffs/*ft{N}-*` |
| `.state.json` is gitignored but never deleted | It is the resume token | n/a |

---

## 4. Phase FT-1 — Texture Pipeline at Scale (DDS → PNG)

**Goal**: Convert all unique DDS textures in the live archive to PNG, organized for RiftFlythrough's `build_texture_map.py`.

**Why first**: RiftFlythrough *only* accepts `.png`. Without textures, faced meshes are useless.

### FT-1.1 — Discover & inventory DDS candidates

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~5k |
| **Pre-flight** | `git status --short` (clean), `python -c "import scripts.rift_workflow"` (importable) |
| **Prompt template** | "Run `python scripts/rift_workflow.py inventory-asset-signatures --type dds --live --out Assets/build/flythrough/evidence/ft1.1/dds-inventory.json`. Report the count of unique DDS candidates, the count per archive, and the top 10 texture-name patterns. Write a one-paragraph summary to evidence/ft1.1/SUMMARY.md." |
| **Expected output** | `Assets/build/flythrough/evidence/ft1.1/dds-inventory.json` (count, per-archive breakdown) + `SUMMARY.md` |
| **Acceptance** | File exists, has `count` field ≥ 9,000, JSON is valid |
| **On failure** | If inventory times out (likely, since live is slow): document in `evidence/ft1.1/TIMEOUT.md` and proceed with the `Source/` historical copy as a fallback for testing the *pipeline* (not for production output) |
| **Resume marker** | `Assets/build/flythrough/evidence/ft1.1/SUMMARY.md` |
| **Commit** | `ft1.1: dds candidate inventory (count=N)` |

### FT-1.2 — Build texture dump script

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~8k |
| **Pre-flight** | FT-1.1 done; `python scripts/live_inventory.py --help` works |
| **Prompt template** | "Create `scripts/dump_textures_for_flythrough.py` that: (1) reads the FT-1.1 inventory, (2) for each unique DDS hash, extracts the payload via `extract-archives --live --id <hash>`, (3) deduplicates by SHA1, (4) writes a deduplicated manifest. Use `--limit` for smoke tests. Mirror the option style of existing `scripts/live_inventory.py`. Write 3 unit tests for the dedup logic in `tests/test_dump_textures_for_flythrough.py`." |
| **Expected output** | `scripts/dump_textures_for_flythrough.py` + 3 unit tests |
| **Acceptance** | `pytest tests/test_dump_textures_for_flythrough.py -v` passes; ruff clean; mypy clean |
| **On failure** | If extract-archives fails on a particular hash, log + skip, do not crash |
| **Resume marker** | `scripts/dump_textures_for_flythrough.py` exists + tests pass |
| **Commit** | `ft1.2: dump_textures_for_flythrough.py with dedup + unit tests` |

### FT-1.3 — DDS → PNG conversion at scale

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~10k |
| **Pre-flight** | FT-1.2 done; `python -c "from PIL import Image"` works (Pillow installed) |
| **Prompt template** | "Modify `scripts/dump_textures_for_flythrough.py` to convert each unique DDS to PNG using Pillow. Naming convention: `<8-char-nif-hash>_<original-dds-base>.png` (lowercase, no spaces). Output to `Assets/build/flythrough/textures/converted/`. Add a `--dry-run` flag. Add a smoke test that runs on 5 textures and validates the output count, naming, and PNG validity. Document the conversion options used (mipmap handling, DXT1/3/5)." |
| **Expected output** | Updated script with PNG conversion + smoke test |
| **Acceptance** | Smoke test passes; PNG files are valid; naming matches RiftFlythrough's `build_texture_map.py` expectations |
| **On failure** | If Pillow can't decode a DDS variant, log the variant, skip, continue |
| **Resume marker** | `Assets/build/flythrough/textures/converted/` populated with PNG files |
| **Commit** | `ft1.3: dds->png conversion with smoke test` |

### FT-1.4 — End-to-end smoke into RiftFlythrough

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~6k |
| **Pre-flight** | FT-1.3 done |
| **Prompt template** | "Run `python scripts/dump_textures_for_flythrough.py --limit 100` to produce 100 deduped PNGs. Drop the output into `C:/RIFT MODDING/RiftFlythrough/textures/converted/`. Run `cd C:/RIFT MODDING/RiftFlythrough && python build_texture_map.py` and confirm it produces a non-empty `TEXTURE_MAP` JavaScript fragment. Run `python check.py` in RiftFlythrough and confirm it passes. Report the texture map size, the JS fragment, and any errors." |
| **Expected output** | `evidence/ft1.4/SMOKE_RESULT.md` with the JS fragment + pass/fail |
| **Acceptance** | `RiftFlythrough/check.py` passes; `TEXTURE_MAP` contains ≥10 entries; 0 errors |
| **On failure** | If naming mismatch, fix and retry; if Pillow decode error, document and skip those variants |
| **Resume marker** | `evidence/ft1.4/SMOKE_RESULT.md` exists with pass status |
| **Commit** | `ft1.4: riftflythrough end-to-end smoke (100 textures)` |

### FT-1.5 — Full-scale run + phase exit handoff

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~8k |
| **Pre-flight** | FT-1.4 smoke pass |
| **Prompt template** | "Run the full pipeline (no `--limit`). Measure wall-clock time and disk usage. Write a phase-exit handoff to `docs/handoffs/2026-MM-DD-ft1-exit.md` with: (1) total textures converted, (2) dedup ratio, (3) wall-clock, (4) output size, (5) any DDS variants that failed, (6) RiftFlythrough load verification. Update `.state.json`: set `FT-1` to `done`, set `current_phase` to `FT-2`, set `current_step` to `FT-2.1`." |
| **Expected output** | Handoff doc + updated `.state.json` |
| **Acceptance** | Handoff exists; `.state.json` updated; `git diff --check` passes |
| **On failure** | If any step failed, document in handoff and leave `.state.json` step in `❌ blocked` state with reason |
| **Resume marker** | `.state.json` shows `current_phase=FT-2, current_step=FT-2.1` |
| **Commit** | `ft1.5: phase exit handoff (N textures, X dedup, T wall-clock)` |

### FT-1 phase exit criteria

- [x] All 5 sub-steps ✅ in `.state.json`
- [x] `Assets/build/flythrough/textures/converted/` populated with PNGs
- [x] `RiftFlythrough/check.py` passes after texture drop
- [x] Phase-exit handoff committed
- [x] `python scripts/test_rift_workflow_utils.py` + new tests pass
- [x] CI green (build 0 errors, ruff 0, mypy 0)

---

## 5. Phase FT-2 — Bulk NIF → OBJ Export

**Goal**: Export every decodable NIF in the live install to OBJ, building toward a full `merged.obj`.

### FT-2.1 — Design bulk driver signature

| Field | Value |
|---|---|
| **Agent** | `cs-architect-gpt` (GPT-5.5, high) — *this is a multi-system design decision* |
| **Token budget** | ~12k |
| **Pre-flight** | FT-1 done; existing `decode-nif-geometry --help` and `bulk_export_sibling.py` reviewed |
| **Prompt template** | "Read `scripts/batch_export_sibling.py`, `scripts/batch_export_mb6.py`, and the C# `decode-nif-geometry` command. Design the function signature and CLI for `scripts/bulk_export_for_flythrough.py` that: (1) takes a list of NIF hashes (from inventory or from a file), (2) runs decode-nif-geometry per hash with `--export-obj`, (3) collects OBJs into `Assets/build/flythrough/objs/<hash>.obj`, (4) writes a per-run JSON manifest, (5) supports `--limit`, `--mesh-size-families`, `--output-dir`, `--skip-on-error`, `--resume`. Document the design in `evidence/ft2.1/DESIGN.md`." |
| **Expected output** | `evidence/ft2.1/DESIGN.md` with function signature, CLI, error handling, idempotency notes |
| **Acceptance** | Design doc exists; reviewed against existing scripts; 1 round of `code-reviewer-lite` passes |
| **On failure** | If design conflicts with existing tools, escalate to `cs-architect-gpt` for redesign |
| **Resume marker** | `evidence/ft2.1/DESIGN.md` |
| **Commit** | `ft2.1: bulk export driver design` |

### FT-2.2 — Implement bulk driver

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~15k |
| **Pre-flight** | FT-2.1 design approved |
| **Prompt template** | "Implement `scripts/bulk_export_for_flythrough.py` per the FT-2.1 design. Mirror the option style of `scripts/rift_workflow.py`. Use `subprocess.run` to call the .NET CLI. Add structured logging via `structlog` or stdlib `logging`. Add `--dry-run`. Add 5 unit tests in `tests/test_bulk_export_for_flythrough.py` covering: empty input, single mesh, error on one mesh, resume after error, --limit." |
| **Expected output** | Script + 5 unit tests |
| **Acceptance** | All tests pass; ruff clean; mypy clean; `--dry-run` does not invoke .NET |
| **On failure** | If a NIF fails to decode, the script must log + skip + continue (per `--skip-on-error`); never crash the whole run |
| **Resume marker** | `scripts/bulk_export_for_flythrough.py --help` shows full signature |
| **Commit** | `ft2.2: bulk_export_for_flythrough.py implementation` |

### FT-2.3 — Smoke run (50 NIFs)

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~8k |
| **Pre-flight** | FT-2.2 done |
| **Prompt template** | "Run `python scripts/bulk_export_for_flythrough.py --limit 50 --output-dir Assets/build/flythrough/objs/`. Validate: (1) ≥40 of 50 NIFs produce OBJs (≥80% success), (2) each OBJ passes `RiftFlythrough/validate_obj.py`, (3) per-OBJ manifest is valid JSON. Write `evidence/ft2.3/SMOKE.md` with the run summary, success rate, and any NIFs that failed (with reason)." |
| **Expected output** | 40+ OBJs in `Assets/build/flythrough/objs/` + smoke report |
| **Acceptance** | ≥80% success; all OBJs pass `validate_obj.py`; smoke report exists |
| **On failure** | If <80% success, halt; investigate the failures; do NOT proceed to full run |
| **Resume marker** | `evidence/ft2.3/SMOKE.md` with success_rate field |
| **Commit** | `ft2.3: bulk export smoke (50 NIFs, X% success)` |

### FT-2.4 — Failure triage + guard

| Field | Value |
|---|---|
| **Agent** | `investigator-gpt` (GPT-5.1, high) — *failure pattern recognition* |
| **Token budget** | ~10k |
| **Pre-flight** | FT-2.3 smoke shows ≥1 failure |
| **Prompt template** | "Read the failures from `evidence/ft2.3/SMOKE.md`. Categorize them by failure mode (parse error, missing stream, validation failure, IO error, other). For each category with ≥2 occurrences, document a proposed fix in `evidence/ft2.4/TRIAGE.md`. If the failure is a real decoder bug, file it as a Phase 0-49 task (do not fix here — that's a different plan). If it's an export-tooling issue, fix it in this lane. Add a guard test that fails if a known-bad NIF is encountered." |
| **Expected output** | `evidence/ft2.4/TRIAGE.md` with categorized failures + fixes/filings |
| **Acceptance** | Triage doc exists; all categories addressed (fixed or filed elsewhere); guard test added |
| **On failure** | If triage can't categorize, escalate to `cs-architect-gpt` |
| **Resume marker** | `evidence/ft2.4/TRIAGE.md` with `guard_test_added: true` |
| **Commit** | `ft2.4: bulk export failure triage + guard` |

### FT-2.5 — Full-scale run + phase exit handoff

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~12k |
| **Pre-flight** | FT-2.3 ≥80% success; FT-2.4 triage addressed |
| **Prompt template** | "Run the full pipeline: `python scripts/bulk_export_for_flythrough.py --output-dir Assets/build/flythrough/objs/`. Use a single long-running tmux session (`tmux new -d -s ft2`) if needed. Measure wall-clock, total OBJ count, total size, success rate, failure rate by category. Generate `merged.obj` by running `python C:/RIFT MODDING/RiftFlythrough/merge_objs.py --objs-dir Assets/build/flythrough/objs/`. Validate via `python C:/RIFT MODDING/RiftFlythrough/validate_obj.py merged.obj`. Write `docs/handoffs/2026-MM-DD-ft2-exit.md` with all metrics. Update `.state.json`." |
| **Expected output** | Handoff doc + `.state.json` updated + `merged.obj` in `Assets/build/flythrough/` |
| **Acceptance** | ≥1,000 OBJs exported; merged.obj generated; validate_obj passes; handoff committed |
| **On failure** | If full run fails midway, use `--resume` to continue from where it stopped |
| **Resume marker** | `.state.json` shows `current_phase=FT-3, current_step=FT-3.1` |
| **Commit** | `ft2.5: phase exit handoff (N OBJs, M% success, T wall-clock)` |

### FT-2 phase exit criteria

- [x] All 5 sub-steps ✅
- [x] `Assets/build/flythrough/merged.obj` generated and validated
- [x] ≥1,000 OBJs (or the live install's full decodable NIF count, whichever is smaller)
- [x] Failure rate documented; known failures triaged
- [x] Phase-exit handoff committed
- [x] CI green

---

## 6. Phase FT-3 — Per-OBJ Metadata Sidecar (Manifest v1)

**Goal**: Emit a JSON sidecar per OBJ with NIF hash, mesh block, manifest row, asset ID, parent node, linked textures, sibling IDs, original-path candidates.

### FT-3.1 — Schema design

| Field | Value |
|---|---|
| **Agent** | `cs-architect-gpt` (GPT-5.5, high) |
| **Token budget** | ~10k |
| **Pre-flight** | FT-2 done; RiftFlythrough `catalog.js` reviewed |
| **Prompt template** | "Design `asset-mesh-manifest-v1.schema.json` for per-OBJ metadata. Required fields: `nif_hash`, `mesh_block`, `manifest_row`, `asset_id`, `mesh_size`, `vertex_count`, `face_count`, `position_descriptor`, `export_timestamp`, `export_command`, `parent_node`, `sibling_meshes`, `linked_textures`, `original_path_candidates`. Optional: `bounding_box`, `transform` (FT-4), `zone_id` (FT-7). Save the schema to `docs/schemas/asset-mesh-manifest-v1.schema.json`. Add a 5-row example to `evidence/ft3.1/EXAMPLE.json`." |
| **Expected output** | Schema + 5-row example |
| **Acceptance** | `jsonschema -i evidence/ft3.1/EXAMPLE.json docs/schemas/asset-mesh-manifest-v1.schema.json` passes |
| **On failure** | If schema is too restrictive, loosen optional fields |
| **Resume marker** | `docs/schemas/asset-mesh-manifest-v1.schema.json` |
| **Commit** | `ft3.1: asset-mesh-manifest-v1 schema` |

### FT-3.2 — Manifest emitter

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~10k |
| **Pre-flight** | FT-3.1 done |
| **Prompt template** | "Create `scripts/emit_mesh_manifest.py` that: (1) takes a list of OBJ paths, (2) for each, parses the OBJ group name to extract NIF hash, (3) joins with FT-2 inventory data to fill manifest fields, (4) writes `<obj_path>.manifest.json` next to each OBJ, (5) validates against the schema. Hook this into `scripts/bulk_export_for_flythrough.py` so manifests are emitted alongside OBJs. Add 3 unit tests for the OBJ-name parser." |
| **Expected output** | Emitter + tests + hook into bulk exporter |
| **Acceptance** | All tests pass; bulk export now produces `.manifest.json` siblings; schema validation passes |
| **On failure** | If schema validation fails on a real manifest, fix the emitter (not the schema) |
| **Resume marker** | `scripts/emit_mesh_manifest.py` works on a sample OBJ |
| **Commit** | `ft3.2: emit_mesh_manifest.py + bulk export hook` |

### FT-3.3 — RiftFlythrough load test

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~6k |
| **Pre-flight** | FT-3.2 done |
| **Prompt template** | "Pick 50 sample OBJs from `Assets/build/flythrough/objs/`. Write a small test that: (1) loads each `<obj>.manifest.json` in RiftFlythrough, (2) prints the catalog entries (mirroring how `catalog.js` would consume them), (3) reports any errors. Write `evidence/ft3.3/RIFTFLYTHROUGH_LOAD.md` with the test code, output, and any field mismatches. If there are mismatches, decide: schema fix or RiftFlythrough `catalog.js` fix." |
| **Expected output** | Load test + result doc |
| **Acceptance** | All 50 manifests parse; `catalog.js`-style consumption works; 0 errors |
| **On failure** | Document the mismatch; propose a fix; do NOT change the schema without re-validating with FT-3.1 |
| **Resume marker** | `evidence/ft3.3/RIFTFLYTHROUGH_LOAD.md` with pass status |
| **Commit** | `ft3.3: riftflythrough manifest load test` |

### FT-3.4 — Full-scale re-run + phase exit handoff

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~8k |
| **Pre-flight** | FT-3.3 pass |
| **Prompt template** | "Re-run `python scripts/bulk_export_for_flythrough.py` (which now emits manifests) end-to-end. Validate: every OBJ has a sibling `.manifest.json`; every manifest passes schema validation; 0 broken references. Write `docs/handoffs/2026-MM-DD-ft3-exit.md` with: count of manifests, schema validation summary, RiftFlythrough load verification, and any fields where most manifests have nulls (indicates a missing data source). Update `.state.json`." |
| **Expected output** | Handoff doc + `.state.json` updated |
| **Acceptance** | All OBJs have manifests; all validate; handoff committed |
| **On failure** | If schema mismatch, halt; investigate |
| **Resume marker** | `.state.json` shows `current_phase=FT-4, current_step=FT-4.1` |
| **Commit** | `ft3.4: phase exit handoff (N manifests, all valid)` |

### FT-3 phase exit criteria

- [x] All 4 sub-steps ✅
- [x] Every OBJ has a valid `.manifest.json` sibling
- [x] RiftFlythrough `catalog.js` consumes them without error
- [x] Phase-exit handoff committed
- [x] CI green

---

## 7. Phase FT-4 — World Placement & Scene Graph Extraction ⭐ KEYSTONE

**Goal**: Extract per-mesh world transforms (position, rotation, scale) and parent-child hierarchy from NIF `NiNode`/`NiMesh` blocks so meshes render at correct world positions in RiftFlythrough.

**This is the highest-risk phase**. The Assets repo has never done this; the proof is at the candidate level. Use a **50-NIF pilot first**, not the full 5,111.

### FT-4.1 — NiNode field inventory

| Field | Value |
|---|---|
| **Agent** | `investigator-gpt` (GPT-5.1, high) |
| **Token budget** | ~12k |
| **Pre-flight** | FT-3 done; existing NIF probe code reviewed |
| **Prompt template** | "Read the C# NIF parser's `NiNode` block handling. Identify which fields in the NiNode block payload contain: (1) world transform (translation/rotation/scale), (2) parent reference, (3) child references. Also check `NiMesh` for inline transform fields. Document in `evidence/ft4.1/NINODE_FIELDS.md` with byte offsets, types, and example values from 3 hand-picked multi-mesh NIFs. Identify which fields are consistent vs variant." |
| **Expected output** | Field map with byte offsets, types, examples |
| **Acceptance** | Field map exists; ≥3 multi-mesh NIFs analyzed; clear distinction between consistent and variant fields |
| **On failure** | If fields are too variant, escalate to `cs-architect-gpt` for multi-strategy approach |
| **Resume marker** | `evidence/ft4.1/NINODE_FIELDS.md` |
| **Commit** | `ft4.1: NiNode field inventory` |

### FT-4.2 — Scene graph probe command

| Field | Value |
|---|---|
| **Agent** | `cs-architect-gpt` (GPT-5.5, high) — *new C# command, complex* |
| **Token budget** | ~20k |
| **Pre-flight** | FT-4.1 done |
| **Prompt template** | "Add a C# command `probe-nif-scene-graph --id <hash> --mesh-block <n>` to `Program.cs`. It should: (1) read the NIF block table, (2) for each `NiNode` block, decode the transform fields, (3) build a tree of parent-child relationships, (4) for each `NiMesh` block, attach to its parent NiNode, (5) emit a JSON report with the full tree. Document the JSON schema in `evidence/ft4.2/SCHEMA.md`. Add 3 xUnit tests." |
| **Expected output** | New C# command + schema + tests |
| **Acceptance** | `dotnet build` 0 errors; `dotnet test` passes including new tests; `probe-nif-scene-graph --id <known multi-mesh NIF>` returns a non-empty tree |
| **On failure** | If transform decode is ambiguous, document the ambiguity; do NOT guess |
| **Resume marker** | `probe-nif-scene-graph` runs on at least one NIF |
| **Commit** | `ft4.2: probe-nif-scene-graph command` |

### FT-4.3 — 50-NIF pilot

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~10k |
| **Pre-flight** | FT-4.2 done |
| **Prompt template** | "Pick 50 multi-mesh NIFs from the live install (use `inventory-nif-mesh-bindings` to find NIFs with ≥2 NiMesh blocks). Run `probe-nif-scene-graph` on each. For each, validate: (1) tree depth ≥1, (2) at least 1 child relationship, (3) all transforms are finite floats, (4) no orphan meshes. Write `evidence/ft4.3/PILOT.md` with success rate, common failure modes, and a decision: GREEN (proceed to FT-4.4), YELLOW (proceed with caveats, document), RED (halt, redesign)." |
| **Expected output** | Pilot report with GREEN/YELLOW/RED decision |
| **Acceptance** | ≥70% success → GREEN; 50-70% → YELLOW; <50% → RED |
| **On failure** | RED: redesign probe; do NOT proceed to FT-4.4 |
| **Resume marker** | `evidence/ft4.3/PILOT.md` with decision field |
| **Commit** | `ft4.3: scene graph 50-NIF pilot (X% success, <decision>)` |

### FT-4.4 — world.json schema + bulk integration

| Field | Value |
|---|---|
| **Agent** | `cs-architect-gpt` (GPT-5.5, high) |
| **Token budget** | ~15k |
| **Pre-flight** | FT-4.3 GREEN or YELLOW |
| **Prompt template** | "Design `docs/schemas/scene-graph-v1.schema.json` for the per-NIF `world.json` sidecar. Required fields: `nif_hash`, `roots[]` (top-level NiNodes with transform), `meshes[]` (each with `mesh_block`, `parent_node`, `local_transform`, `world_transform`). Integrate scene-graph extraction into `scripts/bulk_export_for_flythrough.py` so every NIF with ≥2 meshes gets a `world.json` written next to its OBJ. Add 3 unit tests for the JSON writer. Update `asset-mesh-manifest-v1.schema.json` to reference the new transform field." |
| **Expected output** | Schema + integration + tests |
| **Acceptance** | Schemas validate; bulk export produces `world.json` for multi-mesh NIFs; tests pass |
| **On failure** | If world.json conflicts with manifest schema, reconcile both |
| **Resume marker** | `docs/schemas/scene-graph-v1.schema.json` + sample `world.json` |
| **Commit** | `ft4.4: scene-graph-v1 schema + bulk integration` |

### FT-4.5 — Three.js round-trip validation

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~10k |
| **Pre-flight** | FT-4.4 done |
| **Prompt template** | "Write a small Three.js script (in `C:/RIFT MODDING/RiftFlythrough/tests/`) that: (1) loads 5 OBJs from `Assets/build/flythrough/objs/`, (2) loads their `world.json`, (3) applies the world transforms to the OBJs in a Three.js scene, (4) renders a screenshot. Visually confirm the meshes appear at sensible world positions (not all stacked at origin). Save the screenshot to `evidence/ft4.5/render.png`. Write `evidence/ft4.5/ROUNDTRIP.md` with the screenshot reference, the script, and pass/fail." |
| **Expected output** | Round-trip test + screenshot + report |
| **Acceptance** | Screenshot shows meshes at distinct world positions; pass documented |
| **On failure** | If meshes are still stacked, halt; transforms are wrong; debug FT-4.1–4.4 |
| **Resume marker** | `evidence/ft4.5/render.png` shows distributed geometry |
| **Commit** | `ft4.5: three.js scene-graph round-trip` |

### FT-4.6 — Full-scale run + phase exit handoff

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~15k |
| **Pre-flight** | FT-4.5 pass |
| **Prompt template** | "Re-run bulk export with scene-graph extraction. Measure: NIF coverage, world.json count, transform success rate, wall-clock. Write `docs/handoffs/2026-MM-DD-ft4-exit.md` with: keystone-metric (the % of multi-mesh NIFs with valid world.json), validation screenshots, and any NIF families where transforms are still wrong. Update `.state.json`." |
| **Expected output** | Handoff doc + `.state.json` updated |
| **Acceptance** | ≥70% of multi-mesh NIFs have valid `world.json`; handoff committed |
| **On failure** | If <70%, leave `.state.json` at FT-4 with `blocked_reason` |
| **Resume marker** | `.state.json` shows `current_phase=FT-5, current_step=FT-5.1` |
| **Commit** | `ft4.6: phase exit handoff (X% world.json coverage)` |

### FT-4 phase exit criteria

- [x] All 6 sub-steps ✅
- [x] Keystones: Three.js round-trip shows distributed geometry; ≥70% multi-mesh NIF coverage
- [x] `world.json` schema committed and validated
- [x] Phase-exit handoff committed
- [x] CI green
- [x] **This is the keystone phase** — do NOT proceed to FT-5 without explicit pass

---

## 8. Phase FT-5 — Single-Command Pipeline Integration

**Goal**: `python scripts/build_flythrough_build.py` produces a complete RiftFlythrough-ready asset set.

### FT-5.1 — Orchestrator script skeleton

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~12k |
| **Pre-flight** | FT-1, FT-2, FT-3, FT-4 all done |
| **Prompt template** | "Create `scripts/build_flythrough_build.py` with subcommands: `status`, `step --next`, `step --id <X.Y>`, `complete --id <X.Y> --evidence <path>`. It reads/writes `.state.json`. Add 5 unit tests in `tests/test_build_flythrough_build.py` covering: status, step resolution, complete, idempotency, missing state file." |
| **Expected output** | Orchestrator + tests |
| **Acceptance** | Tests pass; `python scripts/build_flythrough_build.py status` works |
| **On failure** | If state file race conditions occur, add file locking |
| **Resume marker** | Orchestrator works on existing state |
| **Commit** | `ft5.1: build_flythrough_build.py orchestrator skeleton` |

### FT-5.2 — Full pipeline stages wired in

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~15k |
| **Pre-flight** | FT-5.1 done |
| **Prompt template** | "Wire the orchestrator to invoke: (1) `dump_textures_for_flythrough.py` (FT-1), (2) `bulk_export_for_flythrough.py` (FT-2/3/4), (3) `RiftFlythrough/merge_objs.py`, (4) `RiftFlythrough/validate_obj.py`. Each stage writes to `.state.json`. The orchestrator must be resume-safe: if interrupted, `--next` continues from the last incomplete stage. Add 3 integration tests." |
| **Expected output** | Wired orchestrator + integration tests |
| **Acceptance** | All stages run end-to-end; resume works; tests pass |
| **On failure** | If a stage's output is missing, skip and continue; do not abort the whole build |
| **Resume marker** | Orchestrator can build from cold and resume from any state |
| **Commit** | `ft5.2: full pipeline stages wired into orchestrator` |

### FT-5.3 — Incremental rebuild via content-hash cache

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~10k |
| **Pre-flight** | FT-5.2 done |
| **Prompt template** | "Add incremental rebuild: cache a SHA256 of (live archive mtime + script version + config). If unchanged, skip stages whose outputs already exist and validate them. If changed, invalidate and rebuild only the changed stage. Add `--rebuild-all` to force. Write `evidence/ft5.3/CACHE.md` with the cache design and a measurement of cold vs warm build times." |
| **Expected output** | Cache layer + measurement |
| **Acceptance** | Warm rebuild <30 sec; cold rebuild <30 min; cache invalidation works on live archive change |
| **On failure** | If cache hit rate is too low, document and consider per-asset caching |
| **Resume marker** | `evidence/ft5.3/CACHE.md` shows cold vs warm timings |
| **Commit** | `ft5.3: content-hash cache + incremental rebuild` |

### FT-5.4 — BUILD_INFO.json + phase exit handoff

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~8k |
| **Pre-flight** | FT-5.3 done |
| **Prompt template** | "Emit `Assets/build/flythrough/BUILD_INFO.json` after each build with: build_id (UUID), build_timestamp, total_obj_count, total_obj_size_bytes, total_texture_count, total_texture_size_bytes, total_manifest_count, total_world_json_count, script_versions, live_archive_hash. Write `docs/handoffs/2026-MM-DD-ft5-exit.md` with: cold/warm timings, BUILD_INFO example, RiftFlythrough drop-in test result. Update `.state.json`." |
| **Expected output** | Handoff + `.state.json` updated |
| **Acceptance** | BUILD_INFO.json valid; handoff committed; cold build measured |
| **Resume marker** | `.state.json` shows `current_phase=FT-6, current_step=FT-6.1` |
| **Commit** | `ft5.4: BUILD_INFO.json + phase exit handoff` |

### FT-5 phase exit criteria

- [x] All 4 sub-steps ✅
- [x] `python scripts/build_flythrough_build.py` runs end-to-end
- [x] Cold build <30 min, warm build <30 sec
- [x] BUILD_INFO.json emitted
- [x] Phase-exit handoff committed
- [x] CI green

---

## 9. Phase FT-6 — Flythrough-Specific Validation Suite

**Goal**: Automated test that drops the build into RiftFlythrough and checks it loads cleanly.

### FT-6.1 — Drop-in smoke test

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~10k |
| **Pre-flight** | FT-5 done |
| **Prompt template** | "Create `scripts/test_flythrough_build.py` that: (1) copies `Assets/build/flythrough/textures/converted/` to `C:/RIFT MODDING/RiftFlythrough/textures/converted/`, (2) copies `Assets/build/flythrough/merged.obj` to `C:/RIFT MODDING/RiftFlythrough/merged.obj`, (3) runs `cd C:/RIFT MODDING/RiftFlythrough && python check.py`, (4) runs `python validate_obj.py merged.obj`, (5) reports pass/fail. Add 2 unit tests mocking the copy and check steps." |
| **Expected output** | Test script + unit tests |
| **Acceptance** | Script runs successfully; unit tests pass; check.py and validate_obj.py pass on real build |
| **On failure** | If check.py fails, surface the exact check that failed; do not modify RiftFlythrough to pass |
| **Resume marker** | Script exists and runs |
| **Commit** | `ft6.1: test_flythrough_build.py drop-in smoke` |

### FT-6.2 — Headless render test

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~12k |
| **Pre-flight** | FT-6.1 done |
| **Prompt template** | "Extend `test_flythrough_build.py` with a headless render test: (1) start a tmux session running `python dev.py` in RiftFlythrough, (2) use `browser-use` (or a headless Chrome) to load `http://localhost:8000`, (3) wait for the page to fully load, (4) take a screenshot, (5) check console for errors. Save the screenshot to `evidence/ft6.2/screenshot.png`. Document in `evidence/ft6.2/HEADLESS.md`." |
| **Expected output** | Headless test + screenshot + report |
| **Acceptance** | Screenshot captured; 0 console errors; page loads merged.obj + textures |
| **On failure** | If console errors, surface them; do not patch RiftFlythrough to silence them |
| **Resume marker** | `evidence/ft6.2/screenshot.png` shows rendered scene |
| **Commit** | `ft6.2: headless render test` |

### FT-6.3 — Visual regression baseline + phase exit handoff

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~10k |
| **Pre-flight** | FT-6.2 done |
| **Prompt template** | "Add a visual regression check: compare `evidence/ft6.2/screenshot.png` against `evidence/ft6.2/baseline.png` (first-run baseline). Tolerance: 5% pixel diff. If outside tolerance, fail the test and require human review. Add 2 unit tests for the diff function. Write `docs/handoffs/2026-MM-DD-ft6-exit.md` with: the visual regression design, the test results, and the production-readiness verdict. Update `.state.json`." |
| **Expected output** | Regression test + handoff + `.state.json` |
| **Acceptance** | Regression test added; handoff committed; verdict is GO or NO-GO for production |
| **On failure** | NO-GO: list the specific gaps; leave `.state.json` at FT-6 with `blocked_reason` |
| **Resume marker** | `.state.json` shows `current_phase=FT-7, current_step=FT-7.1` (or FT-6 blocked) |
| **Commit** | `ft6.3: visual regression baseline + phase exit handoff` |

### FT-6 phase exit criteria

- [x] All 3 sub-steps ✅
- [x] Visual regression baseline exists
- [x] Production-readiness verdict in handoff
- [x] CI green

---

## 10. Phase FT-7 — Coordinate System, Zone Boundaries, LOD Variants

**Goal**: Extract zone ID, terrain tile, LOD index per mesh; produce zone-partitioned asset sets.

### FT-7.1 — Zone metadata discovery

| Field | Value |
|---|---|
| **Agent** | `investigator-gpt` (GPT-5.1, high) |
| **Token budget** | ~15k |
| **Pre-flight** | FT-6 done |
| **Prompt template** | "Investigate where zone/terrain metadata lives in the live archive. Candidates: (1) NIF `NiStringExtraData` with zone-like strings, (2) external `.dat` files in archive roots, (3) manifest Table 1 strings. Cross-reference with the asset-semantic-index from `build-asset-semantic-index`. Document findings in `evidence/ft7.1/ZONE_METADATA.md`. If found, design a probe. If NOT found, document the negative result and skip to FT-7.3." |
| **Expected output** | Investigation report |
| **Acceptance** | Either: probe design committed, or negative result documented |
| **On failure** | If ambiguous, leave it; do not guess |
| **Resume marker** | `evidence/ft7.1/ZONE_METADATA.md` |
| **Commit** | `ft7.1: zone metadata discovery` |

### FT-7.2 — LOD variant detection

| Field | Value |
|---|---|
| **Agent** | `investigator-gpt` (GPT-5.1, high) |
| **Token budget** | ~12k |
| **Pre-flight** | FT-7.1 done (regardless of result) |
| **Prompt template** | "Investigate whether NIFs have LOD variants (multiple `NiMesh` blocks at decreasing vertex count, or sibling NIFs with the same hash prefix at different vertex counts). Document in `evidence/ft7.2/LOD_VARIANTS.md` with a 5-NIF sample. If found, design a `lod_index` field for the manifest schema (additive, optional)." |
| **Expected output** | Investigation report + optional schema addition |
| **Acceptance** | Either: lod_index added to schema and validated, or negative result documented |
| **On failure** | n/a — investigation may produce negative result |
| **Resume marker** | `evidence/ft7.2/LOD_VARIANTS.md` |
| **Commit** | `ft7.2: lod variant investigation` |

### FT-7.3 — Zone-partitioned builds

| Field | Value |
|---|---|
| **Agent** | `program-cs-editor` (Flash, high) |
| **Token budget** | ~12k |
| **Pre-flight** | FT-7.1, FT-7.2 done |
| **Prompt template** | "If zone metadata was found in FT-7.1: extend the orchestrator to produce zone-partitioned `merged.obj` files (one per zone) plus an index `zone_index.json`. If NOT found: skip; document the gap. Validate at least one zone's merged.obj in RiftFlythrough (if zones exist). Write `docs/handoffs/2026-MM-DD-ft7-exit.md`. Update `.state.json`." |
| **Expected output** | Zone-partitioned builds (or skip doc) + handoff |
| **Acceptance** | Handoff committed; RiftFlythrough loads zone-partitioned output (if applicable) |
| **On failure** | If RiftFlythrough doesn't support multi-zone loads, document and add as FT-7 future work |
| **Resume marker** | `.state.json` shows `current_phase=FT-8, current_step=FT-8.1` (or FT-7 blocked) |
| **Commit** | `ft7.3: zone-partitioned builds + phase exit handoff` |

### FT-7 phase exit criteria

- [x] All 3 sub-steps ✅
- [x] Either zone-partitioned builds exist, or the gap is documented
- [x] Phase-exit handoff committed
- [x] CI green

---

## 11. Phase FT-8 — Mod-Replacement Bridge (Optional)

**Goal**: Use the proven pipeline to *write back* to the game — not just read it.

> **⚠️ HIGH-RISK PHASE — extra-high reasoning required per `docs/task-routing-safety-policy.md`.** All FT-8 work must use `safety-guardian` for pre-commit review.

### FT-8.1 — Injection design + safety review

| Field | Value |
|---|---|
| **Agent** | `cs-architect-gpt` (GPT-5.5, high) + `safety-guardian` review |
| **Token budget** | ~25k |
| **Pre-flight** | FT-7 done |
| **Prompt template** | "Design `scripts/inject_flythrough_assets.py` for injecting modified OBJs/textures back into a `TWAD` archive. Read the C# `extract-archives` flow in reverse. The injection must: (1) re-pack the entry using the original compression, (2) update the manifest checksum, (3) write to a NEW archive (never overwrite the live one), (4) require a `--live-backup` flag that copies the live archive to a safe location first. Submit the design to `safety-guardian` for review BEFORE any code is written. The safety review must produce a `evidence/ft8.1/SAFETY_REVIEW.md` with explicit pass/fail." |
| **Expected output** | Design + safety review |
| **Acceptance** | Safety review pass; design reviewed; no code written yet |
| **On failure** | If safety review fails, redesign; do NOT proceed to code |
| **Resume marker** | `evidence/ft8.1/SAFETY_REVIEW.md` with pass |
| **Commit** | `ft8.1: injection design + safety review` |

### FT-8.2 through FT-8.5 — Implementation, smoke, full run, handoff

(Follow same agentic step pattern. Each sub-step is a separate commit, with `safety-guardian` review at FT-8.3 and FT-8.5. The smoke must round-trip a single modified mesh: extract → edit → inject → verify via RiftReader. Full run only proceeds after the smoke passes.)

### FT-8 phase exit criteria

- [ ] Safety review pass at every step
- [ ] A single mesh round-trips through RiftReader
- [ ] Live archive is NEVER modified
- [ ] Phase-exit handoff committed
- [ ] CI green

---

## 12. Execution dependencies (DAG)

```
FT-1 ──┐
       ├─► FT-3 ──┐
FT-2 ──┘         │
                 ├──► FT-5 ──► FT-6 ──► FT-7 ──► FT-8
FT-4 (keystone) ─┘
```

| Parallel group | Phases | Comment |
|---|---|---|
| Group A | FT-1, FT-2 | Independent; can run in parallel via separate worktrees |
| Group B | FT-3, FT-4 | FT-3 depends on FT-1+FT-2; FT-4 independent but benefits from FT-2's inventory |
| Group C | FT-5, FT-6 | Sequential; integration then validation |
| Group D | FT-7, FT-8 | Sequential; FT-8 always last and gated by safety review |

---

## 13. Drift prevention (cross-phase invariants)

| Rule | Programmatic check |
|---|---|
| `.state.json` is the single source of truth for "what's next" | `cat Assets/build/flythrough/.state.json` |
| Each step has evidence | `ls Assets/build/flythrough/evidence/ft{N}.{M}/` |
| Generated output under `Assets/build/flythrough/` | `git check-ignore Assets/build/flythrough` |
| Each phase has a handoff | `ls docs/handoffs/*ft{N}-*` |
| No live game writes | grep for `C:\\\\Program Files.*Live` in scripts; should be read-only |
| No RiftFlythrough edits from this repo | grep for `cd C:/RIFT MODDING/RiftFlythrough &&` — should only be in tests/evidence, not in build scripts |
| Schemas validate | `python -c "import jsonschema, json; jsonschema.validate(json.load(open(p)), json.load(open(s)))"` for each schema+sample |
| All C# changes go through `dotnet build` + `dotnet test` | `dotnet build RiftAssetDumper.slnx --nologo && dotnet test RiftAssetDumper.slnx --nologo` |
| All Python changes go through ruff + mypy + tests | `ruff check scripts/ tests/ && mypy scripts/ tests/ --no-error-summary && pytest tests/ -q` |

---

## 14. Mapping to RiftFlythrough's own 50-phase roadmap

RiftFlythrough is at Phase 21 (LOD) of its own plan. This Assets-side FT plan feeds:

| RiftFlythrough phase | Needs from Assets | FT phase that delivers |
|---|---|---|
| Phase 21 (LOD) | LOD variants, zone partitioning | FT-7 |
| Phase 22+ (production launch) | Bulk coverage, full textures, transforms | FT-1, FT-2, FT-4 |
| Future: mod-replace mode | Asset manifest, graph | FT-3, FT-8 |

RiftFlythrough's phases 1-20 are pure viewer/UI work and don't depend on Assets. The dependency starts at Phase 21.

---

## 15. Total effort projection

| Phase | Effort | Cumulative |
|---|---:|---:|
| FT-1 (DDS→PNG) | 2–3 d | 2–3 d |
| FT-2 (Bulk export) | 1 wk | 1.5 wk |
| FT-3 (Manifest) | 3–4 d | 2.5 wk |
| FT-4 (Scene graph keystone) | 2–3 wk | 5.5 wk |
| FT-5 (Pipeline integration) | 1 wk | 6.5 wk |
| FT-6 (Validation) | 1 wk | 7.5 wk |
| FT-7 (Zones/LOD) | 2–3 wk | 10 wk |
| FT-8 (Mod-bridge, optional) | 4+ wk | 14+ wk |

**RiftFlythrough production-ready as a viewer**: ~7.5 weeks (FT-1 → FT-6).
**RiftFlythrough production-ready with zones/LOD**: ~10 weeks.
**Full mod-replacement**: ~14+ weeks.

---

## 16. Optimal agent routing (per the existing model strategy)

| Work type | Agent | Model | Why |
|---|---|---|---|
| Routine Python script | `program-cs-editor` | DeepSeek V4 Flash (high) | Cost-effective, well-tested patterns |
| New C# command, complex | `cs-architect-gpt` | GPT-5.5 (high) | Multi-step reasoning across 15K-line `Program.cs` |
| Stream data investigation | `investigator-gpt` | GPT-5.1 (high) | Pattern recognition, experimental decode |
| Schema design | `cs-architect-gpt` | GPT-5.5 (high) | Cross-system contract design |
| Proof guard design | `proof-guard-agent` | DeepSeek V4 Flash (high) | Domain-specific |
| Pre-commit safety | `safety-guardian` | DeepSeek V4 Flash (high) | Required for FT-8 |
| Code review | `code-reviewer-lite` | DeepSeek V4 Flash | Mechanical, well-bounded |
| Smoke command runs | `basher` | — | Shell only, no LLM |
| Obj integrity check | `obj-export-validator` | DeepSeek V4 Flash | Domain-specific |

---

## 17. Resume protocol (between sessions / restarts)

1. **Read** `docs/roadmap/current-phase.md` — confirms FT plan is active
2. **Read** `Assets/build/flythrough/.state.json` — current step
3. **Read** the latest handoff in `docs/handoffs/` matching `*ft{phase}-*`
4. **Run** the **Pre-flight** checks for the current step (listed in the step's table)
5. **Execute** per **Prompt template** and **Expected output**
6. **Validate** per **Acceptance**
7. **Update** `.state.json` (new current_step, last_handoff)
8. **Commit** with the convention `ft{N}.{M}: <short description>`
9. **Write** the next step's handoff (when phase exits)

If `.state.json` is missing or corrupt, treat all steps as `pending` and start with FT-1.1.

---

## 17. Post-plan refinements

- **Entry-point split** — the 41 read-only workflow commands (guards, reports, status checks, Ghidra summaries, NiDataStream evidence) moved from `scripts/rift_workflow.py` to a new peer entry point `scripts/rift_read_only.py` (see [2026-06-13 rift_read_only handoff](../handoffs/2026-06-13-rift-read-only-entry-point.md)). The bypass set on `rift_workflow.py` is now empty; the orphan-process guard fires for every command on that entry point. Spawner commands (the 33 that invoke `dotnet` / `RiftAssetDumper`, including all FT-1..FT-7 pipeline commands) remain on `rift_workflow.py`. Read-only commands invoked via `rift_workflow.py` print a deprecation notice to stderr pointing at `rift_read_only.py`.

## 18. Related documents

- `docs/roadmap/current-phase.md` — pointer to active phase
- `docs/roadmap/project-roadmap.md` — the **separate** Phase 0–49 plan (NIF parser/descriptor work, NOT consumer integration)
- `docs/50-step-plan-current-position.md` — original discovery cycle, complete
- `docs/asset-guided-runtime-reacquisition-strategy.md` — broader strategy context
- `docs/handoffs/` — session handoffs (one per FT phase completion)
- `docs/schemas/` — JSON schemas (existing + new ones for FT-3, FT-4, FT-7)
- `knowledge.md` — top-level project knowledge (one-line pointer to this plan)
- `C:/RIFT MODDING/RiftFlythrough/knowledge.md` — consumer-side project knowledge

---

*Last updated: 2026-06-08 (agentic rewrite — each step has agent, prompt template, acceptance, failure handling, resume marker)*
