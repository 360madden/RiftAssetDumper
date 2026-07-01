# Next Operating Roadmap — Safety, Signal, and Consumer-Useful Evidence

**Created**: 2026-06-30
**Scope**: `C:\RIFT MODDING\Assets` next-cycle operating plan
**Status**: Proposed roadmap; intended to guide the next 1-3 focused cycles
**Relationship to existing roadmaps**: This is a coordination roadmap. It does
not replace `semantic-discovery-roadmap.md`, `binary-signature-roadmap.md`,
or `navmesh-navigation-roadmap.md`.

---

## North star

Maximize the chance of producing durable, consumer-usable evidence while keeping
the repo safe, reviewable, and fast to iterate.

The best next path is:

1. remove process risk first,
2. convert or retire ambiguous WIP,
3. validate the binary-signature lane with the smallest real proof,
4. advance semantic discovery in parallel only when it does not distract from
   the binary proof,

5. ship small PR-backed slices with strong local validation.

---

## Current baseline

| Area | Current state |
|---|---|
| Branch | `main` |
| Local/remote | synced with `origin/main` |
| Tracked tree | clean |
| Known untracked WIP | `scripts/modrm_scanner.py`, `scripts/signature_match.py`, `tests/test_modrm_scanner.py`, `tests/test_signature_match.py` |
| CI | latest push CI green |
| Branch protection | not enabled yet |
| PR workflow | proven once via PR #2 |
| Completed lanes | NIF geometry, Cycle 2 visual-fidelity manifest/delivery, Cycle 5.3.2 follow-up |
| Active evidence lanes | semantic discovery Phase 0, binary signature discovery validation/signature extraction |
| Proposed evidence lanes | navmesh navigation (generative pathfinding from NIF geometry; see `navmesh-navigation-roadmap.md`) |

---

## Operating principles

| Principle | Practical rule |
|---|---|
| Safety first | No broad staging; no `Source/`, `Extracted/`, or generated `Exports/` payloads without explicit intent. |
| Evidence over confidence | Treat self-reported phase exits as leads until revalidated in the current session. |
| Small shippable slices | Prefer 1 focused PR per proof increment. |
| Not too restrictive | Keep parallel lanes possible, but do not let parallelism create conflicting truth claims. |
| Consumer usefulness | Every durable artifact should say who consumes it and what decision it enables. |
| Reviewable by default | Use Option-B branch + PR for substantive work; direct push only for explicitly handoff-marked trivial follow-ups. |
| Python-first automation | New scripts/tools should be Python unless a Ghidra Java script is directly required. |

---

## Recommended phase roadmap

### Phase A — Repo safety and ambiguity closure

**Objective**: Make future work safe to land and remove ambiguous local state.

| Step | Action | Exit criteria |
|---:|---|---|
| A1 | Enable `main` branch protection per GH Issue #1 | Required checks selected; direct non-admin pushes blocked; PR all-green path still works |
| A2 | Decide fate of 4 untracked scanner files | Either committed as a named cycle or removed deliberately |
| A3 | Patch small handoff archaeology ticks if still relevant | Latest handoffs no longer contradict current git truth |
| A4 | Record a short baseline | `git status`, latest CI, and chosen next lane documented |

**Notes**:

- A1 is highest leverage if repo admin access is available.
- A2 is highest leverage if admin work is not available.
- A2 should not be a broad clean. Touch only the four known WIP files unless a
  fresh status shows more.

---

### Phase B — WIP scanner triage

**Objective**: Convert the abandoned scanner files into either a useful bounded
tool or a clean deletion.

| Step | Action | Exit criteria |
|---:|---|---|
| B1 | Read the four WIP scanner/test files | Classify as useful, obsolete, duplicate, or unsafe |
| B2 | Run focused tests for those files only | Know whether they pass as-is |
| B3 | Compare overlap with existing Ghidra tooling | Avoid duplicating `FunctionSiteSurvey`, `ScalarOffsetSearcher`, or `DisasmContext` |
| B4 | Decide ship vs retire | Commit/PR if useful; remove if not |

**Decision rule**:

- **Ship** if the scanner can produce a bounded, validated, non-promotional
  signal that supports `binary-signature-roadmap.md`.

- **Retire** if it duplicates stronger Ghidra tooling, depends on stale manual
  assumptions, or cannot be validated without overfitting.

---

### Phase C — Binary signature proof lane

**Objective**: Produce the first stable, externally validated binary-signature
artifact that can eventually help RiftReader avoid brittle hardcoded offsets.

| Step | Action | Exit criteria |
|---:|---|---|
| C1 | Revalidate current Ghidra/static-analysis baseline | Current binary path, Ghidra tooling, and target assumptions confirmed |
| C2 | Pick exactly one Tier-1 anchor | One anchor chosen with why-it-matters and consumer path |
| C3 | Extract candidate signature(s) with wildcard policy | Candidate includes byte pattern, mask, function context, and volatility notes |
| C4 | Verify uniqueness against full binary | One signature is unique or fallback is documented |
| C5 | Write proof packet + tests | JSON/schema/test coverage prevents silent regression |
| C6 | PR the slice | CI green; docs explain candidate vs durable truth |

**Recommended first anchor**: the most stable already-observed vtable dispatch
or thunk/property-access pattern, not a runtime data address.

**Hard line**: do not promote a runtime address as a static anchor. The value
is a lead only until code-access evidence supports it.

---

### Phase D — Semantic discovery proof lane

**Objective**: Produce compact semantic vocabularies that improve asset-guided
runtime reacquisition and consumer context.

| Step | Action | Exit criteria |
|---:|---|---|
| D1 | Re-run Phase 0 live-archive semantic smoke | Current command works against live archive path |
| D2 | Establish type/category distribution | Counts known for XML/text/Lua/audio candidates |
| D3 | Pick first vocabulary lane | Prefer `hint:map-zone` because it directly supports zone/runtime context |
| D4 | Generate small vocabulary proof | Compact JSON artifact + schema/validation |
| D5 | Rank next semantic lanes | POI, actor/object, UI strings, audio after zone proof |

**Parallelism policy**: D can run in parallel with C only when both lanes have
separate output paths, separate handoffs, and no shared truth promotion.

---

### Phase E — Consumer contract integration

**Objective**: Turn evidence into something downstream repos can safely use.

| Step | Action | Exit criteria |
|---:|---|---|
| E1 | Define consumer contract per artifact | Who uses it: RiftReader, RiftFlythrough, or human review |
| E2 | Add schema or manifest guard | Consumers can validate shape before trusting content |
| E3 | Add provenance and freshness fields | Consumers can distinguish current proof from historical captures |
| E4 | Create handoff with failure modes | Next agent knows what not to overclaim |

---

## Suggested first 10-day roadmap

| Day band | Focus | Deliverable |
|---|---|---|
| 0-1 | Phase A | Branch protection enabled or documented blocked; WIP scanner decision started |
| 1-2 | Phase B | Scanner files either retired or converted into a named, tested WIP branch |
| 2-4 | Phase C start | One binary anchor selected and revalidated |
| 4-6 | Phase C proof | Candidate signature + uniqueness check + proof packet |
| 6-7 | Phase C ship | PR with tests/docs; no generated payloads staged |
| 7-9 | Phase D start | Semantic Phase 0 smoke + type distribution |
| 9-10 | Phase D proof | First compact zone vocabulary proof, if Phase C is already stable |

This timeline is intentionally flexible. If branch protection requires manual
repo-admin work, do not block all evidence work on it; document the blocker and
continue with WIP scanner triage or a local binary proof branch.

---

## Validation matrix

| Work type | Minimum validation |
|---|---|
| Docs-only roadmap/handoff | markdown lint or at least `git diff --check` |
| Python tool | focused pytest + ruff + mypy where practical |
| Ghidra Java static tool | text/static tests + Java brace/import sanity; headless run when available |
| Schema/JSON artifact | schema meta-validation + sample instance validation |
| Binary signature claim | full-binary uniqueness check + wildcard rationale |
| Semantic vocabulary | smoke count + schema validation + provenance summary |
| PR | relevant local validation + CI green before merge |

---

## Success metrics

| Metric | Target |
|---|---:|
| Ambiguous WIP files | 0 unclassified files |
| Substantive direct pushes | 0 unless documented handoff-marked exception |
| Binary proof | 1 unique signature with proof packet |
| Semantic proof | 1 compact vocabulary artifact with validation |
| Generated game payload staged accidentally | 0 |
| Handoffs with stale/current contradiction | trending to 0 |

---

## Non-goals

- Do not reopen Cycle 2 visual-fidelity work without fresh consumer failure
  evidence.

- Do not add new broad C# parse behavior unless fixing a narrow crash or
  exposing a bounded evidence field.

- Do not chase all semantic lanes before one lane is proven end-to-end.
- Do not turn the WIP scanner files into durable truth just because they exist.
- The navmesh navigation roadmap (`navmesh-navigation-roadmap.md`) is a
  proposed third parallel lane. It depends on artifacts from both semantic
  discovery (zone attribution, walkability hints) and binary signature (live
  position reads). Phase 0 of navmesh should NOT start until the Phase A/B
  safety/closure work is complete.

---

## Immediate recommended next action

If repo admin access is available, enable branch protection from GH Issue #1.
If not, start Phase B and classify the four untracked scanner files.

Either path should end with a short handoff and a clean, intentional working
tree state.
