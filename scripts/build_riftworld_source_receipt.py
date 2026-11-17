"""Build a source-only Assets receipt for future RiftWorld model import review.

Inputs are existing, previously qualified Assets RA-1 evidence reports.
This is NOT a riftworld.model/1, scene/1, or patch/1 descriptor.
No geometry, placement, transforms, collision or traversal is promoted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_live_archive_samples import sha256_file, write_report  # noqa: E402

SCHEMA = "riftassetdumper.source-evidence/1"
ID_RE = re.compile(r"[0-9a-f]{16}\Z")
SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
ARCHIVE_RE = re.compile(r"assets\.[0-9]{3}\Z")
MAX_LINKS = 64


def _hex(value: Any, expression: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or expression.fullmatch(value) is None:
        raise ValueError(f"{name} requires lowercase hexadecimal of expected length")
    return value


def _integer(value: Any, name: str, *, minimum: int = 0, maximum: int = 2**31 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def _pak_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("manifest PAK path must be a relative POSIX-style name")
    parts = value.split("/")
    if (value.startswith("/") or any(part in ("", ".", "..") for part in parts)):
        raise ValueError("manifest PAK path has an unsafe component")
    return value


def _sample_model_source(source_report: dict, model_id: str) -> dict:
    if source_report.get("schema") != "ra1-live-archive-samples/v1":
        raise ValueError("expected RA-1.1 source report schema")
    found: list[dict] = []
    for archive in source_report.get("archives", []):
        path = archive.get("source_path")
        if not isinstance(path, str) or not path.startswith("Assets/"):
            raise ValueError("invalid source archive path")
        filename = path.removeprefix("Assets/")
        if ARCHIVE_RE.fullmatch(filename) is None:
            raise ValueError("invalid source archive filename")
        sha = _hex(archive.get("archive_sha256"), SHA256_RE, "archive SHA256")
        for sample in archive.get("samples", []):
            if sample.get("id_prefix") == model_id:
                found.append(
                    {
                        "archive": path,
                        "archiveSha256": sha,
                        "entryIndex": _integer(sample.get("entry_index"), "model entry index"),
                        "contentIdPrefix": model_id,
                        "packedSha256": _hex(sample.get("packed_sha256"), SHA256_RE, "packed SHA256"),
                        "packedSha1": _hex(sample.get("stored_sha1_field"), SHA1_RE, "packed SHA1"),
                        "packedBytes": _integer(sample.get("packed_size"), "packed size", minimum=1),
                        "compressionCode": _integer(sample.get("compression_code"), "compression code", maximum=65535),
                    }
                )
    if len(found) != 1:
        raise ValueError(f"model ID must have one RA-1.1 source sample; found {len(found)}")
    return found[0]


def build_source_receipt(
    source_report: dict,
    link_proof: dict,
    *,
    manifest_sha256: str,
    decoded_nif_sha256: str,
    decoded_nif_sha1: str,
    source_report_sha256: str,
    link_report_sha256: str,
    synthetic_fixture: bool = False,
) -> dict:
    """Turn bounded validated evidence into a source-only, non-promotional receipt."""
    if not isinstance(source_report, dict) or not isinstance(link_proof, dict):
        raise ValueError("source reports must be JSON objects")
    if link_proof.get("schema") != "ra1-terrain-nif-dds-link-proof/v1":
        raise ValueError("expected RA-1.4b DDS link proof schema")
    manifest_hash = _hex(manifest_sha256, SHA256_RE, "manifest SHA256")
    if link_proof.get("manifest_source_sha256") != manifest_hash:
        raise ValueError("manifest hash conflicts with linked source proof")
    nif_sha256 = _hex(decoded_nif_sha256, SHA256_RE, "decoded NIF SHA256")
    nif_sha1 = _hex(decoded_nif_sha1, SHA1_RE, "decoded NIF SHA1")
    nif_id = _hex(link_proof.get("source_nif_id"), ID_RE, "model content ID")
    if link_proof.get("source_nif_sha256") != nif_sha256 or not nif_sha1.startswith(nif_id):
        raise ValueError("decoded NIF content identity disagrees with retained proof")
    origin = _sample_model_source(source_report, nif_id)
    if link_proof.get("pak_paths_are_manifest_metadata_not_verified_payload_locations") is not True:
        raise ValueError("PAK paths must remain explicitly non-verified payload locators")

    links = link_proof.get("links")
    if (not isinstance(links, list) or not 1 <= len(links) <= MAX_LINKS
            or link_proof.get("nif_reference_count") != len(links)
            or link_proof.get("verified_dds_count") != len(links)):
        raise ValueError("DDS reference coverage is incomplete or unbounded")
    result_links: list[dict] = []
    seen_indices: set[int] = set()
    seen_names: set[str] = set()
    for link in links:
        if not isinstance(link, dict):
            raise ValueError("DDS link must be an object")
        name = link.get("name")
        if (not isinstance(name, str) or not name.endswith(".dds")
                or "/" in name or "\\" in name or name in {".", ".."}):
            raise ValueError("DDS source reference must be a basename")
        string_index = _integer(link.get("nif_string_index"), "NIF string index")
        if string_index in seen_indices or name in seen_names:
            raise ValueError("duplicated NIF string index or name")
        seen_indices.add(string_index)
        seen_names.add(name)

        evidence = link.get("evidence")
        required = (
            "nif_string_reference", "unique_filename_fnv_and_length",
            "unique_archive_source_id", "packed_sha1_matches_archive_table",
            "decoded_sha1_prefix_matches_id", "dds_magic_and_decoded_size",
            "dotnet_probe_agrees",
        )
        if not isinstance(evidence, dict) or any(evidence.get(field) is not True for field in required):
            raise ValueError(f"unqualified DDS reference evidence: {name}")
        if any(evidence.get(field) is not False for field in (
            "render_material_slot", "pak_payload_equivalence", "world_or_collision",
        )):
            raise ValueError("this receipt cannot promote material, PAK or world assertions")

        content_id = _hex(link.get("content_id"), ID_RE, "texture content ID")
        decoded_sha1 = _hex(link.get("decoded_sha1"), SHA1_RE, "texture decoded SHA1")
        if not decoded_sha1.startswith(content_id):
            raise ValueError("texture content ID differs from decoded SHA1 prefix")
        archive = link.get("archive")
        if not isinstance(archive, str) or ARCHIVE_RE.fullmatch(archive) is None:
            raise ValueError("texture archive filename is invalid")
        duplicate_count = _integer(
            link.get("manifest_id_rows"), "manifest ID duplicate count", minimum=1,
            maximum=1_000_000,
        )
        result_links.append(
            {
                "nifStringIndex": string_index,
                "filenameCandidate": name,
                "decodedContentIdPrefix": content_id,
                "decodedSha1": decoded_sha1,
                "decodedSha256": _hex(link.get("decoded_sha256"), SHA256_RE, "texture decoded SHA256"),
                "decodedBytes": _integer(link.get("decoded_bytes"), "texture decoded size", minimum=1),
                "twad": {
                    "archive": f"Assets/{archive}",
                    "archiveSha256": _hex(link.get("archive_sha256"), SHA256_RE, "texture archive SHA256"),
                    "entryIndex": _integer(link.get("archive_entry"), "texture entry index"),
                    "packedSha1": _hex(link.get("packed_sha1"), SHA1_RE, "texture packed SHA1"),
                    "packedBytes": _integer(link.get("packed_bytes"), "texture packed size", minimum=1),
                },
                "manifestRecord": {
                    "index": _integer(link.get("filename_manifest_index"), "manifest row index"),
                    "filenameFnv1": _integer(
                        link.get("filename_fnv1"), "filename FNV1", maximum=2**32 - 1,
                    ),
                    "pakIndex": _integer(link.get("filename_manifest_pak_index"), "manifest PAK index"),
                    "pakPath": _pak_path(link.get("filename_manifest_pak_path")),
                    "contentIdManifestRowCount": duplicate_count,
                    "contentIdIsManifestUnique": duplicate_count == 1,
                },
                "evidence": {
                    "nifStringPresent": True,
                    "filenameFnvAndLengthUnique": True,
                    "twadEntryIdUniqueInScannedArchives": True,
                    "packedSha1AndDecodedSha1VerifiedInRetainedReports": True,
                    "decodedType": "dds",
                    "renderMaterialSlot": "unqualified",
                    "pakPayloadEquivalence": "unqualified",
                },
            }
        )
    result_links.sort(key=lambda x: (x["nifStringIndex"], x["filenameCandidate"]))
    ambiguous = sum(row["manifestRecord"]["contentIdManifestRowCount"] > 1 for row in result_links)
    if link_proof.get("ambiguous_manifest_id_count") != ambiguous:
        raise ValueError("manifest ambiguity count conflicts with retained proof")

    receipt = {
        "schema": SCHEMA,
        "kind": "producer-source-evidence-only",
        "fixtureStatus": "synthetic" if synthetic_fixture else "retained-local-source-evidence",
        "inputReports": {
            "archiveReportSha256": _hex(source_report_sha256, SHA256_RE, "RA-1.1 report SHA256"),
            "ddsLinkReportSha256": _hex(link_report_sha256, SHA256_RE, "RA-1.4b report SHA256"),
            "manifest": {"path": "assets64.manifest", "sha256": manifest_hash},
        },
        "sourceModel": {
            "locator": {"kind": "twad-entry", **origin},
            "decodedFileType": "nif",
            "rawSourceSha1": nif_sha1,
            "rawSourceSha256": nif_sha256,
            "sourceGeometryStatus": "unavailable",
        },
        "textures": result_links,
        "counts": {
            "verifiedSourceReferences": len(result_links),
            "ambiguousManifestContentIds": ambiguous,
        },
        "consumerBoundary": {
            "targetContracts": [
                "riftworld.model/1", "riftworld.scene/1", "riftworld.patch/1",
            ],
            "modelGeometryId": None,
            "modelLocalGeometrySha256": None,
            "modelNodeTransforms": None,
            "sourceWorld": None,
            "sourcePlacementMatrix": None,
            "sceneId": None,
            "patchId": None,
            "readiness": {
                "model": False, "scene": False, "patch": False,
                "navigation": False, "traversal": False,
            },
            "qualification": (
                "Provenance only: geometry/topology/transform/placement/source-world closure "
                "and collision/traversal remain unavailable. Not a RiftWorld model, scene, "
                "or WorldPatch descriptor; an importing consumer must separately qualify them."
            ),
        },
    }
    # Determinism and no NaN/Infinity or local paths in the producer receipt.
    json.dumps(receipt, sort_keys=True, allow_nan=False)
    return receipt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--archive-report", type=Path, default=REPO_ROOT / "Exports/ra1/live-archive-samples.json")
    p.add_argument("--dds-proof", type=Path, default=REPO_ROOT / "Exports/ra1/ra14b/dds-link-proof.json")
    p.add_argument("--manifest-file", type=Path, required=True)
    p.add_argument("--nif-file", type=Path, required=True)
    p.add_argument("--out", type=Path, default=REPO_ROOT / "Exports/ra2a/source-evidence.json")
    args = p.parse_args(argv)
    try:
        if args.manifest_file.name.lower() != "assets64.manifest":
            raise ValueError("expected primary assets64.manifest")
        source_report = json.loads(args.archive_report.read_text(encoding="utf-8"))
        link_proof = json.loads(args.dds_proof.read_text(encoding="utf-8"))
        if not args.nif_file.is_file() or not 0 < args.nif_file.stat().st_size <= 16 * 1024 * 1024:
            raise ValueError("bounded source NIF file is missing or oversized")
        with args.nif_file.open("rb") as stream:
            if not stream.read(32).startswith(b"Gamebryo File Format"):
                raise ValueError("source NIF does not have Gamebryo file magic")
        sha1 = hashlib.sha1(args.nif_file.read_bytes()).hexdigest()
        packet = build_source_receipt(
            source_report, link_proof,
            manifest_sha256=sha256_file(args.manifest_file),
            decoded_nif_sha256=sha256_file(args.nif_file),
            decoded_nif_sha1=sha1,
            source_report_sha256=sha256_file(args.archive_report),
            link_report_sha256=sha256_file(args.dds_proof),
        )
        dest = args.out if args.out.is_absolute() else REPO_ROOT / args.out
        write_report(dest, packet)
        print(
            f"RA-2a: source-only packet, {packet['counts']['verifiedSourceReferences']} "
            f"DDS references, {packet['counts']['ambiguousManifestContentIds']} "
            f"ambiguous IDs; model/scene/patch readiness=false -> {dest}"
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"RA-2a ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
