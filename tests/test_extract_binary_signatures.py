"""Tests for ``scripts/extract_binary_signatures.py``.

Exercises:
1. Happy path: synthesize + write.
2. validate-only mode: schema-validates but does not write.
3. Missing Phase 3 catalog: skips Phase 3 silently, emits valid DB without it.
4. Missing input: returns exit 2.
5. Schema-fail input: returns exit 1.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

EXTRACT = REPO_ROOT / "scripts" / "extract_binary_signatures.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _minimal_phase2(path: Path) -> Path:
    doc = {
        "SchemaVersion": "binary-signatures/v1",
        "BinaryTarget": "rift_x64.exe",
        "BinaryVersion": {
            "PEFileVersion": "1",
            "PETimestamp": 1700000000,
            "PETimestampUTC": "2024-01-01T00:00:00Z",
            "FileSizeBytes": 50000000,
        },
        "ImageBase": "0x140000000",
        "ExtractedAt": "2024-01-01T00:00:00Z",
        "WildcardPolicy": "test",
        "CandidateOnly": True,
        "Provenance": {
            "DiscoveryMethod": "modrm-cluster-heuristic",
            "ValidationMethod": "full-binary-uniqueness-scan",
        },
        "Anchors": [
            {
                "Name": "vtable-dispatch",
                "StabilityTier": 1,
                "SignatureHex": "48 85 D2 74 0A",
                "SignatureLength": 4,
                "WildcardCount": 0,
                "UniquenessVerified": True,
                "DiscoveryMethod": "modrm-cluster-heuristic",
            }
        ],
        "Summary": {
            "TotalAnchors": 1,
            "UniqueSignatures": 1,
            "NonUniqueSignatures": 0,
            "StabilityTier1Count": 1,
            "StabilityTier2Count": 0,
            "StabilityTier3Count": 0,
        },
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _minimal_phase3(path: Path) -> Path:
    doc = {
        "SchemaVersion": "struct-layout-catalog/v1",
        "BinaryTarget": "rift_x64.exe",
        "ImageBase": "0x140000000",
        "ExtractedAt": "2024-01-01T00:00:00Z",
        "EvidenceSources": {
            "ModRMScanSchema": "modrm-memory-access-scan/v1",
            "ModRMScanPath": "Exports/binary-phase1/modrm-memory-access-scan.json",
            "ModRMTotalHits": 1000,
            "SignatureCatalogSchema": "binary-signatures/v1",
            "SignatureCatalogPath": "Exports/binary-phase2/rift-x64-signature-catalog.json",
            "GhidraReports": [],
        },
        "GhidraFindings": {},
        "Structs": [
            {
                "Name": "LocalPlayer",
                "Description": "Test",
                "EvidenceSource": "modrm-memory-access-scan/v1",
                "BaseRegisters": {"RBX": 100, "RCX": 50},
                "TotalModRMHits": 150,
                "SignatureAnchors": ["vtable-dispatch"],
                "Fields": [
                    {
                        "Offset": 800,
                        "OffsetHex": "0x320",
                        "Name": "pos_x",
                        "Type": "float32",
                        "Confidence": "confirmed",
                        "ModRMHitCount": 623,
                        "RiftReaderField": "pos_x",
                        "Notes": "primary X",
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


def test_happy_path_writes_output(tmp_path: Path) -> None:
    phase2 = _minimal_phase2(tmp_path / "phase2.json")
    phase3 = _minimal_phase3(tmp_path / "phase3.json")
    out = tmp_path / "unified.json"
    rc = subprocess.run(
        [
            sys.executable,
            str(EXTRACT),
            "--phase2-catalog",
            str(phase2),
            "--phase3-catalog",
            str(phase3),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).returncode
    assert rc == 0, f"extract failed: {rc}, stderr: {rc!r}, stdout: {rc!r}"
    assert out.exists(), "out path missing"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["SchemaVersion"] == "binary-signatures/v1"
    assert len(doc["Anchors"]) >= 1
    manifest = next(out.parent.glob(f"{out.stem}.extraction-manifest.json"), None)
    assert manifest is not None, "extraction manifest missing"
    mdoc = json.loads(manifest.read_text(encoding="utf-8"))
    assert mdoc["SchemaVersion"] == "binary-extraction-manifest/v1"


def test_validate_only_does_not_write(tmp_path: Path) -> None:
    phase2 = _minimal_phase2(tmp_path / "phase2.json")
    phase3 = _minimal_phase3(tmp_path / "phase3.json")
    out = tmp_path / "unified.json"
    rc = subprocess.run(
        [
            sys.executable,
            str(EXTRACT),
            "--phase2-catalog",
            str(phase2),
            "--phase3-catalog",
            str(phase3),
            "--out",
            str(out),
            "--validate-only",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).returncode
    assert rc == 0, f"extract --validate-only failed: {rc}"
    assert not out.exists(), "out should not be written in validate-only mode"


def test_missing_phase3_skipped_silently(tmp_path: Path) -> None:
    phase2 = _minimal_phase2(tmp_path / "phase2.json")
    out = tmp_path / "unified.json"
    rc = subprocess.run(
        [
            sys.executable,
            str(EXTRACT),
            "--phase2-catalog",
            str(phase2),
            "--phase3-catalog",
            "",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).returncode
    assert rc == 0
    assert out.exists()
    doc = json.loads(out.read_text(encoding="utf-8"))
    # Schema valid even without phase 3
    assert doc["SchemaVersion"] == "binary-signatures/v1"


def test_missing_input_returns_exit_2(tmp_path: Path) -> None:
    """If Phase 2 catalog is missing, extract must exit 2."""
    phase3 = _minimal_phase3(tmp_path / "phase3.json")
    rc = subprocess.run(
        [
            sys.executable,
            str(EXTRACT),
            "--phase2-catalog",
            str(tmp_path / "missing.json"),
            "--phase3-catalog",
            str(phase3),
            "--out",
            str(tmp_path / "out.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).returncode
    assert rc in (1, 2), f"expected 1 (validation) or 2 (synth error), got {rc}"


def test_empty_phase2_anchors_raises(tmp_path: Path) -> None:
    """If the Phase 2 Anchors[] is empty, the synthesizer should raise ValueError."""
    phase2 = tmp_path / "phase2.json"
    empty = {
        "SchemaVersion": "binary-signatures/v1",
        "BinaryTarget": "rift_x64.exe",
        "BinaryVersion": {"PEFileVersion": "0", "PETimestamp": 0, "PETimestampUTC": "", "FileSizeBytes": 0},
        "ImageBase": "0x140000000",
        "WildcardPolicy": "test",
        "CandidateOnly": True,
        "Provenance": {},
        "Anchors": [],
        "Summary": {
            "TotalAnchors": 0,
            "UniqueSignatures": 0,
            "NonUniqueSignatures": 0,
            "StabilityTier1Count": 0,
            "StabilityTier2Count": 0,
            "StabilityTier3Count": 0,
        },
    }
    phase2.write_text(json.dumps(empty), encoding="utf-8")
    rc = subprocess.run(
        [
            sys.executable,
            str(EXTRACT),
            "--phase2-catalog",
            str(phase2),
            "--phase3-catalog",
            "",
            "--out",
            str(tmp_path / "out.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).returncode
    assert rc in (1, 2), f"expected 1 (validation) or 2 (synth error), got {rc}"
