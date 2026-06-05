"""Smoke tests for NiDataStream descriptor proof status workflow."""

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


def check_validation_error(desc: str, payload: dict[str, Any], schema: dict[str, Any]) -> None:
    global failed
    try:
        jsonschema.validate(payload, schema)
        print(f"  FAIL: {desc} no validation error")
        failed += 1
    except jsonschema.ValidationError:
        print(f"  PASS: {desc}")


def make_report(path: Path, entry: str, calls: list[str], data_refs: list[str], decompile_terms: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "function": {"entry": entry},
        "callsFromFunction": [{"calleeEntry": call} for call in calls],
        "dataRefsFromFunction": [{"to": ref} for ref in data_refs],
        "decompile": {"completed": True, "errorMessage": "", "c": "\n".join(decompile_terms)},
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def registry_target(key: str, report_name: str) -> dict[str, Any]:
    return {
        "Key": key,
        "Address": "0x141186980",
        "ReportPath": f"Exports/ghidra-reports/{report_name}.json",
        "SummaryPath": f"Exports/ghidra-reports/{report_name}.md",
        "SummaryTerms": ["NiDataStream"],
        "Description": f"{key} test target",
    }


def run_descriptor_status(temp_path: Path, targets_file: Path) -> dict[str, Any]:
    status_output = io.StringIO()
    with (
        patch.object(
            sys,
            "argv",
            [
                "rift_workflow.py",
                "nidatastream-descriptor-proof-status",
                "--ghidra-targets-file",
                str(targets_file),
                "--list-json",
            ],
        ),
        patch("scripts.rift_workflow.REPO_ROOT", temp_path),
        patch("scripts.rift_workflow.generated_output_guard"),
        redirect_stdout(status_output),
    ):
        rift_workflow.main()
    return json.loads(status_output.getvalue())


print("=== NiDataStream descriptor proof status ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    report_root = temp_path / "Exports" / "ghidra-reports"
    make_report(
        report_root / "loadbinary.json",
        "141186980",
        ["1411821f0", "141181770", "1411817c0"],
        [],
        [
            "LoadBinary descriptor calls",
            "FUN_1411821f0(uVar6)",
            "FUN_141181770(*(undefined4 *)(lVar12 + 4 + (longlong)puVar11))",
            "FUN_1411817c0(*(undefined4 *)(lVar12 + 4 + (longlong)puVar11))",
        ],
    )
    make_report(
        report_root / "descriptor-helper.json",
        "1411821f0",
        ["141182280"],
        ["143358be0", "143358be4", "143358be8"],
        ["(int)param_1 < 0", "(&DAT_143358be0)[(ulonglong)(param_1 & 0xff) * 0xc]"],
    )
    make_report(
        report_root / "descriptor-builder-1770.json",
        "141181770",
        [],
        ["143358be0", "143358be4", "143358b01"],
        ["(int)param_1 < 0", "(&DAT_143358be4)[(ulonglong)(param_1 & 0xff) * 0xc]"],
    )
    make_report(
        report_root / "descriptor-builder-17c0.json",
        "1411817c0",
        ["141182280"],
        ["143358be0", "143358be8", "143358b04"],
        ["(int)param_1 < 0", "(&DAT_143358be8 + (ulonglong)(param_1 & 0xff) * 0xc)"],
    )
    targets_file = temp_path / "targets.json"
    registry = {
        "SchemaVersion": "ghidra-function-site-targets/v1",
        "CandidateOnly": True,
        "DefaultProjectName": "RiftAnchorSurvey",
        "DefaultProcess": "rift_x64.exe",
        "DefaultScript": "scripts/ghidra/FunctionSiteSurvey.java",
        "DefaultNoAnalysis": True,
        "DefaultKeepProject": True,
        "DefaultTimeoutSeconds": 900,
        "Targets": [
            registry_target("nidatastream-loadbinary", "loadbinary"),
            registry_target("nidatastream-descriptor-helper", "descriptor-helper"),
            registry_target("nidatastream-descriptor-builder-1770", "descriptor-builder-1770"),
            registry_target("nidatastream-descriptor-builder-17c0", "descriptor-builder-17c0"),
        ],
    }
    targets_file.write_text(json.dumps(registry), encoding="utf-8")
    status = run_descriptor_status(temp_path, targets_file)

schema = json.loads(
    Path("docs/schemas/nidatastream-descriptor-proof-status-v1.schema.json").read_text(encoding="utf-8")
)
jsonschema.validate(status, schema)
print("  PASS: descriptor status schema validation")
check("descriptor schema", status["SchemaVersion"], "nidatastream-descriptor-proof-status/v1")
check("candidate only", status["CandidateOnly"], True)
check("field order not promoted", status["FieldOrderPromoted"], False)
check("all descriptor evidence ready", status["AllRequiredEvidenceReady"], True)
check("ready count", status["EvidenceReadyCount"], 4)
check("target count", status["RequiredTargetCount"], 4)
check("field map rows", len(status["CandidateFieldMap"]) >= 4, True)
stride_field = next(field for field in status["CandidateFieldMap"] if field["Field"] == "descriptor-table-stride")
component_field = next(field for field in status["CandidateFieldMap"] if field["Field"] == "descriptor-component-class")
check("field map promotion status", stride_field["PromotionStatus"], "candidate-only")
check("field map static table stride", stride_field["StaticTableStrideBytes"], 12)
check("field map component offset", component_field["StaticTableOffsetBytes"], 4)
check("field map stream record status", component_field["StreamDescriptorRecordStatus"], "not-mapped-to-parser-field")
record_index_proof = status["DescriptorRecordIndexProof"]
check("record index proof candidate-only", record_index_proof["CandidateOnly"], True)
check("record index proof mapped", record_index_proof["CandidateRecordIndexMapped"], True)
check("record index proof byte offset", record_index_proof["CandidateIndexByteOffset"], 0)
check("record index proof passed count", record_index_proof["PassedEvidenceCount"], 5)
check("record index remaining bytes", record_index_proof["RemainingUnmappedByteOffsets"], [1, 2, 3])
helper_argument_use = status["DescriptorHelperArgumentUseProof"]
check("helper argument proof candidate-only", helper_argument_use["CandidateOnly"], True)
check("helper argument proof high bytes unused", helper_argument_use["HelperLookupHighBytesProvenUnused"], True)
check("helper argument proof high bytes used flag", helper_argument_use["HelperLookupHighBytesUsed"], False)
check("helper argument proof passed count", helper_argument_use["PassedEvidenceCount"], 3)
check("helper argument proof ignored offsets", helper_argument_use["CandidateHelperLookupIgnoredByteOffsets"], [1, 2])
check("helper argument proof sign guard offsets", helper_argument_use["CandidateSignGuardByteOffsets"], [3])
promoted_field_status = json.loads(json.dumps(status))
promoted_field_status["CandidateFieldMap"][0]["PromotionStatus"] = "promoted"
check_validation_error("schema rejects promoted field-map entry", promoted_field_status, schema)
promoted_record_index_status = json.loads(json.dumps(status))
promoted_record_index_status["DescriptorRecordIndexProof"]["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects promoted record index proof", promoted_record_index_status, schema)
promoted_helper_argument_status = json.loads(json.dumps(status))
promoted_helper_argument_status["DescriptorHelperArgumentUseProof"]["ParserExportPromotionAllowed"] = True
check_validation_error("schema rejects promoted helper argument proof", promoted_helper_argument_status, schema)

print("=== NiDataStream descriptor proof negative fixture ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    report_root = temp_path / "Exports" / "ghidra-reports"
    make_report(
        report_root / "loadbinary.json",
        "141186980",
        ["1411821f0", "141181770", "1411817c0"],
        [],
        ["LoadBinary descriptor calls"],
    )
    make_report(
        report_root / "descriptor-helper.json",
        "1411821f0",
        [],
        ["143358be0", "143358be4", "143358be8"],
        ["(&DAT_143358be0)[index * 0xc]"],
    )
    make_report(
        report_root / "descriptor-builder-1770.json",
        "141181770",
        [],
        ["143358be0", "143358be4", "143358b01"],
        ["(&DAT_143358be4)[index * 0xc]"],
    )
    make_report(
        report_root / "descriptor-builder-17c0.json",
        "1411817c0",
        ["141182280"],
        ["143358be0", "143358be8", "143358b04"],
        ["(&DAT_143358be8 + index * 0xc)"],
    )
    targets_file = temp_path / "targets.json"
    registry["Targets"] = [
        registry_target("nidatastream-loadbinary", "loadbinary"),
        registry_target("nidatastream-descriptor-helper", "descriptor-helper"),
        registry_target("nidatastream-descriptor-builder-1770", "descriptor-builder-1770"),
        registry_target("nidatastream-descriptor-builder-17c0", "descriptor-builder-17c0"),
    ]
    targets_file.write_text(json.dumps(registry), encoding="utf-8")
    negative_status = run_descriptor_status(temp_path, targets_file)
jsonschema.validate(negative_status, schema)
print("  PASS: negative descriptor status schema validation")
check("negative descriptor evidence blocks readiness", negative_status["AllRequiredEvidenceReady"], False)
helper_status = next(
    target for target in negative_status["Targets"] if target["Key"] == "nidatastream-descriptor-helper"
)
check("negative descriptor missing call", helper_status["MissingCalls"], ["141182280"])
check(
    "negative record index proof blocks",
    negative_status["DescriptorRecordIndexProof"]["CandidateRecordIndexMapped"],
    False,
)
check(
    "negative helper argument proof blocks",
    negative_status["DescriptorHelperArgumentUseProof"]["HelperLookupHighBytesProvenUnused"],
    False,
)

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
