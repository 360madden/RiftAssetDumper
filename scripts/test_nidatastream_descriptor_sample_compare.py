"""Smoke tests for the NiDataStream descriptor/sample-byte comparison report."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import jsonschema

sys.path.insert(0, ".")

from scripts import rift_workflow

failed = 0


def check(desc: str, actual: Any, expected: Any) -> None:
    global failed
    if actual == expected:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} expected={expected!r} actual={actual!r}")
        failed += 1


def check_contains(desc: str, text: str, expected: str) -> None:
    global failed
    if expected in text:
        print(f"  PASS: {desc}")
    else:
        print(f"  FAIL: {desc} missing={expected!r}")
        failed += 1


def check_validation_error(desc: str, payload: dict[str, Any], schema: dict[str, Any]) -> None:
    global failed
    try:
        jsonschema.validate(payload, schema)
        print(f"  FAIL: {desc} no validation error")
        failed += 1
    except jsonschema.ValidationError:
        print(f"  PASS: {desc}")


def write_descriptor_fixture(temp_path: Path) -> Path:
    out_dir = temp_path / "Exports"
    report_dir = out_dir / "ghidra-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    targets: list[dict[str, Any]] = []
    address_base = 0x141180000
    for index, (key, requirements) in enumerate(rift_workflow.DESCRIPTOR_PROOF_REQUIREMENTS.items(), start=1):
        report_path = report_dir / f"{key}.json"
        summary_path = report_dir / f"{key}.md"
        report_path.write_text(
            json.dumps(
                {
                    "function": {"entry": f"{address_base + index:x}"},
                    "callsFromFunction": [
                        {"calleeEntry": f"0x{call}"} for call in requirements["RequiredCalls"]
                    ],
                    "dataRefsFromFunction": [
                        {"to": f"0x{data_ref}"} for data_ref in requirements["RequiredDataRefs"]
                    ],
                    "decompile": {
                        "completed": True,
                        "c": " ".join(requirements["RequiredTerms"]) or "return;",
                    },
                }
            ),
            encoding="utf-8",
        )
        summary_path.write_text(f"# {key}\n", encoding="utf-8")
        targets.append(
            {
                "Key": key,
                "Address": f"0x{address_base + index:x}",
                "ReportPath": f"Exports/ghidra-reports/{key}.json",
                "SummaryPath": f"Exports/ghidra-reports/{key}.md",
                "SummaryTerms": ["NiDataStream"],
                "Description": f"{key} test fixture",
            }
        )

    targets_file = temp_path / "targets.json"
    targets_file.write_text(
        json.dumps(
            {
                "SchemaVersion": "ghidra-function-site-targets/v1",
                "CandidateOnly": True,
                "Targets": targets,
            }
        ),
        encoding="utf-8",
    )
    return targets_file


def write_layout_fixture(out_dir: Path, *, payload_prefix: int = 28, payload_prefix_count: int | None = None) -> None:
    block_count = 5
    prefix_count = block_count if payload_prefix_count is None else payload_prefix_count
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "nidatastream-layout-report.json").write_text(
        json.dumps(
            {
                "Schema": "nidatastream-layout-report/v1",
                "CandidateOnly": True,
                "FilesScanned": 2,
                "FilesParsed": 2,
                "NiDataStreamBlocks": block_count,
                "GhidraStyleLayoutValidBlocks": block_count,
                "LegacyOffsetShiftedBlocks": block_count,
                "TopPayloadPrefixBytes": [{"Value": payload_prefix, "Count": prefix_count}],
                "TopPayloadTrailerBytes": [{"Value": 1, "Count": block_count}],
                "TopTrailingFlags": [{"Value": 1, "Count": block_count}],
                "TopLegacyOffsetMinusGhidraOffset": [{"Value": 1, "Count": block_count}],
                "TopPairCounts": [{"Value": 1, "Count": block_count}],
                "TopDescriptorCounts": [{"Value": 1, "Count": block_count}],
            }
        ),
        encoding="utf-8",
    )


schema = json.loads(
    Path("docs/schemas/nidatastream-descriptor-sample-compare-v1.schema.json").read_text(encoding="utf-8")
)

print("=== NiDataStream descriptor/sample-byte compare list-json ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "Exports"
    targets_file = write_descriptor_fixture(temp_path)
    write_layout_fixture(out_dir)
    compare_output = io.StringIO()
    with (
        patch.object(
            sys,
            "argv",
            [
                "rift_workflow.py",
                "nidatastream-descriptor-sample-compare",
                "--out",
                str(out_dir),
                "--ghidra-targets-file",
                str(targets_file),
                "--list-json",
            ],
        ),
        patch("scripts.rift_workflow.REPO_ROOT", temp_path),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(compare_output),
    ):
        rift_workflow.main()
compare = json.loads(compare_output.getvalue())
jsonschema.validate(compare, schema)
print("  PASS: descriptor/sample compare schema validation")
check("schema version", compare["SchemaVersion"], "nidatastream-descriptor-sample-compare/v1")
check("candidate-only", compare["CandidateOnly"], True)
check("promotion locked", compare["ParserExportPromotionAllowed"], False)
check("field order locked", compare["FieldOrderPromoted"], False)
check("descriptor ready", compare["DescriptorStatus"]["AllRequiredEvidenceReady"], True)
check("sample checks ready", compare["SampleByteSummary"]["AllExpectedValuesUniform"], True)
check("descriptor + sample evidence ready", compare["DescriptorAndSampleEvidenceReady"], True)
check("sample check count", compare["SampleByteSummary"]["CheckCount"], 6)
check("sample passed count", compare["SampleByteSummary"]["PassedCount"], 6)
check("layout block count", compare["LayoutReportStatus"]["NiDataStreamBlocks"], 5)
check("promotion lock blocker present", "parser-export-promotion-locked" in compare["Blockers"], True)
check("promotion gate blockers present", "narrow-parser-patch" in compare["PromotionGateBlockers"], True)

print("=== NiDataStream descriptor/sample-byte compare mismatch fixture ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "Exports"
    targets_file = write_descriptor_fixture(temp_path)
    write_layout_fixture(out_dir, payload_prefix=29)
    mismatch_output = io.StringIO()
    with (
        patch.object(
            sys,
            "argv",
            [
                "rift_workflow.py",
                "nidatastream-descriptor-sample-compare",
                "--out",
                str(out_dir),
                "--ghidra-targets-file",
                str(targets_file),
                "--list-json",
            ],
        ),
        patch("scripts.rift_workflow.REPO_ROOT", temp_path),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(mismatch_output),
    ):
        rift_workflow.main()
mismatch = json.loads(mismatch_output.getvalue())
jsonschema.validate(mismatch, schema)
print("  PASS: mismatch comparison schema validation")
prefix_check = next(check for check in mismatch["SampleByteSummary"]["Checks"] if check["Key"] == "payload-prefix-bytes")
check("mismatch sample checks fail", mismatch["SampleByteSummary"]["AllExpectedValuesUniform"], False)
check("mismatch descriptor + sample evidence not ready", mismatch["DescriptorAndSampleEvidenceReady"], False)
check("mismatch prefix observed", prefix_check["ObservedInteger"], 29)
check("mismatch prefix does not match", prefix_check["MatchesExpected"], False)
check("mismatch blocker present", "sample-byte-uniformity-incomplete" in mismatch["Blockers"], True)

promoted_compare = json.loads(json.dumps(compare))
promoted_compare["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects parser/export promotion", promoted_compare, schema)
field_promoted_compare = json.loads(json.dumps(compare))
field_promoted_compare["FieldOrderPromoted"] = True
check_validation_error("schema rejects field order promotion", field_promoted_compare, schema)

print("=== NiDataStream descriptor/sample-byte compare writes ignored reports ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "Exports"
    targets_file = write_descriptor_fixture(temp_path)
    write_layout_fixture(out_dir)
    console = io.StringIO()
    with (
        patch.object(
            sys,
            "argv",
            [
                "rift_workflow.py",
                "nidatastream-descriptor-sample-compare",
                "--out",
                str(out_dir),
                "--ghidra-targets-file",
                str(targets_file),
            ],
        ),
        patch("scripts.rift_workflow.REPO_ROOT", temp_path),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(console),
    ):
        rift_workflow.main()
    json_path = out_dir / "nidatastream-descriptor-sample-compare.json"
    markdown_path = out_dir / "nidatastream-descriptor-sample-compare.md"
    check("comparison json written", json_path.exists(), True)
    check("comparison markdown written", markdown_path.exists(), True)
    jsonschema.validate(json.loads(json_path.read_text(encoding="utf-8")), schema)
    print("  PASS: written comparison JSON schema validation")
    check_contains("console reports candidate-only", console.getvalue(), "candidate-only/report-only")
    check_contains("markdown title", markdown_path.read_text(encoding="utf-8"), "# NiDataStream descriptor/sample-byte comparison")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
