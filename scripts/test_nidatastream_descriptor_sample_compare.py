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
    decompile_extras = {
        "nidatastream-loadbinary": [
            "FUN_1411821f0(uVar6)",
            "FUN_141181770(*(undefined4 *)(lVar12 + 4 + (longlong)puVar11))",
            "FUN_1411817c0(*(undefined4 *)(lVar12 + 4 + (longlong)puVar11))",
        ],
        "nidatastream-descriptor-helper": ["(int)param_1 < 0", "(ulonglong)(param_1 & 0xff) * 0xc"],
        "nidatastream-descriptor-builder-1770": ["(int)param_1 < 0", "(ulonglong)(param_1 & 0xff) * 0xc"],
        "nidatastream-descriptor-builder-17c0": ["(int)param_1 < 0", "(ulonglong)(param_1 & 0xff) * 0xc"],
    }
    for index, (key, requirements) in enumerate(rift_workflow.DESCRIPTOR_PROOF_REQUIREMENTS.items(), start=1):
        report_path = report_dir / f"{key}.json"
        summary_path = report_dir / f"{key}.md"
        decompile_terms = list(requirements["RequiredTerms"]) + decompile_extras.get(key, [])
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
                        "c": " ".join(decompile_terms) or "return;",
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
    descriptor_records: list[dict[str, Any]] | None = None,
    shifted_samples: list[dict[str, Any]] | None = None,
) -> None:
    block_count = 5
    prefix_count = block_count if payload_prefix_count is None else payload_prefix_count
    default_shifted_samples = [
        {
            "FirstDescriptorRecordBytes": "aa 04 03 00",
            "FirstPairRecordBytes": "00 00 00 00 05 00 00 00",
            "DataStreamUsage": "1",
            "DataStreamAccess": "19",
            "TypeName": "NiDataStream\u00011\u000119",
        },
        {
            "FirstDescriptorRecordBytes": "aa 04 03 00",
            "FirstPairRecordBytes": "00 00 00 00 05 00 00 00",
            "DataStreamUsage": "1",
            "DataStreamAccess": "19",
            "TypeName": "NiDataStream\u00011\u000119",
        },
        {
            "FirstDescriptorRecordBytes": "aa 04 03 00",
            "FirstPairRecordBytes": "00 00 00 00 06 00 00 00",
            "DataStreamUsage": "2",
            "DataStreamAccess": "19",
            "TypeName": "NiDataStream\u00012\u000119",
        },
        {
            "FirstDescriptorRecordBytes": "bb 02 02 00",
            "FirstPairRecordBytes": "00 00 00 00 07 00 00 00",
            "DataStreamUsage": "3",
            "DataStreamAccess": "19",
            "TypeName": "NiDataStream\u00013\u000119",
        },
        {
            "FirstDescriptorRecordBytes": "bb 02 02 00",
            "FirstPairRecordBytes": "00 00 00 00 07 00 00 00",
            "DataStreamUsage": "3",
            "DataStreamAccess": "19",
            "TypeName": "NiDataStream\u00013\u000119",
        },
    ]
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
                "TopFirstDescriptorRecordBytes": descriptor_records
                if descriptor_records is not None
                else [
                    {"Value": "aa 04 03 00", "Count": 3},
                    {"Value": "bb 02 02 00", "Count": 2},
                ],
                "ShiftedSamples": default_shifted_samples if shifted_samples is None else shifted_samples,
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
record_byte_summary = compare["DescriptorRecordByteSummary"]
check("record byte summary candidate-only", record_byte_summary["CandidateOnly"], True)
check("record byte summary pattern count", record_byte_summary["RecordPatternCount"], 2)
check("record byte summary observed count", record_byte_summary["ObservedRecordCount"], 5)
check("record byte summary width", record_byte_summary["RecordWidthBytes"], 4)
check("record byte offset count", len(record_byte_summary["ByteOffsets"]), 4)
check("record byte offset 0 top value", record_byte_summary["ByteOffsets"][0]["TopValues"][0]["ValueHex"], "aa")
check("record byte offset 0 top count", record_byte_summary["ByteOffsets"][0]["TopValues"][0]["Count"], 3)
record_index_proof = compare["DescriptorRecordIndexProof"]
check("record index proof mapped", record_index_proof["CandidateRecordIndexMapped"], True)
check("record index proof byte offset", record_index_proof["CandidateIndexByteOffset"], 0)
check("record index proof passed count", record_index_proof["PassedEvidenceCount"], 5)
check("record index proof remaining bytes", record_index_proof["RemainingUnmappedByteOffsets"], [1, 2, 3])
helper_argument_use = compare["DescriptorHelperArgumentUseProof"]
check("helper argument proof candidate-only", helper_argument_use["CandidateOnly"], True)
check("helper argument proof high bytes unused", helper_argument_use["HelperLookupHighBytesProvenUnused"], True)
check("helper argument proof high bytes used flag", helper_argument_use["HelperLookupHighBytesUsed"], False)
check("helper argument proof passed count", helper_argument_use["PassedEvidenceCount"], 3)
check("helper argument proof ignored offsets", helper_argument_use["CandidateHelperLookupIgnoredByteOffsets"], [1, 2])
check("helper argument proof sign guard offsets", helper_argument_use["CandidateSignGuardByteOffsets"], [3])
record_byte_roles = compare["DescriptorRecordByteRoleCandidates"]
check("record byte roles candidate-only", record_byte_roles["CandidateOnly"], True)
check("record byte roles all classified", record_byte_roles["AllBytesClassified"], True)
check("record byte roles classified count", record_byte_roles["ClassifiedByteCount"], 4)
check("record byte roles semantic offsets", record_byte_roles["CandidateSemanticByteOffsets"], [0])
check("record byte roles padding offsets", record_byte_roles["CandidatePaddingByteOffsets"], [3])
check("record byte roles remaining offsets", record_byte_roles["RemainingUnmappedByteOffsets"], [1, 2])
role_by_offset = {row["OffsetBytes"]: row for row in record_byte_roles["Rows"]}
check("record byte role offset 0", role_by_offset[0]["CandidateRole"], "static-descriptor-table-index")
check("record byte role offset 1", role_by_offset[1]["CandidateRole"], "unmapped-variable-byte")
check("record byte role offset 3", role_by_offset[3]["CandidateRole"], "zero-padding-or-reserved")
record_pattern_matrix = compare["DescriptorRecordPatternMatrix"]
check("record pattern matrix candidate-only", record_pattern_matrix["CandidateOnly"], True)
check("record pattern matrix rows", record_pattern_matrix["RecordPatternCount"], 2)
check("record pattern matrix observed count", record_pattern_matrix["ObservedRecordCount"], 5)
check("record pattern matrix index offset", record_pattern_matrix["CandidateIndexByteOffset"], 0)
check("record pattern matrix helper ignored offsets", record_pattern_matrix["CandidateHelperLookupIgnoredByteOffsets"], [1, 2])
check("record pattern matrix sign guard offsets", record_pattern_matrix["CandidateSignGuardByteOffsets"], [3])
check("record pattern matrix remaining offsets", record_pattern_matrix["RemainingUnmappedByteOffsets"], [1, 2])
first_pattern_row = record_pattern_matrix["Rows"][0]
check("record pattern matrix first hex", first_pattern_row["RecordHex"], "aa 04 03 00")
check("record pattern matrix first index", first_pattern_row["CandidateIndexByte"]["ValueHex"], "aa")
check("record pattern matrix first helper ignored count", len(first_pattern_row["CandidateHelperLookupIgnoredBytes"]), 2)
check("record pattern matrix first remaining count", len(first_pattern_row["RemainingUnmappedBytes"]), 2)
sample_context = compare["DescriptorSampleContextCorrelation"]
check("sample context candidate-only", sample_context["CandidateOnly"], True)
check("sample context source", sample_context["Source"], "ShiftedSamples")
check("sample context sample count", sample_context["SampleCount"], 5)
check("sample context descriptor samples", sample_context["SamplesWithDescriptorRecord"], 5)
check("sample context pair samples", sample_context["SamplesWithPairRecord"], 5)
check("sample context ready", sample_context["CorrelationReady"], True)
check("sample context pattern count", sample_context["DescriptorPatternCount"], 2)
check("sample context review queue count", sample_context["ReviewQueueCount"], 2)
check(
    "sample context semantic blocker present",
    "descriptor-context-correlation-parser-semantics-unmapped" in sample_context["Blockers"],
    True,
)
first_context_row = sample_context["Rows"][0]
check("sample context first descriptor", first_context_row["DescriptorRecordHex"], "aa 04 03 00")
check("sample context first sample count", first_context_row["SampleCount"], 3)
check("sample context first pair pattern count", first_context_row["PairRecordPatternCount"], 2)
check("sample context first top pair", first_context_row["TopPairRecordBytes"][0]["Value"], "00 00 00 00 05 00 00 00")
check("sample context first top usage", first_context_row["TopUsageValues"][0]["Value"], "1")
first_review_row = sample_context["ReviewQueueRows"][0]
check("sample context review rank", first_review_row["Rank"], 1)
check("sample context review descriptor", first_review_row["DescriptorRecordHex"], "aa 04 03 00")
check("sample context review dominant pair", first_review_row["DominantPairRecordBytes"], "00 00 00 00 05 00 00 00")
check("sample context review dominant pair count", first_review_row["DominantPairRecordCount"], 2)
check("sample context review dominant usage", first_review_row["DominantUsageValue"], "1")
check("sample context review rationale", "candidate-only" in first_review_row["ReviewRationale"].lower(), True)
semantic_feasibility = compare["DescriptorSemanticFeasibility"]
check("semantic feasibility candidate-only", semantic_feasibility["CandidateOnly"], True)
check("semantic feasibility static field map ready", semantic_feasibility["StaticFieldMapReady"], True)
check("semantic feasibility byte distribution ready", semantic_feasibility["DescriptorRecordByteDistributionReady"], True)
check("semantic feasibility record index mapped", semantic_feasibility["DescriptorRecordIndexCandidateMapped"], True)
check("semantic feasibility byte roles classified", semantic_feasibility["DescriptorRecordByteRolesClassified"], True)
check(
    "semantic feasibility high bytes proven unused",
    semantic_feasibility["DescriptorHelperLookupHighBytesProvenUnused"],
    True,
)
check("semantic feasibility mapping blocked", semantic_feasibility["SemanticMappingReady"], False)
check("semantic feasibility static offsets", semantic_feasibility["StaticFieldMapOffsetCount"], 3)
check("semantic feasibility record offsets", semantic_feasibility["DescriptorRecordByteOffsetCount"], 4)
check("semantic feasibility mapped fields", semantic_feasibility["StreamDescriptorRecordMappedCount"], 1)
check("semantic feasibility blocker present", "stream-record-semantics-partial" in semantic_feasibility["Blockers"], True)
check(
    "semantic feasibility remaining byte blocker",
    "stream-record-payload-bytes-unmapped" in semantic_feasibility["Blockers"],
    True,
)
check("semantic feasibility padding offsets", semantic_feasibility["CandidatePaddingByteOffsets"], [3])
check("semantic feasibility helper ignored offsets", semantic_feasibility["CandidateHelperLookupIgnoredByteOffsets"], [1, 2])
check("semantic feasibility sign guard offsets", semantic_feasibility["CandidateSignGuardByteOffsets"], [3])
check("semantic feasibility remaining offsets", semantic_feasibility["RemainingUnmappedRecordByteOffsets"], [1, 2])
first_semantic_row = semantic_feasibility["OffsetComparisonRows"][0]
check("semantic feasibility first field", first_semantic_row["Field"], "descriptor-enable-or-special-flag")
check("semantic feasibility candidate offsets", first_semantic_row["CandidateRecordByteOffsets"], [0, 1, 2, 3])
check(
    "semantic feasibility mapping decision",
    first_semantic_row["MappingDecision"],
    "selected-by-record-byte-0-index-candidate",
)
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
check("descriptor byte examples present", compare["DescriptorByteOrderProof"]["TopFirstDescriptorRecordBytes"][0]["Value"], "aa 04 03 00")
check("sample corpus root", compare["SampleCorpusStatus"]["Root"], "Extracted")
check("sample corpus files scanned", compare["SampleCorpusStatus"]["FilesScanned"], 2)
check("sample corpus shifted samples", compare["SampleCorpusStatus"]["ShiftedSampleCount"], 5)
check("layout block count", compare["LayoutReportStatus"]["NiDataStreamBlocks"], 5)
check("promotion lock blocker present", "parser-export-promotion-locked" in compare["Blockers"], True)
check("semantic blocker present", "stream-record-semantics-partial" in compare["Blockers"], True)
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

print("=== NiDataStream descriptor malformed record fixture ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "Exports"
    targets_file = write_descriptor_fixture(temp_path)
    write_layout_fixture(
        out_dir,
        descriptor_records=[
            {"Value": "aa 04 03 00", "Count": 3},
            {"Value": "not-hex", "Count": 2},
        ],
    )
    malformed_output = io.StringIO()
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
        redirect_stdout(malformed_output),
    ):
        rift_workflow.main()
malformed = json.loads(malformed_output.getvalue())
jsonschema.validate(malformed, schema)
print("  PASS: malformed descriptor record schema validation")
malformed_matrix = malformed["DescriptorRecordPatternMatrix"]
check("malformed matrix rows", malformed_matrix["RecordPatternCount"], 1)
check("malformed matrix malformed count", malformed_matrix["MalformedRecordCount"], 2)
check(
    "malformed matrix blocker present",
    "descriptor-record-pattern-malformed" in malformed_matrix["Blockers"],
    True,
)
check(
    "malformed compare blocker present",
    "descriptor-record-pattern-malformed" in malformed["Blockers"],
    True,
)

print("=== NiDataStream descriptor sample-context malformed fixture ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "Exports"
    targets_file = write_descriptor_fixture(temp_path)
    write_layout_fixture(
        out_dir,
        shifted_samples=[
            {
                "FirstDescriptorRecordBytes": "not-hex",
                "FirstPairRecordBytes": "00 00 00 00 05 00 00 00",
                "DataStreamUsage": "1",
                "DataStreamAccess": "19",
                "TypeName": "NiDataStream\u00011\u000119",
            }
        ],
    )
    malformed_context_output = io.StringIO()
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
        redirect_stdout(malformed_context_output),
    ):
        rift_workflow.main()
malformed_context = json.loads(malformed_context_output.getvalue())
jsonschema.validate(malformed_context, schema)
print("  PASS: malformed descriptor sample-context schema validation")
malformed_context_status = malformed_context["DescriptorSampleContextCorrelation"]
check("malformed context sample count", malformed_context_status["SampleCount"], 1)
check("malformed context ready false", malformed_context_status["CorrelationReady"], False)
check("malformed context rows absent", malformed_context_status["DescriptorPatternCount"], 0)
check("malformed context review queue empty", malformed_context_status["ReviewQueueCount"], 0)
check("malformed context malformed count", malformed_context_status["MalformedDescriptorRecordCount"], 1)
check(
    "malformed context blocker present",
    "descriptor-context-correlation-malformed-descriptor-records" in malformed_context_status["Blockers"],
    True,
)
check(
    "malformed context compare blocker present",
    "descriptor-context-correlation-malformed-descriptor-records" in malformed_context["Blockers"],
    True,
)

promoted_compare = json.loads(json.dumps(compare))
promoted_compare["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects parser/export promotion", promoted_compare, schema)
field_promoted_compare = json.loads(json.dumps(compare))
field_promoted_compare["FieldOrderPromoted"] = True
check_validation_error("schema rejects field order promotion", field_promoted_compare, schema)
field_map_promoted_compare = json.loads(json.dumps(compare))
field_map_promoted_compare["CandidateFieldMap"][0]["PromotionStatus"] = "promoted"
check_validation_error("schema rejects promoted field-map entry", field_map_promoted_compare, schema)
record_byte_promoted_compare = json.loads(json.dumps(compare))
record_byte_promoted_compare["DescriptorRecordByteSummary"]["FieldOrderPromoted"] = True
check_validation_error("schema rejects promoted descriptor record byte summary", record_byte_promoted_compare, schema)
record_index_promoted_compare = json.loads(json.dumps(compare))
record_index_promoted_compare["DescriptorRecordIndexProof"]["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects promoted descriptor record index proof", record_index_promoted_compare, schema)
helper_argument_promoted_compare = json.loads(json.dumps(compare))
helper_argument_promoted_compare["DescriptorHelperArgumentUseProof"]["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects promoted descriptor helper argument proof", helper_argument_promoted_compare, schema)
record_role_promoted_compare = json.loads(json.dumps(compare))
record_role_promoted_compare["DescriptorRecordByteRoleCandidates"]["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects promoted descriptor byte-role candidates", record_role_promoted_compare, schema)
record_pattern_promoted_compare = json.loads(json.dumps(compare))
record_pattern_promoted_compare["DescriptorRecordPatternMatrix"]["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects promoted descriptor record pattern matrix", record_pattern_promoted_compare, schema)
sample_context_promoted_compare = json.loads(json.dumps(compare))
sample_context_promoted_compare["DescriptorSampleContextCorrelation"]["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects promoted descriptor sample context correlation", sample_context_promoted_compare, schema)
sample_context_string_ready_compare = json.loads(json.dumps(compare))
sample_context_string_ready_compare["DescriptorSampleContextCorrelation"]["CorrelationReady"] = "true"
check_validation_error("schema rejects string descriptor sample context ready flag", sample_context_string_ready_compare, schema)
sample_context_bad_review_rank_compare = json.loads(json.dumps(compare))
sample_context_bad_review_rank_compare["DescriptorSampleContextCorrelation"]["ReviewQueueRows"][0]["Rank"] = 0
check_validation_error("schema rejects descriptor sample context review rank zero", sample_context_bad_review_rank_compare, schema)
semantic_promoted_compare = json.loads(json.dumps(compare))
semantic_promoted_compare["DescriptorSemanticFeasibility"]["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects promoted descriptor semantic feasibility", semantic_promoted_compare, schema)
semantic_ready_compare = json.loads(json.dumps(compare))
semantic_ready_compare["DescriptorSemanticFeasibility"]["SemanticMappingReady"] = True
check_validation_error("schema rejects semantic mapping promotion", semantic_ready_compare, schema)

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
    check_contains("markdown descriptor record byte distribution", markdown, "Descriptor record byte distribution")
    check_contains("markdown descriptor record byte value", markdown, "aa (3)")
    check_contains("markdown descriptor record index proof", markdown, "Descriptor record index proof")
    check_contains("markdown descriptor helper argument proof", markdown, "Descriptor helper argument-use proof")
    check_contains("markdown helper high bytes proof", markdown, "Helper lookup high bytes proven unused")
    check_contains("markdown descriptor byte role candidates", markdown, "Descriptor record byte role candidates")
    check_contains("markdown descriptor padding candidate", markdown, "zero-padding-or-reserved")
    check_contains("markdown descriptor record pattern matrix", markdown, "Descriptor record pattern matrix")
    check_contains("markdown descriptor record pattern row", markdown, "aa 04 03 00")
    check_contains("markdown descriptor sample context correlation", markdown, "Descriptor/sample context correlation")
    check_contains("markdown descriptor sample context pair", markdown, "00 00 00 00 05 00 00 00")
    check_contains("markdown descriptor sample context review queue", markdown, "Descriptor/sample context review queue")
    check_contains("markdown descriptor semantic feasibility", markdown, "Descriptor semantic feasibility")
    check_contains("markdown semantic mapping decision", markdown, "selected-by-record-byte-0-index-candidate")
    check_contains("markdown candidate field map", markdown, "Candidate descriptor field map")
    check_contains("markdown format field", markdown, "descriptor-format-size-lookup")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
