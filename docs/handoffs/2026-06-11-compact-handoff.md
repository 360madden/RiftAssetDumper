# Compact Handoff — 2026-06-11

**Date:** 2026-06-11  |  **Previous:** 2026-06-10 comprehensive handoff

---

## CI: ✅ All Green

| Check | Result |
|-------|:------:|
| `dotnet build` | 0 errors ✅ |
| `dotnet test` | 6/6 pass ✅ |
| `ruff check scripts/` | 0 violations ✅ |
| `mypy scripts/` | 0 errors ✅ |
| Python tests | all pass ✅ |

## OBJ Export: 94 OBJs, 65 Faced

- **10,795 faces, 6,079 vertices** across **18+ families**
- **0 structural issues**, **0 unexported candidates** remain
- `batch_sweep.py` validates SHA256, index bounds, NaN, negative indices

## Proof Guards: All 4 ✅ PASSED

| Guard | Validates |
|-------|-----------|
| `attribute_extra_proof_guard` | @264 groups intact, raw-zero-based 5/5 |
| `usage_access_correlation_guard` | 5 roles, 0 pairing exceptions |
| `position_source_sibling_lead_guard` | Guarded leads intact |
| `residual_lead_guard` | 119 residuals, 5 @188 candidates |

## Key Discoveries

- **1,949 PairCompatibleMeshes** (restored Stage 9)
- **Stream roles:** uv-float2 (4,633), normal-float3 (4,167), index-u16be-strip (2,101), position-float3 (210)
- **@264 indexed family:** 5 meshes, raw-zero-based, degenerate-bridge stitch
- **5 shared-source sibling groups** (meshSize=329 strongest: 23 groups)
- **Half-float stream@188:** Dead end — interleaved control bytes, 94.6% plausible but below 0.95 threshold

## Live Archive Expansion (June 9-10)

| Metric | Source | Live |
|--------|:-----:|:----:|
| Archives | 27 | **244 (9×)** |
| New mesh sizes | 16 | **19+** (341, 357, 362) |
| meshSize=362 | — | ✅ Confirmed viable (`cf54e712ff57eaac` block 6) |
| Entries (est.) | 40K | ~2.4M |

## Uncommitted Changes

```text
knowledge.md:             57 insertions (tools registry, agent model strategy)
scripts/rift_workflow_utils.py:  118 insertions (load_tools_config, show_tools_status)
.gitignore:                7 insertions
New files:                .agents/, .tools.json, scripts/ghidra_runner.py
```

## Agent Definitions (`.agents/`)

10 agents with tiered model strategy — `cs-architect-gpt` (GPT-5.5) for complex C#, `investigator-gpt` (GPT-5.1) for stream analysis.

## Top Blockers

| # | Blocker | Priority |
|---|---------|:--------:|
| 1 | Full live inventory scan timeout (244 archives) | 🟡 Medium |
| 2 | New mesh sizes 341, 357 unprobed | 🟢 High |
| 3 | meshSize=362 not yet exported to OBJ | 🟢 High |

## Next Steps (Priority Order)

1. **Decode meshSize=362** from live root: `python scripts/rift_workflow.py decode-geometry --root "C:/Program Files (x86)/Glyph/Games/RIFT/Live" --id cf54e712ff57eaac --mesh-block 6 --experimental-position-source --write-obj`
2. **Probe meshSize=341 & 357** from live root
3. **Scale live scanning** with `--max-total 500`
4. **Run discovery suite** against live root

## Quickstart Commands

```bash
dotnet build RiftAssetDumper.slnx --nologo
ruff check scripts/
mypy scripts/ --no-error-summary
python scripts/test_rift_workflow_utils.py
python scripts/rift_workflow.py discovery-suite --quick --skip-build
```

---
*Created from re-established context on 2026-06-11*
