"""RA-2d: verify one NIF NiTerrainNode -> NiMesh local transform chain.

A source-limited Gamebryo NiAVObject structure check. It does not qualify
RiftWorld world coordinates, model-root geometry, runtime placement or collision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_live_archive_samples import write_report  # noqa: E402

SCHEMA = "ra2d-source-nif-transform/1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_NIF = 16 * 1024 * 1024


def _block(source: bytes, by_index: dict[int, dict], index: int, type_name: str) -> bytes:
    item = by_index.get(index)
    if not isinstance(item, dict) or item.get("TypeName") != type_name:
        raise ValueError(f"source block #{index} is not {type_name}")
    offset, size = item.get("DataOffset"), item.get("Size")
    if (type(offset) is not int or type(size) is not int or offset < 0
            or size < 4 or offset + size > len(source)):
        raise ValueError("source block has invalid byte bounds")
    return source[offset:offset + size]


def parse_niavobject(payload: bytes) -> dict:
    """Parse bounded common NiObjectNET + AVObject transform/property fields."""
    offset = 0

    def read(fmt: str) -> int | float:
        nonlocal offset
        size = struct.calcsize(fmt)
        if offset + size > len(payload):
            raise ValueError("truncated NiAVObject field")
        result = struct.unpack_from(fmt, payload, offset)[0]
        offset += size
        return result

    name = read("<i")
    extras_count = read("<I")
    if extras_count > 32:
        raise ValueError("implausible extra-data count")
    extras = [read("<i") for _ in range(extras_count)]
    controller = read("<i")
    flags = read("<H")
    translation = [read("<f") for _ in range(3)]
    rotation = [[read("<f") for _ in range(3)] for _ in range(3)]
    scale = read("<f")
    property_count = read("<I")
    if property_count > 32:
        raise ValueError("implausible property count")
    properties = [read("<i") for _ in range(property_count)]
    collision = read("<i")
    floating = translation + [v for row in rotation for v in row] + [scale]
    if not all(math.isfinite(value) for value in floating) or scale <= 0:
        raise ValueError("non-finite or invalid source transform")
    return {
        "nameIndex": name,
        "extraDataIndices": extras,
        "controllerIndex": controller,
        "flags": flags,
        "translation": translation,
        "rotationRows": rotation,
        "scale": scale,
        "propertyIndices": properties,
        "collisionIndex": collision,
        "byteCount": offset,
    }


def _identity(transform: dict) -> bool:
    expected = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    return all(
        abs(transform["rotationRows"][r][c] - expected[r][c]) < 1e-7
        for r in range(3) for c in range(3)
    ) and abs(transform["scale"] - 1.0) < 1e-7


def _valid_indices(indices: list[int], blocks: dict[int, dict], *, expected: list[str] | None = None) -> bool:
    if any(i not in blocks for i in indices):
        return False
    return expected is None or [blocks[i]["TypeName"] for i in indices] == expected


def _child_refs(node_payload: bytes, after_avobject: int) -> tuple[list[int], list[int], int]:
    o = after_avobject

    def read_u32() -> int:
        nonlocal o
        if o + 4 > len(node_payload):
            raise ValueError("truncated NiTerrainNode hierarchy")
        x = struct.unpack_from("<I", node_payload, o)[0]
        o += 4
        return x

    def read_i32() -> int:
        nonlocal o
        if o + 4 > len(node_payload):
            raise ValueError("truncated NiTerrainNode child ref")
        x = struct.unpack_from("<i", node_payload, o)[0]
        o += 4
        return x

    count = read_u32()
    if count > 128:
        raise ValueError("unbounded NiTerrainNode children")
    children = [read_i32() for _ in range(count)]
    effects_count = read_u32()
    if effects_count > 128:
        raise ValueError("unbounded NiTerrainNode effects")
    effects = [read_i32() for _ in range(effects_count)]
    return children, effects, o


def analyze(source: bytes, nif_header: dict, expected_sha256: str) -> dict:
    if not 100 <= len(source) <= MAX_NIF or not source.startswith(b"Gamebryo File Format"):
        raise ValueError("source is not a bounded Gamebryo NIF")
    source_sha = hashlib.sha256(source).hexdigest()
    if SHA256.fullmatch(expected_sha256) is None or source_sha != expected_sha256:
        raise ValueError("NIF source SHA256 mismatch")
    if (not isinstance(nif_header, dict) or nif_header.get("Length") != len(source)
            or not isinstance(nif_header.get("Header"), dict)
            or nif_header["Header"].get("Warnings") != []):
        raise ValueError("NIF header report is missing or unqualified")
    declared = nif_header["Header"].get("Blocks")
    if not isinstance(declared, list):
        raise ValueError("missing source block declarations")
    blocks: dict[int, dict] = {}
    for block in declared:
        if (not isinstance(block, dict) or type(block.get("Index")) is not int
                or block["Index"] in blocks):
            raise ValueError("duplicate or invalid source block index")
        blocks[block["Index"]] = block

    parent_bytes = _block(source, blocks, 0, "NiTerrainNode")
    mesh_bytes = _block(source, blocks, 2, "NiMesh")
    parent = parse_niavobject(parent_bytes)
    mesh = parse_niavobject(mesh_bytes)
    if not _identity(parent) or not _identity(mesh):
        raise ValueError("this bounded source probe does not qualify nonidentity transforms")
    if not _valid_indices(parent["propertyIndices"], blocks, expected=["NiVertexColorProperty"]):
        raise ValueError("unexpected NiTerrainNode property references")
    if not _valid_indices(mesh["propertyIndices"], blocks, expected=["NiTexturingProperty", "NiMaterialProperty"]):
        raise ValueError("unexpected NiMesh property references")
    if not _valid_indices(mesh["extraDataIndices"], blocks, expected=["NiColorExtraData", "NiIntegersExtraData"]):
        raise ValueError("unexpected NiMesh extra-data references")
    if parent["collisionIndex"] != -1 or mesh["collisionIndex"] != -1:
        raise ValueError("unexpected NiAVObject collision reference")

    children, effects, after_hierarchy = _child_refs(parent_bytes, parent["byteCount"])
    if children != [2] or effects:
        raise ValueError("NiTerrainNode does not have one NiMesh #2 child and zero effects")

    # The currently qualified NIF has a five-record, 21-byte-spaced stream table
    # in NiMesh, with 32-bit block references at offsets 134, 155, 176, 197, 218.
    if len(mesh_bytes) < 222 or struct.unpack_from("<I", mesh_bytes, 130)[0] != 5:
        raise ValueError("NiMesh five-stream table count is missing")
    stream_refs = [struct.unpack_from("<I", mesh_bytes, 134 + 21 * i)[0] for i in range(5)]
    if stream_refs != [20, 21, 22, 23, 24]:
        raise ValueError("NiMesh stream references do not match the qualified source")
    if not all(str(blocks[i].get("TypeName", "")).startswith("NiDataStream") for i in stream_refs):
        raise ValueError("NiMesh referenced target is not a NiDataStream")

    # These identity rotations/scales make local node composition unambiguous.
    # This is still NOT an authoritative RiftWorld source-world transform.
    composed_translation = [
        parent["translation"][i] + mesh["translation"][i] for i in range(3)
    ]
    return {
        "schema": SCHEMA,
        "sourceNifSha256": source_sha,
        "sourceNifNode": {
            "blockIndex": 0,
            "type": "NiTerrainNode",
            "transform": parent,
            "childMeshIndices": children,
            "effectIndices": effects,
            "hierarchyEndOffset": after_hierarchy,
            "childrenQualifiedFromSourceBytes": True,
        },
        "sourceMesh": {
            "blockIndex": 2,
            "type": "NiMesh",
            "transform": mesh,
            "streamReferenceCount": len(stream_refs),
            "streamBlockIndices": stream_refs,
            "referenceOffsets": [134 + 21 * i for i in range(5)],
        },
        "localNodeComposition": {
            "parentRelativeTranslation": composed_translation,
            "rotationIdentity": True,
            "unitScale": True,
            "coordinateFrame": "NIF node hierarchy; mapping to RiftWorld source-world not established",
        },
        "consumerBoundary": {
            "sourceHierarchyQualified": True,
            "sourceWorld": None,
            "worldPlacementMatrix": None,
            "modelGeometryId": None,
            "originalTrianglesQualified": False,
            "riftworldModelReady": False,
            "riftworldSceneReady": False,
            "collisionOrNavigationQualified": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nif", type=Path, required=True)
    p.add_argument("--nif-header-report", type=Path, required=True)
    p.add_argument("--expected-nif-sha256", required=True)
    p.add_argument("--out", type=Path, default=ROOT / "Exports/ra2d/terrain-node-transform.json")
    args = p.parse_args(argv)
    try:
        if not args.nif.is_file() or not 100 <= args.nif.stat().st_size <= MAX_NIF:
            raise ValueError("NIF source is unavailable or outside bounds")
        header = json.loads(args.nif_header_report.read_text(encoding="utf-8-sig"))
        result = analyze(args.nif.read_bytes(), header, args.expected_nif_sha256)
        out = args.out if args.out.is_absolute() else ROOT / args.out
        write_report(out, result)
        print(
            f"RA-2d: parent #0 -> NiMesh #2, source-relative translation "
            f"{result['localNodeComposition']['parentRelativeTranslation']}, "
            f"RiftWorld readiness=false -> {out}"
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"RA-2d ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
