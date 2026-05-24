# AI-driven workflow

This repo uses a Codex-first autonomous milestone loop for safe asset-discovery work.

## Default loop

1. Read `AGENTS.md`, `knowledge.md`, `docs/current-status.md`, and the newest handoff before changing direction.
2. Choose one bounded milestone with a concrete success condition.
3. Prefer durable repo workflow commands over one-off scripts.
4. Make the smallest coherent code/doc change needed for the milestone.
5. Run validation and generated-output safety checks.
6. Commit and push the coherent milestone after gates pass.
7. Write or update a handoff only when the milestone changes durable repo truth or resume context.

## Commit and push gate

Before staging, verify:

```powershell
git status --short
git diff --name-only
git diff --check
python scripts/rift_workflow.py generated-output-guard
```

For Python workflow changes, also run:

```powershell
python -m py_compile scripts/rift_workflow.py scripts/rift_workflow_utils.py scripts/ghidra_runner.py scripts/test_rift_workflow_utils.py
python scripts/test_rift_workflow_utils.py
ruff check scripts/
mypy scripts/ --no-error-summary
```

For tool-registry or Ghidra workflow changes, also run:

```powershell
python scripts/rift_workflow.py tools-status
python scripts/rift_workflow.py ghidra-dry-run
python scripts/test_ghidra_runner.py
```

Stage only the intended tracked files. Do not use broad staging such as `git add .` in this repo.

## Safety boundaries

Never stage or commit:

- `Source/`
- `Extracted/`
- `Exports/`
- `bin/`, `obj/`, `__pycache__/`, `*.pyc`
- `.env`
- local assistant/tool histories, logs, or provider config

Keep local Windows user-profile paths and account-like usernames out of tracked docs and chat summaries unless explicitly requested.

Use high/extra-high reasoning for asset truth, parser truth, proof guards, schemas, runtime/live-game work, Ghidra interpretation, exporter gates, commit review, and push decisions.

## Tool roles

### Codex

Codex is the primary driver for multi-step work:

- use `/goal` for multi-step milestones;
- keep each goal bounded and testable;
- continue autonomously through safe follow-up milestones when the lane is open;
- validate before every commit/push.

### Repo workflow commands

`scripts/rift_workflow.py` is the durable Python workflow surface. Add new recurring capabilities there before creating one-off helpers, unless the new helper needs a genuinely separate runtime surface.

### Ghidra

Ghidra is an explicit offline static-analysis support tool, not part of the default discovery suite.

Use it first for target-bound questions such as TWAD, NIF, or `NiDataStream` parser anchors. Keep generated projects under ignored `Exports/ghidra-projects/`. Treat findings as hypotheses until parser output and proof guards validate them.

Use the repo workflow surface first:

```powershell
python scripts/rift_workflow.py tools-status
python scripts/rift_workflow.py ghidra-dry-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project
python scripts/rift_workflow.py ghidra-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project --ghidra-timeout 900 --ghidra-script scripts/ghidra/FunctionSiteSurvey.java --ghidra-script-arg 0x1406e905f --ghidra-script-arg Exports/ghidra-reports/twad_site_survey.json
python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/twad_site_survey.json --ghidra-summary-term TWAD
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 10
python scripts/rift_workflow.py ghidra-pairing-non-export-guard
python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
python scripts/rift_workflow.py ghidra-attribute-candidate-report
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
```

Use `--ghidra-timeout 14400` for a first-pass full import/auto-analysis of `rift_x64.exe`; use shorter script-only reruns against a retained project when possible. Call `scripts/ghidra_runner.py` directly only when debugging the lower-level wrapper itself.

Prefer Java Ghidra scripts in this lane. Ghidra 12.1 headless did not run `.py` scripts in the validated `rift_x64.exe` launch mode; treat Python/Jython Ghidra scripts as unproven until a future validation shows otherwise.

Run retained-project Ghidra jobs serially. Parallel `ghidra-run` calls against the same project can fail on the Ghidra project lock.

For `FunctionSiteSurvey.java` reports, use `ghidra-summarize` to produce a small Markdown review. The generated JSON schema is documented at `docs/schemas/ghidra-function-site-survey-v1.schema.json`; raw reports and optional summaries should stay under ignored `Exports/ghidra-reports/`.

For `NiDataStream::LoadBinary()` follow-up, use `nidatastream-layout` before changing decoder behavior. It validates the candidate prefix/payload/trailing-flag layout across copied/extracted NIF samples and writes ignored report files under `Exports/`.

For Ghidra pairing follow-up, use `ghidra-pairing-review-report` as the durable queue, `mesh-probe --review-rank N` for focused probes, `ghidra-attribute-candidate-report` for grouped sample-mesh triage, `ghidra-attribute-candidate-guard` for the current incomplete-group proof baseline, and `ghidra-pairing-non-export-guard` before any commit that touches Ghidra/mesh export boundaries. The report schemas are `docs/schemas/ghidra-pairing-review-v1.schema.json` and `docs/schemas/ghidra-attribute-candidate-v1.schema.json`; the promotion gate is `docs/ghidra-pairing-promotion-checklist.md`.

## Current Ghidra lane state

- Anchor survey complete: `docs/handoffs/2026-05-24-ghidra-anchor-survey.md`
- TWAD proof complete: `docs/handoffs/2026-05-24-twad-ghidra-proof.md`
- NiDataStream/NiMesh proof started: `docs/handoffs/2026-05-24-nidatastream-ghidra-proof.md`
- NiDataStream layout mismatch documented: `docs/handoffs/2026-05-24-nidatastream-layout-mismatch.md`
- NiDataStream C# layout sidecar comparison wired: `docs/handoffs/2026-05-24-nidatastream-layout-helper-migration.md`
- NiDataStream role-delta ranking wired: `docs/handoffs/2026-05-24-ghidra-role-delta-ranking.md`
- Candidate-only Ghidra pairing comparison wired: `docs/handoffs/2026-05-24-ghidra-pairing-comparison.md`
- Little-endian index stats for Ghidra pairings wired: `docs/handoffs/2026-05-24-ghidra-little-endian-index-stats.md`
- Legacy/Ghidra pairing overlap review wired: `docs/handoffs/2026-05-24-ghidra-pairing-overlap.md`
- Candidate-only Ghidra pairing review findings wired: `docs/handoffs/2026-05-24-ghidra-pairing-review.md`
- Workflow-level Ghidra pairing review report wired: `docs/handoffs/2026-05-24-ghidra-pairing-review-report.md`
- Focused mesh-probe Ghidra sidecar pairings wired: `docs/handoffs/2026-05-24-ghidra-mesh-probe-sidecar-pairings.md`
- Ghidra non-export guard, `mesh-probe --review-rank`, schema, and promotion checklist wired: `docs/handoffs/2026-05-24-ghidra-workflow-guard-review-rank-schema.md`
- Current Ghidra-only review groups probed 1-14, covering all 64 Ghidra-only pairings: `docs/handoffs/2026-05-24-ghidra-only-rank-1-14-probes.md`
- Focused Ghidra normal/UV probe review fields wired: `docs/handoffs/2026-05-24-ghidra-normal-uv-probe-reviews.md`
- Grouped Ghidra attribute candidate report wired: `docs/handoffs/2026-05-24-ghidra-attribute-candidate-report.md`
- Grouped Ghidra attribute candidate guard wired: `docs/handoffs/2026-05-24-ghidra-attribute-candidate-guard.md`
- Grouped Ghidra attribute candidate schema wired: `docs/handoffs/2026-05-24-ghidra-attribute-schema.md`
- Plan/status for that proof: `docs/plans/2026-05-24-twad-ghidra-proof-plan.md`
- `TWAD` is proven as archive file/header magic; `TWAM` remains manifest-layer magic.
- `NiDataStream::LoadBinary()` and mesh semantic-adapter validation have first-pass static proof; no parser behavior change is recommended yet.
- Parser/export behavior should remain unchanged until the sidecar Ghidra-aligned role/body fields, `TopGhidraRoleDeltas`, little-endian index stats, candidate-only `TopGhidraPairings`, pairing overlap/gap evidence, `TopGhidraPairingReviewFindings`, ignored `ghidra-pairing-review-report` outputs, focused `probe-nif-mesh` `GhidraPairings`, `mesh-probe --review-rank` evidence, and position/normal/UV review fields are reviewed and promoted through a small guarded decoder patch. `ghidra-pairing-non-export-guard` should keep failing closed on any premature export wiring.
- Next safe Ghidra target: either a tiny unsupported-TWAD-version warning/test review or the `NiDataStream` / `NiMesh` leads from the anchor survey.
