# Binary Signature Phase 2 Exit Handoff

- **Date:** 2026-07-07
- **Roadmap:** `docs/roadmap/binary-signature-roadmap.md` — Phase 2
- **Sessions:** 4 sessions (~1 hour each)
- **Commits:** 3 shipped to `origin/main`

---

## 1. Headline State

Binary-signature catalog is **synthesized and shipped**: 9 anchors (7 unique + 2 NOT_FOUND), schema-validated against `binary-signatures-v1.schema.json`, cross-validated against live `rift_x64.exe`, and documented with a consumer contract for RiftReader integration.

| Metric | Value |
|---|---|
| Total anchors | 9 |
| Unique (verified exactly 1 match in `.text`) | 7 |
| NOT_FOUND (0 matches) | 2 |
| Tier-1 (engine core, zero wildcards) | 1 (vtable-dispatch) |
| Tier-2 (game logic) | 8 |
| Schema validation | PASS (jsonschema 4.23.0, Draft 2020-12) |
| Cross-validation | 7/7 PASS_MATCH |
| Consumer contract | `docs/binary-signature-consumer-contract.md` |
| Catalog artifact | `Exports/binary-phase2/rift-x64-signature-catalog.json` (gitignored) |
| Tests | 13 new (schema conformance + anchor structure + summary consistency) |

---

## 2. What Was Built

### Session 1 — Pipeline Smoke Test (`dbceb18`)

- Ran `signature_match.py` against live `rift_x64.exe` (60MB, 39MB `.text`)
- 7/9 signatures produced exactly 1 match; 2 (#7, #8) produced 0 matches
- Ran `synthesize_signature_catalog.py --validate` — schema PASS
- Marked #7 and #8 as NOT_FOUND with specific fallback explanations
- Fixed: `FallbackStrategy` now prefers candidate's own `fallback` field

### Session 2 — Consumer Contract & Schema Lockdown (`6972686`)

- **NEW**: `docs/binary-signature-consumer-contract.md` (157 lines)
  - How to use anchors: pattern-scan → resolve pointer → apply struct layout
  - Stability tiers, wildcard policy, broken-signature recovery procedure
  - Safety boundaries: CandidateOnly, no decompiled code, read-only
- Upgraded `--validate` from lightweight checks to `jsonschema.validate()` (with ImportError fallback)
- **NEW**: `tests/test_synthesize_signature_catalog.py` (13 tests)
  - Schema conformance via `jsonschema.validate()`
  - Anchor structure validation (required fields, tier ranges, sig hex format)
  - Summary consistency (counts match array lengths)
- Schema fix: `Name` pattern relaxed to allow `#`, spaces, parens for cluster names
- Schema fix: `ClusterVA`/`EntryVA` only emitted when non-empty

### Session 3 — Cross-Validation (`81709c8`)

- **NEW**: `scripts/cross_validate_signatures.py` (258 lines)
  - Compares Ghidra-reported `entry_va` vs actual match RVA from `signature_match.py`
  - Computes RVA deltas for all 9 anchors
  - Produces JSON + markdown report
- All 7 unique signatures confirmed at expected locations with consistent RVA deltas
- Tree was already clean — no untracked WIP files to remove
- Ruff-formatted before commit

### Session 4 — This Handoff (current)

- Handoff document written
- `knowledge.md` updated with binary-signature lane status
- Full CI sweep: ruff ✅, mypy ✅, dotnet build ✅, dotnet test 56/56 ✅, pytest 935/942 (7 pre-existing failures unrelated)

---

## 3. Artifacts Produced

### Committed (tracked)

| File | Lines | Purpose |
|---|---|---|
| `scripts/synthesize_signature_catalog.py` | 294 | Synthesizes the binary-signature catalog from Phase 1 + Phase 2 inputs; validates against schema |
| `scripts/signature_match.py` | 300 | Validates byte signatures against `.text` section; reports uniqueness |
| `scripts/cross_validate_signatures.py` | 258 | Compares expected entry VAs to actual match RVAs; RVA delta report |
| `docs/schemas/binary-signatures-v1.schema.json` | ~220 | JSON Schema 2020-12 for the catalog |
| `docs/binary-signature-consumer-contract.md` | 157 | Consumer-facing doc for RiftReader integration |
| `tests/test_synthesize_signature_catalog.py` | 130 | 13 tests: schema conformance, anchor structure, summary consistency |
| `tests/test_signature_match.py` | 182 | Signature match unit tests |
| `tests/test_modrm_scanner.py` | 266 | ModRM scanner unit tests |
| `tests/test_probe_modrm_leads.py` | 318 | ModRM probe leads unit tests |

### Gitignored (in `Exports/binary-phase2/`)

| File | Purpose |
|---|---|
| `signature-candidates.json` | 9 candidate signatures with wildcard counts and Ghidra VAs |
| `signature-match-report.{json,md}` | Uniqueness scan results against live binary |
| `rift-x64-signature-catalog.json` | Final synthesized catalog (9 anchors, schema-valid) |
| `cross-validation-report.{json,md}` | RVA delta report for all 9 anchors |

---

## 4. Signature Catalog Detail

### Tier-1 (engine core, maximally stable)

| Anchor | Sig Length | Wildcards | Status |
|---|---|---|---|
| `vtable-dispatch` | 15B | 0 | ✅ UNIQUE — pure opcode, zero addresses, survives any patch |

### Tier-2 (game logic, moderately stable)

| Anchor | Sig Length | Wildcards | Status |
|---|---|---|---|
| #1 (28h) | 28B | 4 | ✅ UNIQUE — ModRM disp32 wildcarded |
| #2 (17h) | 40B | 0 | ✅ UNIQUE — zero-wildcard function prologue |
| #3 (17h) | 40B | 4 | ✅ UNIQUE — ModRM disp32 wildcarded |
| #4 (15h) | 16B | 0 | ✅ UNIQUE — zero-wildcard |
| #5 (14h) | 16B | 0 | ✅ UNIQUE — zero-wildcard |
| #6 (13h) | 32B | 0 | ✅ UNIQUE — zero-wildcard |
| #7 (11h) | 16B | 1 | ❌ NOT_FOUND — RIP-relative fragment too fragile |
| #8 (9h) | 16B | 4 | ❌ NOT_FOUND — data-immediate prefix shifted |

### Fallback Strategies for NOT_FOUND signatures

- **#7**: "Signature produced 0 matches in .text — too fragile (RIP-relative 0xAB4A at end may have shifted). Re-extract from Ghidra with broader wildcarding."
- **#8**: "Signature produced 0 matches in .text — data-immediate prefix (10 03 00 00) + RIP-relative suffix may have shifted. Re-extract from Ghidra with broader wildcarding."

---

## 5. Remaining Phase 2 Work (deferred to post-exit)

| # | Item | Priority |
|---|---|---|
| 1 | Recover #7 and #8 via Ghidra re-extraction with broader wildcarding | Medium |
| 2 | Wire catalog into RiftReader (out of scope — cross-repo) | Low (RiftReader-side) |
| 3 | Add `--image-base` CLI arg to `cross_validate_signatures.py` for binary portability | Low |
| 4 | Build `scripts/compare_signature_databases.py` (Phase 6 automation) | Low (Phase 6) |

---

## 6. CI Sweep (End of Phase 2)

| Check | Result |
|---|---|
| ruff (`check scripts/`) | ✅ All checks passed |
| mypy (`scripts/ --no-error-summary`) | ✅ No errors |
| dotnet build (`RiftAssetDumper.slnx --nologo`) | ✅ 0 errors, 0 warnings |
| dotnet test (`RiftAssetDumper.slnx --nologo`) | ✅ 56/56 passed |
| pytest (`tests/ scripts/`) | 935/942 passed (7 pre-existing failures in `test_rift_read_only_no_spawn.py` — `probe-modrm-leads`, `scan-live-diff`, `scan-live-values` missing from `COMMAND_MAP`; unrelated to binary-sig work) |
| markdownlint (pre-commit) | ✅ Pass |

---

## 7. Resume Protocol

When resuming binary-signature work:

1. Verify: `git log --oneline -5` should show `81709c8`, `6972686`, `dbceb18`
2. Read: this handoff (`docs/handoffs/2026-07-07-binary-phase2-exit.md`)
3. Read: `docs/roadmap/binary-signature-roadmap.md` for Phase 3+ context
4. Key entry points:
   - `python scripts/signature_match.py` — re-scan binary for signature uniqueness
   - `python scripts/synthesize_signature_catalog.py --validate` — regenerate catalog
   - `python scripts/cross_validate_signatures.py` — cross-validate expected vs actual RVAs

---

*End of handoff. Phase 2 binary-signature catalog is complete and shipped. 7 unique, validated signatures ready for RiftReader integration.*
