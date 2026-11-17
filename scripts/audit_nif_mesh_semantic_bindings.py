"""RA-2g: source-hash-bound NiMesh 21-byte semantic binding evidence.

Decode stream IDs and semantic string indices on a bounded terrain NiMesh.
Do not infer unknown record fields, original indices, world placement or collision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_nif_terrain_grid as grid  # noqa: E402
from scripts import audit_nif_terrain_node_transform as node  # noqa: E402
from scripts.audit_live_archive_samples import write_report  # noqa: E402

SCHEMA = "ra2g-nimesh-semantic-bindings/1"
SOURCE_HASH = re.compile(r"[0-9a-f]{64}\Z")
SEMANTICS = ("INDEX", "POSITION", "NORMAL", "COLOR", "TEXCOORD")
RECORD_SIZE = 21
STREAM_TABLE_OFFSET = 130


def inspect_mesh_bindings(
    mesh: bytes,
    string_table: dict[int, str],
    blocks: dict[int, dict],
) -> list[dict]:
    """Qualify this terrain profile by semantic name as well as stream target."""
    if not 150 <= len(mesh) <= 16 * 1024:
        raise ValueError("unsupported bounded NiMesh source payload length")
    if STREAM_TABLE_OFFSET + 4 > len(mesh):
        raise ValueError("truncated NiMesh record count")
    count = struct.unpack_from("<I", mesh, STREAM_TABLE_OFFSET)[0]
    if count != len(SEMANTICS) or STREAM_TABLE_OFFSET + 4 + count * RECORD_SIZE > len(mesh):
        raise ValueError("unsupported NiMesh 21-byte record count or truncated table")

    records = []
    seen_targets: set[int] = set()
    seen_semantics: set[str] = set()
    for ordinal in range(count):
        offset = STREAM_TABLE_OFFSET + 4 + ordinal * RECORD_SIZE
        target, flag, word5, word9, name_idx, semantic_ordinal = struct.unpack_from(
            "<IBIIII", mesh, offset,
        )
        if target in seen_targets or target not in blocks:
            raise ValueError("NiMesh has duplicate or nonexistent stream target")
        if not str(blocks[target].get("TypeName", "")).startswith("NiDataStream"):
            raise ValueError("NiMesh semantic target is not a NiDataStream")
        if name_idx not in string_table:
            raise ValueError("NiMesh semantic string index is out of range")
        name = string_table[name_idx]
        if name in seen_semantics or name != SEMANTICS[ordinal]:
            raise ValueError("NiMesh semantic ordering or name is unqualified")
        if flag != 0 or word5 != 1 or word9 != 1 or semantic_ordinal != 0:
            raise ValueError("NiMesh descriptor fields differ from qualified source profile")
        seen_targets.add(target)
        seen_semantics.add(name)
        records.append({
            "ordinal": ordinal,
            "meshByteOffset": offset,
            "targetBlockIndex": target,
            "semanticNameStringIndex": name_idx,
            "semanticName": name,
            "semanticOrdinal": semantic_ordinal,
            "flagByte": flag,
            "unknownWordAtPlus5": word5,
            "unknownWordAtPlus9": word9,
            "rawRecordSha256": hashlib.sha256(mesh[offset:offset + RECORD_SIZE]).hexdigest(),
        })
    if tuple(record["semanticName"] for record in records) != SEMANTICS:
        raise ValueError("NiMesh source semantic ordering changed")
    return records


def analyze_source(source: bytes, header: dict, expected_sha256: str) -> dict:
    if (not 100 <= len(source) <= node.MAX_NIF
            or not source.startswith(b"Gamebryo File Format")
            or SOURCE_HASH.fullmatch(expected_sha256) is None
            or hashlib.sha256(source).hexdigest() != expected_sha256):
        raise ValueError("source NIF magic/size/SHA256 does not qualify")
    if (not isinstance(header, dict) or header.get("Length") != len(source)
            or not isinstance(header.get("Header"), dict)
            or header["Header"].get("Warnings") != []):
        raise ValueError("NIF header report missing or inconsistent with source")
    blocks = {}
    for item in header["Header"].get("Blocks", []):
        if (not isinstance(item, dict) or type(item.get("Index")) is not int
                or item["Index"] in blocks):
            raise ValueError("invalid or duplicate NIF block record")
        blocks[item["Index"]] = item
    strings = {}
    for item in header["Header"].get("Strings", []):
        if (not isinstance(item, dict) or type(item.get("Index")) is not int
                or not isinstance(item.get("Value"), str)
                or item["Index"] in strings):
            raise ValueError("invalid or duplicate NIF string index")
        strings[item["Index"]] = item["Value"]
    mesh = node._block(source, blocks, 2, "NiMesh")
    avobject = node.parse_niavobject(mesh)
    if avobject["byteCount"] != 90:
        raise ValueError("NiMesh AVObject prefix differs from bounded terrain profile")
    bindings = inspect_mesh_bindings(mesh, strings, blocks)
    # Every named stream must actually exist in the source byte payload,
    # not merely be claimed by a compatible header type string.
    for binding in bindings:
        body = grid._stream_body(source, blocks, binding["targetBlockIndex"])
        binding["streamBodySha256"] = hashlib.sha256(body).hexdigest()
        binding["streamBodyBytes"] = len(body)
    return {
        "schema": SCHEMA,
        "sourceNifSha256": expected_sha256,
        "meshBlock": 2,
        "meshBlockSha256": hashlib.sha256(mesh).hexdigest(),
        "bytesPerBinding": RECORD_SIZE,
        "bindingCount": len(bindings),
        "semanticBindings": bindings,
        "qualified": {
            "streamIdsBoundToStringTableSemanticNames": True,
            "fullDescriptorFieldsSemanticsKnown": False,
            "nativeIndexEncodingKnown": False,
            "sourceWorldFrameQualified": False,
            "nativeTrianglesQualified": False,
            "riftworldModelReady": False,
        },
        "qualification": (
            "Five source stream refs and their string-table semantic names are independently "
            "bound in two source terrain NIF examples; flag and unknown u32 fields are observed "
            "but not interpreted as authoritative engine semantics. Index topology is unqualified."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nif", type=Path, required=True)
    p.add_argument("--nif-header-report", type=Path, required=True)
    p.add_argument("--expected-nif-sha256", required=True)
    p.add_argument("--out", type=Path, default=ROOT / "Exports/ra2g/semantic-bindings.json")
    args = p.parse_args(argv)
    try:
        if not args.nif.is_file() or not 100 <= args.nif.stat().st_size <= node.MAX_NIF:
            raise ValueError("bounded source NIF absent or oversized")
        header = json.loads(args.nif_header_report.read_text(encoding="utf-8-sig"))
        report = analyze_source(args.nif.read_bytes(), header, args.expected_nif_sha256)
        out = args.out if args.out.is_absolute() else ROOT / args.out
        write_report(out, report)
        print(
            f"RA-2g: {report['bindingCount']} source-bound names="
            f"{','.join(r['semanticName'] for r in report['semanticBindings'])}; "
            f"original topology unqualified -> {out}"
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"RA-2g ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
