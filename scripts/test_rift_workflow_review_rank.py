"""Smoke tests for mesh-probe --review-rank workflow routing."""

from __future__ import annotations

import json
import sys
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
        print(f"  FAIL: {desc}  expected={expected!r}  actual={actual!r}")
        failed += 1


def check_raises(desc: str, fn: Any, exc_type: type[BaseException] = SystemExit) -> None:
    global failed
    try:
        fn()
        print(f"  FAIL: {desc} (no exception raised)")
        failed += 1
    except exc_type:
        print(f"  PASS: {desc}")


def write_review_report(out_dir: Path, rank: int, asset_id: str, mesh_block: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ghidra-pairing-review-report.json").write_text(
        json.dumps(
            {
                "SchemaVersion": "ghidra-pairing-review-report/v1",
                "CandidateOnly": True,
                "Findings": [
                    {
                        "Rank": rank,
                        "ReviewKind": "ghidra-only",
                        "SampleIdPrefix": asset_id,
                        "SampleMeshBlockIndex": mesh_block,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


print("=== mesh-probe --review-rank ===")
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "exports"
    asset_id = "25f30ec90608eab7"
    write_review_report(out_dir, rank=2, asset_id=asset_id, mesh_block=7)

    captured: dict[str, Any] = {}

    def fake_dotnet_run(**kwargs: Any) -> None:
        captured.update(kwargs)

    workflow_argv = [
        "rift_workflow.py",
        "mesh-probe",
        "--review-rank",
        "2",
        "--out",
        str(out_dir),
        "--skip-build",
    ]
    with (
        patch.object(sys, "argv", workflow_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.rift_workflow._run_dotnet_and_summarize", side_effect=fake_dotnet_run),
    ):
        rift_workflow.main()

    check("rank resolved asset id", captured["asset_id"], asset_id)
    check("rank resolved mesh block", captured["mesh_block"], 7)
    check("rank keeps command", captured["command"], "mesh-probe")

    conflict_argv = [
        "rift_workflow.py",
        "mesh-probe",
        "--review-rank",
        "2",
        "--id",
        "0000000000000000",
        "--out",
        str(out_dir),
        "--skip-build",
    ]
    with (
        patch.object(sys, "argv", conflict_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.rift_workflow._run_dotnet_and_summarize", side_effect=fake_dotnet_run),
    ):
        check_raises("conflicting explicit id fails closed", rift_workflow.main)

    rebuild_out = temp_path / "rebuild-exports"
    rebuild_out.mkdir()
    (rebuild_out / "nif-mesh-binding-inventory.json").write_text("{}", encoding="utf-8")

    def fake_review_report(_inventory_path: str, output_dir: Path, take: int = 100) -> None:
        check("review report rebuild take", take, 100)
        write_review_report(output_dir, rank=5, asset_id=asset_id, mesh_block=25)

    captured.clear()
    rebuild_argv = [
        "rift_workflow.py",
        "mesh-probe",
        "--review-rank",
        "5",
        "--out",
        str(rebuild_out),
        "--skip-build",
    ]
    with (
        patch.object(sys, "argv", rebuild_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.rift_workflow.ghidra_pairing_review_report", side_effect=fake_review_report),
        patch("scripts.rift_workflow._run_dotnet_and_summarize", side_effect=fake_dotnet_run),
    ):
        rift_workflow.main()

    check("missing report rebuilt from inventory", captured["mesh_block"], 25)

print("=== ghidra-review-rank-probes ===")
manifest_schema = json.loads(
    Path("docs/schemas/ghidra-review-rank-probes-manifest-v1.schema.json").read_text(encoding="utf-8")
)
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "batch-exports"
    out_dir.mkdir()
    (out_dir / "ghidra-pairing-review-report.json").write_text(
        json.dumps(
            {
                "SchemaVersion": "ghidra-pairing-review/v1",
                "CandidateOnly": True,
                "Findings": [
                    {
                        "Rank": 1,
                        "ReviewKind": "ghidra-only",
                        "SampleIdPrefix": "1111111111111111",
                        "SampleMeshBlockIndex": 7,
                    },
                    {
                        "Rank": 2,
                        "ReviewKind": "shared",
                        "SampleIdPrefix": "2222222222222222",
                        "SampleMeshBlockIndex": 8,
                    },
                    {
                        "Rank": 3,
                        "ReviewKind": "ghidra-only",
                        "SampleIdPrefix": "3333333333333333",
                        "SampleMeshBlockIndex": 9,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    captured_calls: list[dict[str, Any]] = []

    def fake_batch_dotnet_run(**kwargs: Any) -> None:
        captured_calls.append(kwargs)

    batch_argv = [
        "rift_workflow.py",
        "ghidra-review-rank-probes",
        "--out",
        str(out_dir),
        "--limit",
        "2",
        "--skip-build",
    ]
    with (
        patch.object(sys, "argv", batch_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.rift_workflow._run_dotnet_and_summarize", side_effect=fake_batch_dotnet_run),
    ):
        rift_workflow.main()

    check("batch probes ghidra-only count", len(captured_calls), 2)
    check("batch first asset", captured_calls[0]["asset_id"], "1111111111111111")
    check("batch first rank dir", captured_calls[0]["out_dir"].name, "rank01")
    check("batch skips shared finding", captured_calls[1]["asset_id"], "3333333333333333")
    check("batch second rank dir", captured_calls[1]["out_dir"].name, "rank03")
    manifest = json.loads((out_dir / "ghidra-review-rank-probes" / "manifest-ghidra-only.json").read_text(encoding="utf-8"))
    check("batch manifest schema", manifest["SchemaVersion"], "ghidra-review-rank-probes-manifest/v1")
    check("batch manifest selected count", manifest["SelectedCount"], 2)
    check("batch manifest kind", manifest["ReviewKindFilter"], "ghidra-only")
    jsonschema.validate(manifest, manifest_schema)
    print("  PASS: batch manifest schema validation")

with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    out_dir = temp_path / "vertex-rebuild"
    out_dir.mkdir()
    (out_dir / "nif-mesh-binding-inventory.json").write_text("{}", encoding="utf-8")
    captured_calls = []

    def fake_vertex_review_report(_inventory_path: str, output_dir: Path, take: int = 100) -> None:
        check("vertex rebuild uses review report limit", take, 100)
        (output_dir / "ghidra-pairing-review-report.json").write_text(
            json.dumps(
                {
                    "SchemaVersion": "ghidra-pairing-review/v1",
                    "CandidateOnly": True,
                    "Findings": [
                        {
                            "Rank": 1,
                            "ReviewKind": "ghidra-only",
                            "SampleIdPrefix": "1111111111111111",
                            "SampleMeshBlockIndex": 7,
                        },
                        {
                            "Rank": 15,
                            "ReviewKind": "vertex-semantic-change",
                            "SampleIdPrefix": "aaaaaaaaaaaaaaaa",
                            "SampleMeshBlockIndex": 11,
                        },
                        {
                            "Rank": 16,
                            "ReviewKind": "vertex-semantic-change",
                            "SampleIdPrefix": "bbbbbbbbbbbbbbbb",
                            "SampleMeshBlockIndex": 12,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

    vertex_argv = [
        "rift_workflow.py",
        "ghidra-review-rank-probes",
        "--out",
        str(out_dir),
        "--limit",
        "1",
        "--review-kind",
        "vertex-semantic-change",
        "--skip-build",
    ]
    with (
        patch.object(sys, "argv", vertex_argv),
        patch("scripts.rift_workflow.generated_output_guard"),
        patch("scripts.rift_workflow.ghidra_pairing_review_report", side_effect=fake_vertex_review_report),
        patch("scripts.rift_workflow._run_dotnet_and_summarize", side_effect=fake_batch_dotnet_run),
    ):
        rift_workflow.main()

    check("vertex batch selected count", len(captured_calls), 1)
    check("vertex batch first asset", captured_calls[0]["asset_id"], "aaaaaaaaaaaaaaaa")
    vertex_manifest = json.loads(
        (out_dir / "ghidra-review-rank-probes" / "manifest-vertex-semantic-change.json").read_text(encoding="utf-8")
    )
    check("vertex manifest kind", vertex_manifest["ReviewKindFilter"], "vertex-semantic-change")
    check("vertex manifest report limit", vertex_manifest["ReviewReportLimit"], 100)
    jsonschema.validate(vertex_manifest, manifest_schema)
    print("  PASS: vertex manifest schema validation")

print(f"\n{'=' * 50}")
if failed:
    print(f"FAILURES: {failed}")
    sys.exit(1)
else:
    print("All tests passed!")
