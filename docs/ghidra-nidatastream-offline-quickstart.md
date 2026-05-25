# Ghidra + NiDataStream offline quickstart

Status date: 2026-05-25

This workflow is for offline/static evidence only. It does not require the live game client after the executable and copied sample inputs already exist locally. Keep generated Ghidra projects, reports, copied samples, and extraction output ignored.

## Safety rules

- Treat Ghidra evidence as candidate-only until promotion gates pass.
- Do not commit `Source/`, `Extracted/`, `Exports/`, generated reports, copied assets, `bin/`, `obj/`, caches, or `.pyc` files.
- Do not change parser/export behavior from Ghidra evidence until `ParserExportPromotionAllowed` is deliberately changed through a reviewed proof patch.
- Prefer retained-project reruns over repeated full imports once the first Ghidra import has succeeded.
- Run retained-project Ghidra jobs serially; shared Ghidra projects can lock under parallel runs.

## 1. Check local tool wiring

```powershell
python scripts/rift_workflow.py tools-status
python scripts/rift_workflow.py ghidra-dry-run --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project
```

Expected result: the repo can find the configured Ghidra/JDK/tool paths and can print a headless command without committing local paths.

## 2. Inspect registered Ghidra targets

```powershell
python scripts/rift_workflow.py ghidra-function-site-target-guard
python scripts/rift_workflow.py ghidra-function-site-survey --list-json
python scripts/rift_workflow.py ghidra-function-site-status --list-json
python scripts/rift_workflow.py nidatastream-evidence-status --list-json
```

Use target keys from `docs/ghidra-function-site-targets.json`. Reports and summaries must stay under ignored `Exports/ghidra-reports/`.

## 3. Print or run one serialized NiDataStream target

Dry-run/print the exact commands first:

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-loadbinary
```

Run only when intentionally refreshing ignored evidence:

```powershell
python scripts/rift_workflow.py ghidra-function-site-survey --ghidra-target nidatastream-loadbinary --ghidra-execute --ghidra-project-name RiftAnchorSurvey --ghidra-process rift_x64.exe --ghidra-no-analysis --ghidra-keep-project --ghidra-timeout 900
```

For a first full import/analysis, use a much larger timeout such as `--ghidra-timeout 14400`. Prefer shorter retained-project reruns after that.

## 4. Summarize Ghidra evidence

```powershell
python scripts/rift_workflow.py ghidra-summarize --ghidra-report Exports/ghidra-reports/nidatastream_loadbinary.json --ghidra-summary-term NiDataStream --ghidra-summary-term LoadBinary --ghidra-summary-out Exports/ghidra-reports/nidatastream_loadbinary.md
python scripts/rift_workflow.py nidatastream-descriptor-proof-status --list-json
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-descriptor-table-sample
```

Descriptor status is still candidate-only. `FieldOrderPromoted` must remain false until a separate promotion patch proves otherwise.
The descriptor/sample compare command writes ignored JSON/Markdown under `Exports/` and checks descriptor-helper readiness, copied-sample byte-counter evidence, and descriptor-table sample status without changing parser/export behavior.
The descriptor-table sample command prints a plan by default; use `--list-json` for machine-readable planning and `--ghidra-execute` only when intentionally refreshing ignored `Exports/ghidra-reports/nidatastream_descriptor_table_samples.*` evidence. Current sampled candidate table rows are readable but zero, so they are blocker evidence rather than promotion proof.

## 5. Refresh local sample-byte evidence only when needed

```powershell
python scripts/rift_workflow.py nidatastream-layout --root Extracted --full
```

This scans copied/extracted local samples and writes ignored `Exports/nidatastream-layout-report.json` and `.md` files. The report includes sample corpus metadata, prefix/trailer distributions, pair/descriptor count offsets, and first pair/descriptor record byte examples. Do not stage those outputs.

## 6. Check Ghidra pairing impact

```powershell
python scripts/rift_workflow.py ghidra-pairing-review-report --quick --limit 25
python scripts/rift_workflow.py ghidra-attribute-candidate-report
python scripts/rift_workflow.py ghidra-attribute-candidate-guard
```

Current guard baseline expects zero complete Ghidra-only position+normal+UV candidate groups. A complete group is not automatically promotion; it is a review trigger.

## 7. Run promotion brakes before any parser/export work

```powershell
python scripts/rift_workflow.py nidatastream-promotion-preflight
```

The preflight writes the ignored dashboard and descriptor/sample comparison, prints ignored evidence artifact timestamp/status, runs the current Ghidra/NiDataStream promotion guard suite, and reruns generated-output safety at the end. Expanded equivalent checks:

```powershell
python scripts/rift_workflow.py nidatastream-promotion-status --list-json
python scripts/rift_workflow.py nidatastream-promotion-dashboard
python scripts/rift_workflow.py nidatastream-descriptor-sample-compare
python scripts/rift_workflow.py nidatastream-parser-export-non-consumption-guard
python scripts/rift_workflow.py nidatastream-parser-field-proof-guard
python scripts/rift_workflow.py ghidra-workflow-guard-suite --skip-build
python scripts/rift_workflow.py generated-output-guard
```

Expected current result:

- `CandidateOnly: true`
- `ParserExportPromotionAllowed: false`
- `FieldOrderPromoted: false`
- parser/export non-consumption guard passes
- workflow guard suite passes while promotion remains blocked

## Promotion rule

Only consider a parser/export patch after all of these have a positive proof:

1. FunctionSite targets and summaries are ready.
2. Descriptor field order is proved from Ghidra and parser/sample bytes.
3. Sample-byte layout evidence covers the selected corpus.
4. Pairing impact improves useful position/normal/UV evidence without promoting noise.
5. Negative fixtures and schemas still fail closed.
6. Generated-output guard confirms no copied/generated assets are staged.
