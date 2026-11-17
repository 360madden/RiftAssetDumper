"""RA-2a source-only RiftWorld handoff tests using synthetic, never game, data."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts import audit_live_archive_samples as archive_audit
from scripts import build_riftworld_source_receipt as producer

FIXTURE = Path(__file__).parent / "fixtures" / "ra2a_source_evidence_synthetic.json"
SCHEMA = Path(__file__).resolve().parents[1] / "docs/schemas/riftassetdumper-source-evidence-v1.schema.json"


def _synthetic() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["syntheticFixture"] is True
    return data


def _build(data: dict) -> dict:
    return producer.build_source_receipt(
        data["sourceReport"], data["linkProof"],
        manifest_sha256=data["manifestSha256"],
        decoded_nif_sha256=data["nifSha256"],
        decoded_nif_sha1=data["nifSha1"],
        source_report_sha256=data["archiveReportSha256"],
        link_report_sha256=data["linkReportSha256"],
        synthetic_fixture=True,
    )


def test_synthetic_fixture_is_not_world_geometry_or_ready() -> None:
    packet = _build(_synthetic())
    assert packet["schema"] == "riftassetdumper.source-evidence/1"
    assert packet["fixtureStatus"] == "synthetic"
    assert packet["sourceModel"]["locator"]["archive"] == "Assets/assets.001"
    assert packet["sourceModel"]["rawSourceSha256"] == "5" * 64
    assert packet["sourceModel"]["sourceGeometryStatus"] == "unavailable"
    assert packet["textures"][0]["manifestRecord"]["contentIdManifestRowCount"] == 2
    assert packet["textures"][0]["manifestRecord"]["contentIdIsManifestUnique"] is False
    boundary = packet["consumerBoundary"]
    assert boundary["modelGeometryId"] is None
    assert boundary["modelLocalGeometrySha256"] is None
    assert boundary["modelNodeTransforms"] is None
    assert boundary["sourcePlacementMatrix"] is None
    assert boundary["sourceWorld"] is None
    assert boundary["sceneId"] is None and boundary["patchId"] is None
    assert not any(boundary["readiness"].values())
    assert packet["counts"] == {"verifiedSourceReferences": 1, "ambiguousManifestContentIds": 1}
    assert "riftworld.model/1" in boundary["targetContracts"]
    assert packet["schema"] not in boundary["targetContracts"]
    assert "C:" not in json.dumps(packet, sort_keys=True)


def test_source_packet_json_schema_accepts_synthetic_fixture() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_build(_synthetic()))


def test_json_schema_refuses_promotion_or_unexpected_fields() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    packet = _build(_synthetic())
    packet["consumerBoundary"]["readiness"]["model"] = True
    with pytest.raises(ValidationError):
        validator.validate(packet)
    packet["consumerBoundary"]["readiness"]["model"] = False
    packet["consumerBoundary"]["modelGeometryId"] = "0" * 64
    with pytest.raises(ValidationError):
        validator.validate(packet)
    packet["consumerBoundary"]["modelGeometryId"] = None
    packet["textures"][0]["unknownPromotionFlag"] = True
    with pytest.raises(ValidationError):
        validator.validate(packet)


def test_deterministic_reference_order_and_retain_shared_content_identity() -> None:
    data = _synthetic()
    one = deepcopy(data["linkProof"]["links"][0])
    two = deepcopy(one)
    two["name"] = "another_name.dds"
    two["nif_string_index"] = 1
    two["filename_manifest_index"] = 10
    two["filename_fnv1"] = 4321
    # This second filename intentionally references the SAME content ID.
    data["linkProof"]["links"].append(two)
    data["linkProof"]["nif_reference_count"] = 2
    data["linkProof"]["verified_dds_count"] = 2
    data["linkProof"]["ambiguous_manifest_id_count"] = 2
    a = _build(data)
    data["linkProof"]["links"].reverse()
    b = _build(data)
    assert a == b
    assert [x["nifStringIndex"] for x in a["textures"]] == [1, 2]
    assert a["textures"][0]["decodedContentIdPrefix"] == a["textures"][1]["decodedContentIdPrefix"]
    assert a["counts"]["ambiguousManifestContentIds"] == 2


@pytest.mark.parametrize(
    "mutate, error",
    [
        (lambda d: d["sourceReport"]["archives"][0]["samples"].clear(), "one RA-1.1 source sample"),
        (lambda d: d["linkProof"].update({"manifest_source_sha256": "0" * 64}), "manifest hash conflicts"),
        (lambda d: d["linkProof"].update({"source_nif_sha256": "0" * 64}), "decoded NIF content identity"),
        (lambda d: d.update({"nifSha1": "f" * 40}), "decoded NIF content identity"),
        (lambda d: d["linkProof"].update({"verified_dds_count": 2}), "coverage is incomplete"),
        (lambda d: d["linkProof"].update({"ambiguous_manifest_id_count": 0}), "ambiguity count"),
        (lambda d: d["linkProof"]["links"][0]["evidence"].update({"dds_magic_and_decoded_size": False}), "unqualified DDS"),
        (lambda d: d["linkProof"]["links"][0]["evidence"].update({"render_material_slot": True}), "cannot promote"),
        (lambda d: d["linkProof"]["links"][0].update({"decoded_sha1": "0" * 40}), "decoded SHA1 prefix"),
        (lambda d: d["linkProof"]["links"][0].update({"filename_manifest_pak_path": "../escape.pak"}), "unsafe"),
        (lambda d: d["linkProof"]["links"][0].update({"archive": "assets.001/../../bad"}), "archive filename"),
        (lambda d: d["sourceReport"]["archives"][0]["samples"][0].update({"packed_sha256": "not-hex"}), "packed SHA256"),
    ],
)
def test_contradictory_or_unqualified_provenance_fails_closed(mutate, error: str) -> None:
    data = _synthetic()
    mutate(data)
    with pytest.raises(ValueError, match=error):
        _build(data)


@pytest.mark.parametrize("pakpath", ["./x.pak", "assets//x.pak", "assets/./x.pak", "assets/../x.pak", "/root/x.pak"])
def test_relative_pak_name_cannot_escape_or_alias(pakpath: str) -> None:
    data = _synthetic()
    data["linkProof"]["links"][0]["filename_manifest_pak_path"] = pakpath
    with pytest.raises(ValueError, match="unsafe|relative"):
        _build(data)


def test_duplicate_string_indices_are_rejected() -> None:
    data = _synthetic()
    data["linkProof"]["links"].append(deepcopy(data["linkProof"]["links"][0]))
    data["linkProof"]["nif_reference_count"] = 2
    data["linkProof"]["verified_dds_count"] = 2
    data["linkProof"]["ambiguous_manifest_id_count"] = 2
    with pytest.raises(ValueError, match="duplicated NIF"):
        _build(data)


def test_cli_uses_hash_bound_reports_and_ignored_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _synthetic()
    repo = tmp_path / "repo"
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    repo.mkdir()
    monkeypatch.setattr(producer, "REPO_ROOT", repo)
    monkeypatch.setattr(archive_audit, "REPO_ROOT", repo)

    nif_bytes = b"Gamebryo File Format, Version 20.6.0.0\n" + bytes(range(80))
    nif_file = inputs / "source.nif"
    nif_file.write_bytes(nif_bytes)
    nif_sha1 = hashlib.sha1(nif_bytes).hexdigest()
    nif_sha256 = hashlib.sha256(nif_bytes).hexdigest()
    data["sourceReport"]["archives"][0]["samples"][0]["id_prefix"] = nif_sha1[:16]
    data["linkProof"]["source_nif_id"] = nif_sha1[:16]
    data["linkProof"]["source_nif_sha256"] = nif_sha256

    manifest = inputs / "assets64.manifest"
    manifest.write_bytes(b"synthetic manifest fixture with hash only")
    data["linkProof"]["manifest_source_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()

    src = inputs / "archive-report.json"
    links = inputs / "dds-links.json"
    src.write_text(json.dumps(data["sourceReport"]), encoding="utf-8")
    links.write_text(json.dumps(data["linkProof"]), encoding="utf-8")
    out = repo / "Exports" / "ra2a" / "receipt.json"
    args = [
        "--archive-report", str(src), "--dds-proof", str(links),
        "--manifest-file", str(manifest), "--nif-file", str(nif_file),
        "--out", str(out),
    ]
    assert producer.main(args) == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["sourceModel"]["rawSourceSha256"] == nif_sha256
    assert receipt["sourceModel"]["locator"]["contentIdPrefix"] == nif_sha1[:16]
    assert receipt["inputReports"]["manifest"]["sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert all(ready is False for ready in receipt["consumerBoundary"]["readiness"].values())

    manifest.write_bytes(b"tampered manifest bytes")
    with pytest.raises(ValueError, match="manifest hash conflicts"):
        producer.build_source_receipt(
            data["sourceReport"], data["linkProof"],
            manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            decoded_nif_sha256=nif_sha256, decoded_nif_sha1=nif_sha1,
            source_report_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
            link_report_sha256=hashlib.sha256(links.read_bytes()).hexdigest(),
        )


def test_cli_rejects_non_nif_magic_without_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _synthetic()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(producer, "REPO_ROOT", repo)
    monkeypatch.setattr(archive_audit, "REPO_ROOT", repo)
    source = tmp_path / "source.json"
    links = tmp_path / "links.json"
    source.write_text(json.dumps(data["sourceReport"]), encoding="utf-8")
    links.write_text(json.dumps(data["linkProof"]), encoding="utf-8")
    nif = tmp_path / "fake.nif"
    nif.write_bytes(b"not NIF magic" + b"x" * 80)
    manifest = tmp_path / "assets64.manifest"
    manifest.write_bytes(b"fixture manifest")
    output = repo / "Exports" / "ra2a" / "must-not-exist.json"
    assert producer.main([
        "--archive-report", str(source), "--dds-proof", str(links),
        "--manifest-file", str(manifest), "--nif-file", str(nif),
        "--out", str(output),
    ]) == 1
    assert not output.exists()


def test_cli_output_outside_ignored_exports_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _synthetic()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(producer, "REPO_ROOT", repo)
    monkeypatch.setattr(archive_audit, "REPO_ROOT", repo)
    with pytest.raises(ValueError, match="ignored Exports"):
        producer.write_report(tmp_path / "outside.json", _build(data))
