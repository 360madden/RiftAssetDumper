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


def write_layout_fixture(
    out_dir: Path,
    *,
    payload_prefix: int = 28,
    payload_prefix_count: int | None = None,
    descriptor_record_offset: int = 24,
) -> None:
    block_count = 5
    prefix_count = block_count if payload_prefix_count is None else payload_prefix_count
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "nidatastream-layout-report.json").write_text(
        json.dumps(
            {
                "Schema": "nidatastream-layout-report/v1",
                "CandidateOnly": True,
                "Root": "Extracted",
                "MaxFiles": None,
                "FilesScanned": 2,
                "FilesParsed": 2,
                "FilesWithNiDataStreamBlocks": 2,
                "ParseErrorCount": 0,
                "NiDataStreamBlocks": block_count,
                "GhidraStyleLayoutValidBlocks": block_count,
                "LegacyOffsetShiftedBlocks": block_count,
                "TopPayloadPrefixBytes": [{"Value": payload_prefix, "Count": prefix_count}],
                "TopPayloadTrailerBytes": [{"Value": 1, "Count": block_count}],
                "TopTrailingFlags": [{"Value": 1, "Count": block_count}],
                "TopLegacyOffsetMinusGhidraOffset": [{"Value": 1, "Count": block_count}],
                "TopSecondUInt32": [{"Value": 0, "Count": block_count}],
                "TopPairCounts": [{"Value": 1, "Count": block_count}],
                "TopPairRecordOffsets": [{"Value": 12, "Count": block_count}],
                "TopFirstPairRecordBytes": [{"Value": "04 00 00 00 05 00 00 00", "Count": block_count}],
                "TopDescriptorCounts": [{"Value": 1, "Count": block_count}],
                "TopDescriptorCountOffsets": [{"Value": 20, "Count": block_count}],
                "TopDescriptorRecordOffsets": [{"Value": descriptor_record_offset, "Count": block_count}],
                "TopFirstDescriptorRecordBytes": [{"Value": "aa 00 00 00", "Count": block_count}],
                "ShiftedSamples": [],
                "Warnings": [],
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
check("byte-order checks ready", compare["DescriptorByteOrderProof"]["AllExpectedFieldsUniform"], True)
check("descriptor + sample evidence ready", compare["DescriptorAndSampleEvidenceReady"], True)
check("sample check count", compare["SampleByteSummary"]["CheckCount"], 6)
check("sample passed count", compare["SampleByteSummary"]["PassedCount"], 6)
check("byte-order check count", compare["DescriptorByteOrderProof"]["CheckCount"], 7)
check("byte-order passed count", compare["DescriptorByteOrderProof"]["PassedCount"], 7)
check("candidate field map count", len(compare["CandidateFieldMap"]), 4)
stride_field = next(field for field in compare["CandidateFieldMap"] if field["Field"] == "descriptor-table-stride")
format_field = next(field for field in compare["CandidateFieldMap"] if field["Field"] == "descriptor-format-size-lookup")
check("field map promotion status", stride_field["PromotionStatus"], "candidate-only")
check("field map table stride", stride_field["StaticTableStrideBytes"], 12)
check("field map format offset", format_field["StaticTableOffsetBytes"], 8)
check("field map stream record not promoted", format_field["StreamDescriptorRecordStatus"], "not-mapped-to-parser-field")
descriptor_record_check = next(
    check for check in compare["DescriptorByteOrderProof"]["Checks"] if check["Key"] == "descriptor-record-offset"
)
check("descriptor record offset observed", descriptor_record_check["ObservedInteger"], 24)
check("descriptor byte examples present", compare["DescriptorByteOrderProof"]["TopFirstDescriptorRecordBytes"][0]["Value"], "aa 00 00 00")
check("sample corpus root", compare["SampleCorpusStatus"]["Root"], "Extracted")
check("sample corpus files scanned", compare["SampleCorpusStatus"]["FilesScanned"], 2)
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

print("=== NiDataStream descriptor byte-order mismatch fixture ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "Exports"
    targets_file = write_descriptor_fixture(temp_path)
    write_layout_fixture(out_dir, descriptor_record_offset=25)
    byte_order_output = io.StringIO()
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
        redirect_stdout(byte_order_output),
    ):
        rift_workflow.main()
byte_order_mismatch = json.loads(byte_order_output.getvalue())
jsonschema.validate(byte_order_mismatch, schema)
print("  PASS: byte-order mismatch comparison schema validation")
descriptor_offset_check = next(
    check for check in byte_order_mismatch["DescriptorByteOrderProof"]["Checks"] if check["Key"] == "descriptor-record-offset"
)
check("byte-order mismatch checks fail", byte_order_mismatch["DescriptorByteOrderProof"]["AllExpectedFieldsUniform"], False)
check("byte-order mismatch descriptor + sample evidence not ready", byte_order_mismatch["DescriptorAndSampleEvidenceReady"], False)
check("byte-order mismatch observed", descriptor_offset_check["ObservedInteger"], 25)
check("byte-order mismatch blocker present", "descriptor-byte-order-incomplete" in byte_order_mismatch["Blockers"], True)

promoted_compare = json.loads(json.dumps(compare))
promoted_compare["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects parser/export promotion", promoted_compare, schema)
field_promoted_compare = json.loads(json.dumps(compare))
field_promoted_compare["FieldOrderPromoted"] = True
check_validation_error("schema rejects field order promotion", field_promoted_compare, schema)
field_map_promoted_compare = json.loads(json.dumps(compare))
field_map_promoted_compare["CandidateFieldMap"][0]["PromotionStatus"] = "promoted"
check_validation_error("schema rejects promoted field-map entry", field_map_promoted_compare, schema)

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
    markdown = markdown_path.read_text(encoding="utf-8")
    check_contains("markdown title", markdown, "# NiDataStream descriptor/sample-byte comparison")
    check_contains("markdown candidate field map", markdown, "Candidate descriptor field map")
    check_contains("markdown format field", markdown, "descriptor-format-size-lookup")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
