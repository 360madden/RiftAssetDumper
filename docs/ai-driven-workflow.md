# AI-driven workflow

This repo uses a Codex-first autonomous milestone loop for safe asset-discovery work.

Canonical stage label: the historical geometry/export pipeline is **Stage 18 complete**. Current active work is the **post-Stage-18 Ghidra/NiDataStream proof-guard lane**; do not renumber this as a new Stage 4. Treat dated stage tables in older status docs as historical unless refreshed by current git state, CI, and latest handoffs.

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
python -c "import pathlib, py_compile; [py_compile.compile(str(path), doraise=True) for path in pathlib.Path('scripts').glob('*.py')]"
Get-ChildItem scripts/test_*.py | Sort-Object Name | ForEach-Object { python $_.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
ruff check scripts/
mypy scripts/ --no-error-summary
```

For tool-registry or Ghidra workflow changes, also run:

```powershell
python scripts/rift_workflow.py tools-status
python scripts/rift_workflow.py ghidra-dry-run
python scripts/test_ghidra_runner.py
python scripts/test_rift_workflow_command_wiring.py
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

Use it first for target-bound questions such as TWAD, NIF, or `NiDataStream` parser anchors. Keep generated projects under ignored `Exports/ghidra-projects/`. Treat findings as hypotheses until parser output and proof guards validate them. For the current offline/static NiDataStream lane, start with `docs/ghidra-nidatastream-offline-quickstart.md`.

Use the repo workflow surface first:

```powershell
python scripts/rift_workflow.py tools-status
python scripts/rift_workflow.py ghidra-dry-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project
python scripts/rift_workflow.py ghidra-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project --ghidra-timeout 900 --ghidra-script scripts/ghidra/FunctionSiteSurvey.java --ghidra-script-arg 0x1406e905f --ghidra-script-arg Exports/ghidra-reports/twad_site_survey.json
python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/twad_site_survey.json --ghidra-summary-term TWAD
python scripts/rift_workflow.py ghidra-function-site-target-guard
python scripts/rift_workflow.py ghidra-function-site-survey --list-json
python scripts/rift_workflow.py ghidra-function-site-status --list-json
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-loadbinary
python scripts/rift_workflow.py nidatastream-evidence-status --list-json
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-promotion-dashboard
python scripts/rift_workflow.py nidatastream-promotion-preflight
python scripts/rift_workflow.py nidatastream-parser-field-proof-guard
python scripts/rift_workflow.py nidatastream-parser-export-non-consumption-guard
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 10
python scripts/rift_workflow.py ghidra-pairing-non-export-guard
python scripts/rift_workflow.py mesh-probe --review-rank 2 --skip-build
python scripts/rift_workflow.py ghidra-review-rank-probes --limit 14 --skip-build
python scripts/rift_workflow.py ghidra-review-rank-probes --review-kind vertex-semantic-change --limit 11 --skip-build
python scripts/rift_workflow.py ghidra-review-rank-probes-summary --review-kind all
python scripts/rift_workflow.py ghidra-attribute-candidate-report
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
python scripts/rift_workflow.py ghidra-workflow-guard-suite
```

Use `--ghidra-timeout 14400` for a first-pass full import/auto-analysis of `rift_x64.exe`; use shorter script-only reruns against a retained project when possible. Call `scripts/ghidra_runner.py` directly only when debugging the lower-level wrapper itself.

Prefer Java Ghidra scripts in this lane. Ghidra 12.1 headless did not run `.py` scripts in the validated `rift_x64.exe` launch mode; treat Python/Jython Ghidra scripts as unproven until a future validation shows otherwise.

Run retained-project Ghidra jobs serially. Parallel `ghidra-run` calls against the same project can fail on the Ghidra project lock.

For `FunctionSiteSurvey.java` reports, use `ghidra-function-site-target-guard` to validate that tracked targets remain candidate-only and write only repo-relative ignored `Exports/ghidra-reports/` files. Use `ghidra-function-site-survey --list-json` for an agent-readable target list, `ghidra-function-site-status --list-json` to inspect which ignored reports/summaries currently exist, and `ghidra-function-site-survey --ghidra-target <key>` with targets from `docs/ghidra-function-site-targets.json` to print serialized rerun/summarize commands; the target registry schema is `docs/schemas/ghidra-function-site-targets-v1.schema.json`, and the list/status schemas are `docs/schemas/ghidra-function-site-target-list-v1.schema.json` and `docs/schemas/ghidra-function-site-status-v1.schema.json`. `--list-json` mode still runs the generated-output guard but suppresses success banners so stdout is parseable JSON. Add `--ghidra-execute` only when intentionally running one target against the retained project. Use `ghidra-summarize` to produce a small Markdown review. The generated report JSON schema is documented at `docs/schemas/ghidra-function-site-survey-v1.schema.json`; raw reports and optional summaries should stay under ignored `Exports/ghidra-reports/`.

For `NiDataStream::LoadBinary()` follow-up, use `nidatastream-promotion-preflight` before considering decoder/export changes. The preflight writes the ignored dashboard, prints ignored local evidence artifact timestamps/status, runs the Ghidra/NiDataStream promotion guard suite, and reruns generated-output safety. For narrower checks, use `nidatastream-evidence-status --list-json`, `nidatastream-promotion-status --list-json`, `nidatastream-promotion-dashboard`, `nidatastream-descriptor-proof-status --list-json`, `nidatastream-descriptor-sample-compare`, `nidatastream-parser-export-non-consumption-guard`, and `nidatastream-parser-field-proof-guard`. The status command reports the post-Stage-18 parser/export promotion gates, and the dashboard writes compact ignored Markdown/JSON snapshots under `Exports/`. These include descriptor-helper evidence, ignored local `nidatastream-layout-report.json` sample-byte status, and ignored local `ghidra-attribute-candidate-report.json` pairing-impact status. The descriptor/sample compare command writes ignored JSON/Markdown that checks descriptor-helper readiness against uniform sample-byte counters, and its schema is `docs/schemas/nidatastream-descriptor-sample-compare-v1.schema.json`; it remains candidate-only and keeps parser/export promotion locked off. The proof guard fails closed on premature promotion while current descriptor/sample/pairing gates remain candidate-only or blocked, and the non-consumption guard verifies decode/export-sensitive C# consumers do not read candidate NiDataStream/Ghidra body-layout fields. Use `nidatastream-layout` before changing decoder behavior. It validates the candidate prefix/payload/trailing-flag layout across copied/extracted NIF samples and writes ignored report files under `Exports/`; the report schema is `docs/schemas/nidatastream-layout-report-v1.schema.json`.

Before any future parser/export patch, read `docs/nidatastream-promotion-readiness-checklist.md` and copy `docs/nidatastream-parser-export-promotion-decision-template.md` into a dated decision record or handoff. Before changing promotion-critical schemas, read `docs/nidatastream-ghidra-schema-policy.md`. The v1 schemas intentionally lock `ParserExportPromotionAllowed=false` and `FieldOrderPromoted=false`.

For Ghidra pairing follow-up, use `ghidra-pairing-review-report` as the durable queue, `mesh-probe --review-rank N` for a single focused probe, `ghidra-review-rank-probes` to batch-refresh ignored `Exports/ghidra-review-rank-probes/rankNN/` folders plus per-kind `manifest-*.json`/`.md`, `ghidra-review-rank-probes-summary` to roll those manifests up for quick review, `ghidra-attribute-candidate-report` for grouped sample-mesh triage, `ghidra-attribute-candidate-guard` for the current incomplete-group proof baseline, and `ghidra-workflow-guard-suite`/`ghidra-pairing-non-export-guard` before any commit that touches Ghidra/mesh export boundaries. `ghidra-workflow-guard-suite` now includes the FunctionSiteSurvey target-path guard and `nidatastream-parser-field-proof-guard` before running the grouped attribute candidate baseline. The report schemas are `docs/schemas/ghidra-pairing-review-v1.schema.json`, `docs/schemas/ghidra-review-rank-probes-manifest-v1.schema.json`, `docs/schemas/ghidra-review-rank-probes-summary-v1.schema.json`, and `docs/schemas/ghidra-attribute-candidate-v1.schema.json`; the promotion gate is `docs/ghidra-pairing-promotion-checklist.md`.

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
- Batch Ghidra review-rank probe refresh wired: `docs/handoffs/2026-05-24-ghidra-review-rank-probes.md`
- Ghidra promotion checklist refreshed for batch probes and grouped candidate guard: `docs/handoffs/2026-05-24-ghidra-promotion-checklist-refresh.md`
- Ghidra workflow guard suite wired: `docs/handoffs/2026-05-24-ghidra-workflow-guard-suite.md`
- Ghidra review-rank probe manifest and vertex semantic-change batch docs wired: `docs/handoffs/2026-05-24-ghidra-review-rank-manifest.md`
- Ghidra review-rank probe manifest schema wired: `docs/handoffs/2026-05-24-ghidra-review-rank-manifest-schema.md`
- Ghidra review-rank probe summary wired: `docs/handoffs/2026-05-24-ghidra-review-rank-probes-summary.md`
- Ghidra review-rank probe summary schema wired: `docs/handoffs/2026-05-24-ghidra-review-rank-probes-summary-schema.md`
- Aggregate tracked schema/doc validation wired: `docs/handoffs/2026-05-25-schema-registry-validation.md`
- Ghidra FunctionSiteSurvey target registry wired: `docs/handoffs/2026-05-24-ghidra-function-site-target-registry.md`
- Ghidra FunctionSiteSurvey target registry schema wired: `docs/handoffs/2026-05-24-ghidra-function-site-target-schema.md`
- Ghidra FunctionSiteSurvey target guard/list/status wired: `docs/handoffs/2026-05-25-ghidra-function-site-target-guard-status.md`
- Ghidra FunctionSiteSurvey list/status schemas wired: `docs/handoffs/2026-05-25-ghidra-function-site-list-status-schemas.md`
- Local FunctionSiteSurvey Markdown summaries refreshed under ignored `Exports/`: `docs/handoffs/2026-05-25-ghidra-function-site-summary-refresh.md`
- Ghidra NiDataStream descriptor targets registered: `docs/handoffs/2026-05-24-ghidra-nidatastream-descriptor-targets.md`
- Ghidra NiDataStream parser-field comparison documented: `docs/handoffs/2026-05-24-ghidra-nidatastream-parser-field-comparison.md`
- Ghidra NiDataStream parser-field promotion checklist added: `docs/handoffs/2026-05-25-ghidra-nidatastream-parser-field-checklist.md`
- Post-Stage-18 NiDataStream promotion status/guard wired: `docs/handoffs/2026-05-25-nidatastream-promotion-status-guard.md`
- NiDataStream layout schema/status wired into promotion status: `docs/handoffs/2026-05-25-nidatastream-layout-schema-status.md`
- NiDataStream descriptor proof status wired: `docs/handoffs/2026-05-25-nidatastream-descriptor-proof-status.md`
- NiDataStream pairing-impact status wired into promotion status: `docs/handoffs/2026-05-25-nidatastream-pairing-impact-status.md`
- NiDataStream promotion-readiness locks documented/tested: `docs/handoffs/2026-05-25-nidatastream-promotion-readiness-lock.md`
- NiDataStream promotion dashboard added: `docs/handoffs/2026-05-25-nidatastream-promotion-dashboard.md`
- NiDataStream evidence timestamp/status command added: `docs/handoffs/2026-05-25-nidatastream-evidence-status.md`
- NiDataStream promotion preflight command added: `docs/handoffs/2026-05-25-nidatastream-promotion-preflight.md`
- NiDataStream descriptor/sample-byte comparison report added: `docs/handoffs/2026-05-25-nidatastream-descriptor-sample-compare.md`
- NiDataStream parser/export promotion decision template added: `docs/handoffs/2026-05-25-nidatastream-promotion-decision-template.md`
- NiDataStream negative fixture guards added: `docs/handoffs/2026-05-25-nidatastream-negative-fixture-guards.md`
- CI runtime warnings documented: `docs/handoffs/2026-05-25-ci-runtime-notes.md`
- NiDataStream parser/export non-consumption guard wired: `docs/handoffs/2026-05-25-nidatastream-parser-export-non-consumption-guard.md`
- NiDataStream dashboard negative fixture guards added: `docs/handoffs/2026-05-25-nidatastream-dashboard-negative-fixtures.md`
- Ghidra/NiDataStream offline quickstart documented: `docs/handoffs/2026-05-25-ghidra-nidatastream-offline-quickstart.md`
- NiDataStream/Ghidra schema policy documented: `docs/handoffs/2026-05-25-nidatastream-ghidra-schema-policy.md`
- TWAD unsupported archive-version warning/test wired: `docs/handoffs/2026-05-24-twad-unsupported-version-warning.md`
- Plan/status for that proof: `docs/plans/2026-05-24-twad-ghidra-proof-plan.md`
- `TWAD` is proven as archive file/header magic; `TWAM` remains manifest-layer magic.
- `NiDataStream::LoadBinary()` and mesh semantic-adapter validation have first-pass static proof; no parser behavior change is recommended yet.
- Parser/export behavior should remain unchanged until the sidecar Ghidra-aligned role/body fields, `TopGhidraRoleDeltas`, little-endian index stats, candidate-only `TopGhidraPairings`, pairing overlap/gap evidence, `TopGhidraPairingReviewFindings`, ignored `ghidra-pairing-review-report` outputs, focused `probe-nif-mesh` `GhidraPairings`, `mesh-probe --review-rank` evidence, and position/normal/UV review fields are reviewed and promoted through a small guarded decoder patch. `ghidra-pairing-non-export-guard` should keep failing closed on any premature export wiring.
- Next safe Ghidra target: continue the `NiDataStream` / `NiMesh` leads from the anchor survey through report-only target runs and parser-field comparison notes.
