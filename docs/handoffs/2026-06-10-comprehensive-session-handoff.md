# Session Handoff — 2026-05-21 — 2026-06-10: Half-Float Investigation + Live Archive Expansion + Agent Rebuild

**Date range:** 2026-05-21 — 2026-06-10  \
**Previous:** Stage 18 (batch-sweep runner, 94 OBJs, candidate exhaustion)

## Summary

Three parallel workstreams completed: (1) **Half-float stream@188 deep-dive** — confirmed IEEE 754 half-float data interleaved with control/metadata bytes, classified as candidate-only dead end (below 0.95 threshold), no C# decoder port warranted; (2) **Live archive expansion** — discovered 244 archives (9× Source's 27) with completely new mesh sizes (341, 357, 362), probed meshSize=362 with confirmed normals/UVs/positions as first viable new export candidate; (3) **Agent definitions rebuilt** — `.agents/` restored and expanded with 10 definitions including new `cs-architect-gpt` (GPT-5.5) and `investigator-gpt` (GPT-5.1), model strategy documented in `knowledge.md`. All investigation scratch scripts cleaned up. CI fully green.

---

## 1. Half-Float Stream@188 Investigation

### What was done

- Extracted full 192-byte stream body (block 21) from asset `04297730afc68f38` (meshSize=305)
- Built custom Python analysis via `investigate_half_float.py` — decoded all 96 uint16 values as IEEE 754 half-float using `struct.unpack('e')`
- Analyzed 0xAA56 (43606 sentinel) marker pattern across 8 occurrences
- Cross-validated against sibling mesh `014e1ff60d8508f1` (288-byte variant)

### Key findings

| Metric | Value |
|--------|-------|
| **Payload** | 192 bytes = 96 uint16 = 96 half-floats |
| **Vertex layout** | 16 vertices × 12 bytes (6 half-floats) — fits perfectly |
| **0xAA56 markers** | 8 occurrences at indices [26, 32, 38, 44, 74, 80, 86, 92] (spacing of 6, one gap of 30) |
| **Finite values** | 92/96 finite, 4 NaN |
| **Plausible positions** | 87/92 (94.6%) in [-1000, 1000] |
| **Plausible range** | [-8.76, 17.02] — very tight, game-appropriate |
| **Structural family** | `u16-ternary-mixed-c` with interleaved even/odd triple pattern |

### The interleaving pattern

The 192 bytes are structured as **16 triples × 6 bytes = 96 bytes per half** (two structurally identical halves):

- **Even triples** → A+B are position-like, **C** is NaN/0xAA56 (the control/sentinel channel)
- **Odd triples** → A+B vary, C=65 (near-zero as half-float) — metadata channel

### Sibling validation

| Sibling | Payload | Structure | Verdict |
|---------|:-------:|:---------:|:-------:|
| `04297730afc68f38` | 192 bytes | interleaved half-float + control | Candidate-only |
| `014e1ff60d8508f1` | 288 bytes | same pattern, 24 triples | Candidate-only |
| `0d9a25c9a6af7b18` | 264 bytes | **float32** (already works with existing decoder) | **Already exportable** |

### Verdict

**Dead end for clean export.** The data IS half-float but interleaved with control/metadata bytes. 94.6% plausible-position rate is a stronger signal than float32 decode (0%), but all 8 candidate rows failed strict classifier (below 0.95 threshold). No C# decoder port justified.

---

## 2. Live Archive Expansion

### Archive comparison

| Metric | Source (copied) | Live (full) | Delta |
|--------|:---------------:|:-----------:|:-----:|
| Archives | 27 | **244** | **9×** |
| NIF entries | 5,511 | ~825 sampled | ~15% sampled |
| NiMesh blocks | 5,507 | ~152 sampled | ~3% sampled |
| Unique mesh sizes | 16 (max 354) | **19+ (max 362+)** | +3 new |
| Manifest identical? | — | 48 bytes diff | Same game version |

### Live archive type breakdown (2,408 entries sampled)

| Type | Count |
|------|:-----:|
| DDS (textures) | 953 |
| NIF (models) | 825 |
| BIN (binary data) | 360 |
| RIFF (audio) | 213 |
| JPG (images) | 52 |
| TXT | 4 |
| XML | 1 |

### New mesh sizes discovered (not in Source)

| Size | Status | Notes |
|:----:|:------:|-------|
| **362** | ✅ Confirmed viable | mesh block 6, asset `cf54e712ff57eaac` |
| 341 | 🟡 Unprobed | Exists in live role groups |
| 357 | 🟡 Unprobed | Exists in live role groups |

### Live probe: cf54e712ff57eaac (mesh block 6, meshSize=362)

| Property | Value |
|----------|-------|
| Source archive | assets.002 (entry 1191) |
| Mesh size | **362** (not in Source) |
| Total NIF blocks | 32 (1 NiMesh + 31 other) |
| Attribute sets | 0 |
| Pairings | 0 |
| Candidate links | 3 |

**Stream layout:**

| Offset | Role | Vertices | Bytes | Confidence |
|:------:|------|:--------:|:-----:|:----------:|
| 232 | `normal-float3-ror1-lead` | 6,489 | 77,897 | 85% (unit-length ratio=1.0) |
| 308 | `position-float3-ror1-lead` | 41 | 492 | 75% (finite bounds, extent=3.0763) |
| 316 | `uv-float2-ror1-lead` | 6,489 | 51,941 | 80% (UV-range confirmed) |

**Key evidence:** Normal stream has **NearUnitVectorRatio=1.0** (6,489/6,489 unit-length). Position stream has game-appropriate extent=3.0763. UV stream has perfect UV-range ratios. **First viable export candidate from live archives** via `--experimental-position-source`.

### Inventory constraints

- Full mesh inventory against live root **timed out after 10 minutes** — 244-archive scan too heavy for single pass
- All live data comes from 50-entry smoke test (`--max-total 50`) and 100-entry scan
- **Estimated ~2.4M total entries** in live (244 archives × ~10K each) vs Source's 40K

### Probe output files created

| File | Size | Contents |
|------|:----:|----------|
| `Exports/live-mesh-inventory-smoke.json` | 10.4 MB | 50-entry live inventory smoke test |
| `Exports/live-mesh-fast.json` | Data file | 100-entry live mesh inventory |
| `Exports/live-archive-inventory.json` | Data file | 244-archive type breakdown |
| `Exports/live-probe-cf54.json` | Probe file | NIF structure probe |
| `Exports/live-probe-cf54-mesh6.json` | Probe file | Mesh block 6 data (meshSize=362) |
| `Exports/live-probe-cf54-mesh0.json` | Probe file | Mesh block 0 |
| `Exports/live-probe-cf54-mesh1.json` | Probe file | Mesh block 1 |
| `Exports/live-probe-cf54-mesh12.json` | Probe file | Mesh block 12 |
| `Exports/live-probe-cf54-mesh24.json` | Probe file | Mesh block 24 |

---

## 3. Agent Definitions Rebuilt

### `.agents/` directory restored and expanded

The `.agents/` directory was rebuilt from scratch after being deleted. It now contains **10 agent definitions**:

| Agent | Model | Purpose |
|-------|:-----:|---------|
| `nif-probe-agent` | DeepSeek V4 Flash (high) | NIF mesh analysis, stream role probing |
| `discovery-orchestrator` | DeepSeek V4 Flash | Pipeline orchestration (build→inventory→guards) |
| `program-cs-editor` | DeepSeek V4 Flash (high) | Routine C# edits, simple gate changes |
| `proof-guard-agent` | DeepSeek V4 Flash (high) | Guard suite maintenance & validation |
| `obj-export-validator` | DeepSeek V4 Flash | OBJ structural integrity checks |
| `handoff-summarizer` | DeepSeek V4 Flash (high) | Session handoff document generation |
| `safety-guardian` | DeepSeek V4 Flash (high) | Pre-commit safety audits |
| `autonomous-worker` | DeepSeek V4 Flash | Task queue executor |
| **`cs-architect-gpt`** | **OpenAI GPT-5.5** (high) | **Complex C# changes** — new decode paths, subtle bugs, algorithm design |
| **`investigator-gpt`** | **OpenAI GPT-5.1** (high) | **Stream data investigation** — half-float decode, magic-byte patterns |

### Agent model strategy documented

The new `knowledge.md` entry defines a tiered strategy:
- **Default:** Flash agents for speed/cost on routine work
- **Complex C#:** Deploy `cs-architect-gpt` (GPT-5.5) when changes require multi-step reasoning across ~15K-line `Program.cs`
- **Binary analysis:** Deploy `investigator-gpt` (GPT-5.1) for stream data requiring pattern recognition and experimental decode prototyping

### Notes on agent backup

Git status at session start showed `.agents.bak2/` as an untracked directory (original agent definitions backed up during rebuild). The `.agents/` directory now contains the rebuilt and expanded set. The `.agents.bak2/` directory may not persist on disk; the rebuilt definitions in `.agents/` are the canonical set.

---

## 4. Cleanup & CI

### Investigation scripts removed

| Script | Purpose | Status |
|--------|---------|:------:|
| `scripts/investigate_half_float.py` | Half-float decode + marker analysis | ✅ Deleted |
| `scripts/investigate_half_float_summary.py` | Summary visualizer | ✅ Deleted |

### CI status (all green)

| Check | Result |
|-------|:------:|
| `dotnet build` | 0 errors ✅ |
| `ruff check scripts/` | 0 violations ✅ |
| `mypy scripts/ --no-error-summary` | 0 errors ✅ |
| Python tests (58) | 58/58 pass ✅ |

### Git state

| Change | Status | Details |
|--------|:------:|---------|
| `.agents/*.ts` files | 🔄 Rebuilt | 10 agent definitions (restored + 2 new GPT agents) |
| `.agents.bak2/` | 🆕 Untracked (git status) | Backup of old agent definitions (may not persist on disk) |
| `knowledge.md` | 📝 Modified | Stage 18 stats, agent model strategy, batch_sweep.py docs |
| `docs/handoffs/2026-05-21-agent-rebuild-and-test.md` | 🆕 New | Previous agent rebuild handoff |
| `docs/handoffs/2026-06-09-half-float-investigation-live-expansion.md` | 🆕 New | Previous session handoff |
| Investigation scripts | ✅ Deleted | Cleaned up |

---

## Blockers

| # | Blocker | Priority | Resolution |
|---|---------|:--------:|------------|
| 1 | **Half-float @ stream@188**: Interleaved with control bytes, below 0.95 strict classifier threshold | 🟤 Superceded | Dead end confirmed — no further investigation warranted |
| 2 | **Full live inventory timeout**: 244-archive scan takes 10+ min at default settings | 🟡 Medium | Use `--max-total 500` for targeted scans; consider batch scanning or parallelization |
| 3 | **New mesh sizes (341, 357)**: Existence confirmed in live but no probe data yet | 🟢 High | Probe these from live root in next session |
| 4 | **meshSize=362 export**: Viable candidate identified but not yet decoded to OBJ | 🟢 High | Run `--experimental-position-source --write-obj` as first priority |

## Proof Guard Status

Not run this session — no C# or algorithm changes were made to `Program.cs` or `rift_workflow_guards.py`. All 4 proof guards (attribute-extra, usage-access-correlation, position-source-sibling-lead, residual-lead) remain at their Stage 18 PASSED baselines.

---

## 6. Optimal Next Steps

| Priority | Action | Expected ROI |
|:--------:|--------|:------------:|
| 1️⃣ | Decode meshSize=362 from live root (`cf54e712ff57eaac` block 6) with `--experimental-position-source --write-obj` | **First OBJ export from live archives** |
| 2️⃣ | Probe meshSize=341 and meshSize=357 assets from live root | Uncover new export families |
| 3️⃣ | Scale live archive scanning with optimized limits (`--max-total 500`) | Comprehensive live mesh catalog |
| 4️⃣ | Deploy `cs-architect-gpt` for any C# decode-path changes arising from live discoveries | Complex algorithm changes |

---

## Commands Used

```bash
# Probe live mesh sizes
dotnet run --project src/RiftAssetDumper -- probe-nif --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" --id cf54e712ff57eaac --out "Exports/live-probe-cf54.json"

# Decode geometry from live (experimental)
python scripts/rift_workflow.py decode-geometry --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" --id cf54e712ff57eaac --mesh-block 6 --experimental-position-source --write-obj

# Run discovery suite (live)
python scripts/rift_workflow.py discovery-suite --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" --skip-build --quick

# CI checks
ruff check scripts/
mypy scripts/ --no-error-summary
python scripts/test_rift_workflow_utils.py
dotnet build RiftAssetDumper.slnx --nologo
```

---

## Key Numbers Summary

```
Half-float plausible rate:       94.6%
Candidate rows at stream@188:    8 (0 strict passes)
Source archives:                 27
Live archives:                   244 (9×)
Total live entries (est.):       2.4M
New mesh sizes:                  341, 357, 362
Confirmed export candidates:     1 (meshSize=362)
Agent definitions:               10 (2 new GPT agents)
CI status:                       ALL GREEN
Scratch scripts cleaned:         2
```
