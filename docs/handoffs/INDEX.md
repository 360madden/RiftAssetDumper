# Handoff Doc Index

**Last Updated**: 2026-07-12
**Purpose**: Surfaces the most-important handoff documents per cycle so future AI
sessions resuming work on a specific cycle can quickly find context. Each cycle
has one primary handoff row (pointed at first), plus supporting handoffs if
applicable.

**Format**: Cycles are sorted descending by cycle number; within a cycle, handoffs
are sorted by ship/closure date descending. All paths are relative to
`docs/handoffs/`.

## Cycles

| # | Cycle | Topic | Status | Primary handoff | Supporting handoffs |
|---|---|---|---|---|---|
| **5** | (a) Tier-1 archive provenance | Disjoint `assets.N` split, `build_live_archive_index.py`, archive-derived lockdowns, audit-key correctness finding | SHIPPED 2026-06-21 | [`2026-06-21-cycle-five-tier1-archive-provenance.md`](2026-06-21-cycle-five-tier1-archive-provenance.md) | — |
| **5** | (b) Semantic-category surface | Scene manifest v0.9 optional `semantic`, delivery v0.3 flat `semantic_categories`, wire-format lock + migration safety | SHIPPED 2026-06-21 | [`2026-06-cycle-5-semantic-surface.md`](2026-06-cycle-5-semantic-surface.md) | — |
| **6** | NM-6 scale-out and multi-zone routing | M6.1-M6.4 complete: protected/provenanced full index, 4 built zones, actual-navmesh 2-edge graph, Detour-projected cross-zone segments, explicit disconnected-pair handling, and debug OBJ export. | COMPLETE 2026-07-12 | [`2026-07-12-nm-6-phase6-completion.md`](2026-07-12-nm-6-phase6-completion.md) | [`2026-07-12-nm-6-m6.1-batch-navmesh.md`](2026-07-12-nm-6-m6.1-batch-navmesh.md), [`2026-07-12-nm-6-m6.1-batch-navmesh-compact.md`](2026-07-12-nm-6-m6.1-batch-navmesh-compact.md) |
| **4** | Mesh297 + mesh321 leader discovery | 27 OBJs from 2 untapped families, 9/9 guards PASS, frontier exhausted | CLOSED 2026-06-18 | [`2026-06-18-discovery-cycle-3.md`](2026-06-18-discovery-cycle-3.md) | [`2026-06-18-mesh297-discovery.md`](2026-06-18-mesh297-discovery.md), [`2026-06-21-cycle-4-lod-closure.md`](2026-06-21-cycle-4-lod-closure.md) |
| **2** | Consumer visual fidelity (scene manifests) | 241 stage6 + stage2 manifests, v0.7→v0.8 NIF-confirmed material scan, 9th guard, ship-kill | SHIPPED 2026-06-16 | [`2026-06-16-cycle-2-phase-7-exit.md`](2026-06-16-cycle-2-phase-7-exit.md) | 12+ supporting handoffs in `2026-06-15..16-cycle-2-*` and `2026-06-16-c2-*` |

## How to find more

- **Cycle 2**: List files matching `2026-06-15..16-cycle-2-*` and `2026-06-16-c2-*.md`. Phase-exit handoffs cover C2-1 through C2-7.
- **Cycle 4**: Includes per-asset mesh297 breakdown and LOD closure.
- **Cycle 5 (a)**: Tier-1 archive provenance — anchored by `2026-06-21-cycle-five-tier1-archive-provenance.md`. Quickstart entry points surfaced in `knowledge.md` (`build_live_archive_index.py`, `synthesize_semantic_matrices.py --archive-index --validate`, etc.).
- **Cycle 5 (b)**: Semantic-category surface — `scripts/semantic_surface.py` loader, `$defs/Semantic` schema additions, 12 wire-format lock tests in `tests/test_semantic_surface.py`.
- **Cycle 6 (NM-6)**: M6.1 implementation plus post-ship hardening truth —
  full handoff `2026-07-12-nm-6-m6.1-batch-navmesh.md`; compact TL;DR
  companion `2026-07-12-nm-6-m6.1-batch-navmesh-compact.md`.

## Pre-cycle history

Earlier handoffs (Phase 1 M1.1–M1.5 milestones, Ghidra proof lane, FT-1..FT-8
flythrough bridge, sibling pairing phases 16–24, position-source family proof)
are not indexed here. They live in:

- `docs/handoffs/2026-06-m1.*-*.md` — Phase 1 milestones
- `docs/handoffs/2026-05-2*.md` — Ghidra + flythrough bridge
- `docs/handoffs/2026-05-26-final-50-step-session.md` — 50-step plan end
